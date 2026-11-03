"""
Клиент YandexGPT (второй провайдер; исключение из принципа 4, решение
владельца 2026-10-08)

API — Yandex AI Studio, нативный `foundationModels.completion`:
`https://llm.api.cloud.yandex.net/foundationModels/v1/completion`.
Авторизация: `Authorization: Api-Key <ключ>`. Модель — строка вида
`gpt://<folder_id>/<model>/latest`. Сверено по документации Yandex Cloud
2026-10-20: `https://yandex.cloud/ru/docs/foundation-models/text-generation/api-ref/TextGeneration/completion`.

Безопасный клиент — замечание 5 ревью безопасности:
- сессия `requests.Session()` с `trust_env=False` (не берёт прокси/.netrc/CA
  из окружения);
- `verify=True` (проверка сертификата **не отключается**);
- `allow_redirects=False` (к LLM уходит только то, что мы послали);
- явные таймауты соединения и чтения, явный `maxTokens`;
- любое исключение транспорта или 4xx/5xx → `YandexGPTError(...) from None`:
  ключ, заголовки, тело ответа **не** попадают в текст исключения, в логи
  и в ответ пользователю;
- образец печати длины ключа при импорте (как у GigaChat) НЕ повторяется.
"""

import logging

import requests
from django.conf import settings

from langchain_core.messages import HumanMessage, SystemMessage

from .gigachat_api import (
    GigaChatTokenUsage,
    _account_llm_call,
    _token_limit_reached,
    assemble_prompt_from_criteria,
    build_user_message,
    estimate_tokens,
    postprocess_final_result,
)


logger = logging.getLogger(__name__)


# Константные сообщения-ошибки (замечание 5 ревью безопасности):
# ровно одно сообщение на уровне view на каждый случай, никаких «ключ не
# принят» или «вот тело ответа» — иначе ключ и внутренности апстрима
# утекут в HTML-страницу, лог или history
MSG_YANDEX_GENERATION_FAILED = (
    'Не удалось сгенерировать текст. Сервис генерации временно недоступен, попробуйте позже.'
)
MSG_YANDEX_LIMIT_REACHED = (
    'Лимит токенов YandexGPT исчерпан. Генерация недоступна.'
)
MSG_YANDEX_RATE_LIMITED = (
    'Слишком много запросов к YandexGPT. Попробуйте позже.'
)
MSG_YANDEX_NOT_CONFIGURED = (
    'Модель YandexGPT недоступна: ключ не настроен.'
)


YANDEX_COMPLETION_URL = (
    'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
)


class YandexGPTError(Exception):
    """
    Ошибка YandexGPT для показа пользователю

    Контракт тот же, что у `GigaChatError` в `gigachat_api.py` (из фазы 2а.1):
    `.message` — константная строка на русском без технических подробностей
    (её view возвращает как `error`), `.status_code` — HTTP-код ответа
    (502 — апстрим недоступен; 429 — упёрлись в rate limit; 400 — ключ
    не настроен). Текст исключения не содержит ключа, заголовков и тела
    апстрима — такое исключение можно безопасно сериализовать в ответ.
    """

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _make_session():
    """
    Безопасная `requests.Session` для YandexGPT

    `trust_env=False`: сессия не читает `HTTP_PROXY`, `HTTPS_PROXY`,
    `.netrc`, `REQUESTS_CA_BUNDLE` и `CURL_CA_BUNDLE`. Иначе переменные
    окружения могли бы перенаправить запрос через прокси или подменить CA
    """
    session = requests.Session()
    session.trust_env = False
    return session


class _TransportFailure(Exception):
    """
    Внутреннее исключение, которое `_do_http_call` поднимает при ошибке.

    `_call_completion` ловит его и поднимает `YandexGPTError` без ссылки
    на ключ в своих локалах. Так ключ, заголовки и тело апстрима не
    попадают в фрейм, где рождается наружное исключение (замечание 5
    ревью безопасности, Django `ExceptionReporter` показывает f_locals).
    """

    def __init__(self, message, status_code):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _do_http_call(system_prompt, user_message, api_key, folder_id,
                  model_name, max_tokens, connect_timeout, read_timeout):
    """
    Один HTTP-запрос к YandexGPT; возвращает текст ответа модели

    Любая ошибка — `_TransportFailure` без текста исключения и тела ответа.
    Эта функция ВЛАДЕЕТ ключом; наружное исключение `YandexGPTError`
    поднимается уровнем выше, где ключа в локалах уже нет
    """
    model_uri = f"gpt://{folder_id}/{model_name}/latest"
    payload = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": 0.6,
            "maxTokens": str(max_tokens),
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_message},
        ],
    }
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
    }
    session = _make_session()
    try:
        response = session.post(
            YANDEX_COMPLETION_URL,
            json=payload,
            headers=headers,
            timeout=(connect_timeout, read_timeout),
            verify=True,
            allow_redirects=False,
        )
    except Exception:
        # Чистим ссылки, которые могли остаться во фрейме исключения
        headers = payload = None
        logger.error('YandexGPT: ошибка транспорта')
        raise _TransportFailure(MSG_YANDEX_GENERATION_FAILED, 502) from None

    # Больше ключ не нужен — чистим локальные ссылки, чтобы f_locals не хранили
    headers = payload = api_key = None

    status = response.status_code
    if status == 429:
        logger.error('YandexGPT: 429 Too Many Requests')
        raise _TransportFailure(MSG_YANDEX_RATE_LIMITED, 429) from None
    if status >= 400:
        logger.error('YandexGPT: ответ со статусом %s', status)
        raise _TransportFailure(MSG_YANDEX_GENERATION_FAILED, 502) from None
    if 300 <= status < 400:
        logger.error('YandexGPT: неожиданный редирект %s', status)
        raise _TransportFailure(MSG_YANDEX_GENERATION_FAILED, 502) from None

    try:
        data = response.json()
        return data['result']['alternatives'][0]['message']['text']
    except Exception:
        logger.error('YandexGPT: не удалось разобрать ответ')
        raise _TransportFailure(MSG_YANDEX_GENERATION_FAILED, 502) from None


def _call_completion(system_prompt, user_message, *, api_key, folder_id,
                     model_name, max_tokens, connect_timeout, read_timeout):
    """
    Безопасная обёртка над `_do_http_call`

    Прячет ключ: `YandexGPTError` поднимается из фрейма, где `api_key`
    уже удалён из локалов. Django `ExceptionReporter` рендерит f_locals,
    поэтому локальную переменную с ключом нужно убрать до `raise`
    (замечание 5 ревью безопасности).
    """
    try:
        result = _do_http_call(
            system_prompt, user_message, api_key, folder_id,
            model_name, max_tokens, connect_timeout, read_timeout,
        )
        # Чистим ключ сразу после успешного вызова на всякий случай
        del api_key
        return result
    except _TransportFailure as failure:
        message = failure.message
        status_code = failure.status_code
        # Убираем ключ и внутреннее исключение из локалов этого фрейма —
        # иначе `ExceptionReporter.get_traceback_html()` покажет f_locals,
        # где они всё ещё есть
        del api_key, failure
        raise YandexGPTError(message, status_code=status_code) from None


def _call_from_settings(system_prompt, user_message):
    """
    Читает ключ из `settings` и вызывает `_call_completion`

    Выделено в отдельную функцию, чтобы `api_key` жил только в её
    локалах — родительский фрейм `generate_text_yandex`, через который
    пойдёт `__traceback__` исключения, ключа не видит (замечание 5)
    """
    api_key = getattr(settings, 'YANDEX_API_KEY', '') or ''
    folder_id = getattr(settings, 'YANDEX_FOLDER_ID', '') or ''
    if not api_key or not folder_id:
        raise YandexGPTError(MSG_YANDEX_NOT_CONFIGURED, status_code=400)

    try:
        return _call_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            api_key=api_key,
            folder_id=folder_id,
            model_name=getattr(settings, 'YANDEX_GPT_MODEL', 'yandexgpt-lite'),
            max_tokens=getattr(settings, 'YANDEX_MAX_TOKENS', 2000),
            connect_timeout=getattr(settings, 'YANDEX_CONNECT_TIMEOUT', 10.0),
            read_timeout=getattr(settings, 'YANDEX_READ_TIMEOUT', 60.0),
        )
    finally:
        # Чистим локалы: `api_key` и `folder_id` больше не нужны,
        # но мы в `finally` — Python не удаляет f_locals после возврата.
        # `del` сработает до пропуска исключения вверх
        try:
            del api_key
        except NameError:
            pass


def generate_text_yandex(data, user=None, token=None, generation_id=None):
    """
    Генерирует текст через YandexGPT

    Контракт тот же, что у `generate_text` в `gigachat_api.py`: тот же
    системный промпт, то же сообщение пользователя (единый путь текста
    для трёх моделей), та же постобработка. Строка учёта пишется с
    `provider='yandexgpt'` и `model_code='yandexgpt'` — коды из закрытого
    списка `GigaChatTokenUsage.PROVIDER_CHOICES` (не из env).

    Raises:
        YandexGPTError: исчерпан лимит токена, ключ не настроен или сбой апстрима.
    """
    if _token_limit_reached(token):
        raise YandexGPTError(MSG_YANDEX_LIMIT_REACHED, status_code=429)

    system_prompt = assemble_prompt_from_criteria(data)
    user_message = build_user_message(data)
    full_prompt = f"{system_prompt}\n\n{user_message}"

    # Ключ читается во внутренней функции — в этом фрейме его нет
    raw_text = _call_from_settings(system_prompt, user_message)

    clean_result = postprocess_final_result(raw_text, data.get('platform'))

    _account_llm_call(
        token,
        estimate_tokens(full_prompt) + estimate_tokens(raw_text),
        operation_type='TEXT_GENERATION',
        prompt_text=full_prompt,
        response_text=raw_text,
        generation_id=generation_id,
        user=user,
        topic=data.get('topic'),
        platform=data.get('platform'),
        provider=GigaChatTokenUsage.PROVIDER_YANDEXGPT,
        model_code=GigaChatTokenUsage.PROVIDER_YANDEXGPT,
    )

    return clean_result
