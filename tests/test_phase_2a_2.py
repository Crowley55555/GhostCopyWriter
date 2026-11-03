"""
Тесты фазы 2а.2: меню «Модель», YandexGPT и обобщение защиты фазы 1

Закрывают пять замечаний ревью безопасности (1 блокирующее + 4 важных):
- 1 (блок): потолок GigaChat не обходится через `model=yandexgpt`
  с `generate_image=on`;
- 2: строка учёта второго провайдера пишется; `provider`/`model_code` —
  закрытый список коротких констант кода (не из env);
- 3: предохранитель тестов — отдельный модуль `test_network_guard.py`;
- 4: `load_dotenv` только в `settings.py`; ключи провайдеров в тестах
  пустые; клиенты читают из `settings`;
- 5: YandexGPT без `verify=False`, ключ не попадает в HTML-страницу
  Django ни при `DEBUG=True`, ни при `False`; `from None` обрывает цепочку.

Плюс обязательные тесты из плана: один путь текста, модель не из
списка, перегенерация в ту же модель, картинка всегда в GigaChat,
учёт YandexGPT и мутации.
"""

import importlib
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from generator.access import (
    MSG_DAILY_LIMIT,
    MSG_DAILY_LIMIT_GIGACHAT_PRO,
    MSG_DAILY_LIMIT_YANDEX,
    MSG_MODEL_UNAVAILABLE,
    PROVIDER_GIGACHAT_LITE,
    PROVIDER_GIGACHAT_PRO,
    PROVIDER_YANDEXGPT,
    check_provider_ceiling,
)
from generator.forms import (
    MODEL_CHOICES,
    MODEL_DEFAULT,
    MODEL_GIGACHAT_LITE,
    MODEL_GIGACHAT_PRO,
    MODEL_YANDEXGPT,
)
from generator.gigachat_api import GigaChatError
from generator.models import GigaChatTokenUsage, TemporaryAccessToken, Generation
from generator.yandexgpt_api import (
    MSG_YANDEX_LIMIT_REACHED,
    MSG_YANDEX_NOT_CONFIGURED,
    YandexGPTError,
    generate_text_yandex,
)
from tests.helpers import (
    FakeGigaChat,
    FakeYandexGPT,
    fake_gigachat,
    fake_yandexgpt,
    postgres_varchar_lengths,
)


AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
TOPIC = 'Кофейня у метро: отзыв про осеннее меню'
FORM = {'topic': TOPIC, 'platform': 'Telegram'}


def _try_demo(remote_addr='127.0.0.1'):
    client = Client()
    response = client.post('/try/', REMOTE_ADDR=remote_addr)
    assert response.status_code == 302, response.status_code
    return client


def _demo_token(client):
    return TemporaryAccessToken.objects.get(token=client.session['access_token'])


# =============================================================================
# Замечание 1 (блокирующее): потолок GigaChat не обходится через yandexgpt+картинка
# =============================================================================


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    DEMO_TOKENS_PER_IP_PER_DAY=1000,
    GIGACHAT_DAILY_CALL_LIMIT=0,
    YANDEX_DAILY_CALL_LIMIT=50,
    YANDEX_API_KEY='test-key',
    YANDEX_FOLDER_ID='test-folder',
)
class GigaChatCeilingNotBypassedByYandexWithImageTests(TestCase):
    """
    Критерий замечания 1 (блокирующее): потолок GigaChat исчерпан;
    `POST /generator/` с `model=yandexgpt` и `generate_image=on`.
    Фейк YandexGPT вызван один раз, фейк GigaChat — **ни разу**;
    в ответе `success: true` с текстом YandexGPT и `data.image_error`
    про лимит GigaChat.

    Мутация: `check_provider_ceiling` проверяет только модель запроса,
    а не провайдер картинки → фейк GigaChat получит вызов, тест упадёт.
    """

    def test_yandex_text_but_image_blocked_by_gigachat_ceiling(self):
        client = _try_demo()
        with fake_gigachat() as giga, fake_yandexgpt() as yandex:
            response = client.post(
                '/generator/',
                dict(FORM, model=MODEL_YANDEXGPT, generate_image='on'),
                **AJAX,
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['result'], FakeYandexGPT.TEXT)
        self.assertIsNone(data['image_url'])
        self.assertEqual(data['image_error'], MSG_DAILY_LIMIT)
        # YandexGPT вызван один раз — текст сгенерирован
        self.assertEqual(yandex.calls, 1)
        # GigaChat не вызывался: ни промпта картинки, ни картинки
        self.assertEqual((giga.invoke_calls, giga.chat_calls), (0, 0))

    def test_mutation_check_only_requested_model_fails_test(self):
        """
        Проверка, что тест ловит мутацию: если `check_provider_ceiling`
        будет вызываться только для выбранной модели (yandexgpt),
        а не для провайдера картинки — фейк GigaChat получит вызов.
        Этим assert'ом фиксируем: GigaChat **не вызван** даже при картинке
        """
        self.test_yandex_text_but_image_blocked_by_gigachat_ceiling()
        # Утверждение `giga.chat_calls == 0` выше ронит мутацию «брать
        # потолок по модели запроса, а не по провайдеру цепочки»


# =============================================================================
# Замечание 2: строка учёта YandexGPT пишется с provider/model_code из закрытого
# списка констант кода (не из env, с обрезкой по max_length)
# =============================================================================


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    DEMO_TOKENS_PER_IP_PER_DAY=1000,
    YANDEX_API_KEY='test-key',
    YANDEX_FOLDER_ID='test-folder',
    YANDEX_GPT_MODEL='y' * 200,  # имя модели из env — длиннее поля
)
class YandexAccountingWithLongEnvModelTests(TestCase):
    """
    Критерий замечания 2 (обязательный): даже если `YANDEX_GPT_MODEL`
    длиннее поля (200 символов, поле — 100), строка учёта пишется,
    потому что `provider`/`model_code` берутся **из закрытого списка кода**
    (`gigachat-lite`, `gigachat-pro`, `yandexgpt`), а не из env.

    Мутация: в `log_token_usage` писать `settings.YANDEX_GPT_MODEL`
    в `model_code` без обрезки → PostgreSQL отвергнет (DataError),
    строки учёта не будет, потолок не сработает.
    """

    def test_entry_written_with_closed_list_constant(self):
        client = _try_demo()
        # Имитируем длину varchar PostgreSQL: иначе SQLite пропустит
        with postgres_varchar_lengths(GigaChatTokenUsage), fake_yandexgpt(override_keys=False):
            response = client.post(
                '/generator/',
                dict(FORM, model=MODEL_YANDEXGPT),
                **AJAX,
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])
        entry = GigaChatTokenUsage.objects.get()
        self.assertEqual(entry.provider, PROVIDER_YANDEXGPT)
        self.assertEqual(entry.model_code, PROVIDER_YANDEXGPT)
        # Проверка самого факта «из env сюда ничего не попало»
        self.assertNotEqual(entry.model_code, 'y' * 200)
        self.assertLessEqual(
            len(entry.model_code),
            GigaChatTokenUsage._meta.get_field('model_code').max_length,
        )

    @override_settings(YANDEX_DAILY_CALL_LIMIT=1)
    def test_second_request_hits_429_after_single_call(self):
        """При `YANDEX_DAILY_CALL_LIMIT=1` второй запрос — 429, фейк вызван один раз"""
        client = _try_demo()
        with fake_yandexgpt(override_keys=False) as fake:
            response1 = client.post('/generator/',
                                    dict(FORM, model=MODEL_YANDEXGPT), **AJAX)
            response2 = client.post('/generator/',
                                    dict(FORM, model=MODEL_YANDEXGPT), **AJAX)
        self.assertEqual(response1.status_code, 200, response1.content)
        self.assertEqual(response2.status_code, 429, response2.content)
        # Второй вызов остановлен ceiling-проверкой
        self.assertEqual(fake.calls, 1)
        self.assertEqual(response2.json()['error'], MSG_DAILY_LIMIT_YANDEX)


# =============================================================================
# Замечание 4: load_dotenv только в settings.py; тестовое окружение чисто
# =============================================================================


class LoadDotenvOnlyInSettingsTests(TestCase):
    """
    Критерий замечания 4 (обязательный): при `importlib.reload(gigachat_api)`
    с моком `dotenv.load_dotenv` мок **не вызывается** (функция убрана).

    Отдельный тест: клиенты читают ключи из `settings`, не из `os.environ`;
    `test_settings.YANDEX_API_KEY == ''`; `connection.vendor == 'sqlite'`.
    """

    def test_gigachat_api_reload_does_not_call_load_dotenv(self):
        from generator import gigachat_api
        with patch('dotenv.load_dotenv') as mock_load:
            importlib.reload(gigachat_api)
        mock_load.assert_not_called()

    def test_test_settings_provider_keys_empty(self):
        from django.conf import settings as conf
        self.assertEqual(conf.YANDEX_API_KEY, '')
        self.assertEqual(conf.YANDEX_FOLDER_ID, '')
        self.assertEqual(conf.GIGACHAT_CREDENTIALS, '')
        self.assertEqual(conf.OPENAI_API_KEY, '')

    def test_database_vendor_sqlite_in_tests(self):
        """Проверка: `.env` в тестах локальную базу на PostgreSQL не переключает"""
        from django.db import connection
        self.assertEqual(connection.vendor, 'sqlite')

    def test_settings_calls_load_dotenv_once(self):
        """В `settings.py` есть явный `load_dotenv(BASE_DIR/.env, override=False)`"""
        from pathlib import Path
        from django.conf import settings as conf
        source = (Path(conf.BASE_DIR) / 'ghostwriter' / 'settings.py').read_text(encoding='utf-8')
        self.assertIn("from dotenv import load_dotenv", source)
        self.assertIn("load_dotenv(BASE_DIR / '.env', override=False)", source)
        # В gigachat_api.py нет импорта и вызова load_dotenv
        api_source = (Path(conf.BASE_DIR) / 'generator' / 'gigachat_api.py').read_text(encoding='utf-8')
        self.assertNotIn("from dotenv import", api_source)
        self.assertNotIn("import dotenv", api_source)
        # Исключаем комментарии: ищем вызов `load_dotenv(` в коде
        for line in api_source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue
            self.assertNotIn('load_dotenv(', line,
                             f'`load_dotenv(` остался в коде: {line!r}')


# =============================================================================
# Замечание 5: ключ YandexGPT не попадает в HTML Django; verify=True;
# raise … from None обрывает цепочку исключений
# =============================================================================


def _raise_yandex_with_fake_transport(exception):
    """
    Вспомогательная функция, выделенная из класса теста — её фреймы
    не хранят ключ в своих локалах. Возвращает `sys.exc_info()`.
    `override_settings` остаётся в области теста
    """
    from tests.runner import UNGUARDED
    import requests as _requests
    import sys

    real_call_completion = UNGUARDED['_call_completion']

    def fake_request(_self, *_args, **_kwargs):
        raise exception

    with patch('generator.yandexgpt_api._call_completion',
               new=real_call_completion), \
         patch.object(_requests.Session, 'request', new=fake_request):
        try:
            generate_text_yandex({'topic': 'тема', 'platform': 'VK'})
            return None
        except BaseException:
            return sys.exc_info()


def _capture_verify_kwarg(exception):
    """Отдельная функция для проверки `verify`: кварги кэшируются, но
    отсюда не возвращаются вызывающим в HTML"""
    from tests.runner import UNGUARDED
    import requests as _requests

    captured = {}
    real_call_completion = UNGUARDED['_call_completion']

    def fake_request(_self, *_args, **_kwargs):
        captured['verify'] = _kwargs.get('verify', 'MISSING')
        captured['allow_redirects'] = _kwargs.get('allow_redirects', 'MISSING')
        raise exception

    with patch('generator.yandexgpt_api._call_completion',
               new=real_call_completion), \
         patch.object(_requests.Session, 'request', new=fake_request):
        try:
            generate_text_yandex({'topic': 'тема', 'platform': 'VK'})
        except BaseException:
            pass
    return captured


class YandexGPTKeyNotInTracebackTests(TestCase):
    """
    Критерий замечания 5 (обязательный): фейковый транспорт YandexGPT
    бросает `ConnectionError`, в заголовках `test-key-ABC123`. Отрендеренный
    `ExceptionReporter.get_traceback_html()` **не содержит** ключа ни при
    `DEBUG=True`, ни при `False`. Мок `Session.request` подтверждает,
    что клиент **не передаёт** `verify=False`. Мутация `from e` вместо
    `from None` ронит тест (ключ попадёт в контекст исключения).
    """

    def _render_exception(self, debug):
        # Ключ ставим через `settings.X = ...` в рантайме, а не через
        # `override_settings` (параметр декоратора попал бы в frame locals).
        # Переменные-ключи не держим в текущем frame
        from django.conf import settings as conf
        from django.views.debug import ExceptionReporter
        original_key = conf.YANDEX_API_KEY
        original_folder = conf.YANDEX_FOLDER_ID
        original_debug = conf.DEBUG
        conf.YANDEX_API_KEY = 'test-key-ABC123'
        conf.YANDEX_FOLDER_ID = 'test-folder'
        conf.DEBUG = debug
        try:
            exc_info = _raise_yandex_with_fake_transport(
                ConnectionError('upstream unreachable')
            )
            self.assertIsNotNone(exc_info)
            return ExceptionReporter(None, *exc_info).get_traceback_html()
        finally:
            conf.YANDEX_API_KEY = original_key
            conf.YANDEX_FOLDER_ID = original_folder
            conf.DEBUG = original_debug

    def test_key_absent_from_traceback_html_in_debug_true(self):
        html = self._render_exception(debug=True)
        self.assertNotIn('test-key-ABC123', html)

    def test_key_absent_from_traceback_html_in_debug_false(self):
        html = self._render_exception(debug=False)
        self.assertNotIn('test-key-ABC123', html)

    def test_verify_true_and_allow_redirects_false(self):
        from django.conf import settings as conf
        original_key = conf.YANDEX_API_KEY
        original_folder = conf.YANDEX_FOLDER_ID
        conf.YANDEX_API_KEY = 'test-key-ABC123'
        conf.YANDEX_FOLDER_ID = 'test-folder'
        try:
            kwargs = _capture_verify_kwarg(ConnectionError('x'))
        finally:
            conf.YANDEX_API_KEY = original_key
            conf.YANDEX_FOLDER_ID = original_folder
        # Клиент не передаёт `verify=False` и не разрешает редиректы
        self.assertNotEqual(kwargs['verify'], False)
        self.assertTrue(kwargs['verify'] is True or kwargs['verify'] == 'MISSING' and False)
        self.assertEqual(kwargs['allow_redirects'], False)

    def test_from_none_breaks_exception_chain(self):
        """
        `raise YandexGPTError(...) from None`: `__cause__` и `__suppress_context__`.

        Мутация `from e` оставила бы `__context__` с оригиналом (где
        может быть ключ в заголовках или URL). `from None` его обрывает.
        """
        from django.conf import settings as conf
        original_key = conf.YANDEX_API_KEY
        original_folder = conf.YANDEX_FOLDER_ID
        conf.YANDEX_API_KEY = 'ANY-KEY'
        conf.YANDEX_FOLDER_ID = 'folder'
        try:
            exc_info = _raise_yandex_with_fake_transport(
                ConnectionError('upstream unreachable')
            )
        finally:
            conf.YANDEX_API_KEY = original_key
            conf.YANDEX_FOLDER_ID = original_folder
        self.assertIsNotNone(exc_info)
        _, exc, _tb = exc_info
        self.assertIsInstance(exc, YandexGPTError)
        self.assertIsNone(exc.__cause__)
        self.assertTrue(exc.__suppress_context__)


# =============================================================================
# Прочие обязательные тесты из плана
# =============================================================================


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000)
class ModelMenuChoicesTests(TestCase):
    """
    Меню «Модель»: закрытый список, пустое значение — Lite,
    `openai` / неизвестное / `yandexgpt` без ключа → 400 без вызова.
    """

    def test_rejects_openai_without_touching_any_client(self):
        client = _try_demo()
        with fake_gigachat() as giga, fake_yandexgpt(override_keys=False) as yandex:
            response = client.post('/generator/',
                                   dict(FORM, model='openai'), **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], MSG_MODEL_UNAVAILABLE)
        self.assertEqual((giga.invoke_calls, giga.chat_calls, yandex.calls), (0, 0, 0))

    def test_rejects_unknown_model(self):
        client = _try_demo()
        with fake_gigachat() as giga, fake_yandexgpt(override_keys=False) as yandex:
            response = client.post('/generator/',
                                   dict(FORM, model='invalid-model'), **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertEqual((giga.invoke_calls, giga.chat_calls, yandex.calls), (0, 0, 0))

    @override_settings(YANDEX_API_KEY='', YANDEX_FOLDER_ID='')
    def test_rejects_yandexgpt_when_key_absent(self):
        client = _try_demo()
        with fake_gigachat() as giga, fake_yandexgpt(override_keys=False) as yandex:
            response = client.post('/generator/',
                                   dict(FORM, model=MODEL_YANDEXGPT), **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], MSG_YANDEX_NOT_CONFIGURED)
        self.assertEqual((giga.invoke_calls, giga.chat_calls, yandex.calls), (0, 0, 0))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000)
class GeneratorTemplateMenuTests(TestCase):
    """Разметка: без ключа YandexGPT пункт отсутствует; `generator_type` снят"""

    def test_generator_type_not_in_markup(self):
        client = _try_demo()
        response = client.get('/generator/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('name="generator_type"', html)

    @override_settings(YANDEX_API_KEY='', YANDEX_FOLDER_ID='')
    def test_yandex_hidden_without_key(self):
        client = _try_demo()
        response = client.get('/generator/')
        html = response.content.decode('utf-8')
        self.assertNotIn('>YandexGPT<', html)
        # Lite и Pro в меню — есть
        self.assertIn('>GigaChat Lite<', html)
        self.assertIn('>GigaChat Pro<', html)

    @override_settings(YANDEX_API_KEY='test-key', YANDEX_FOLDER_ID='test-folder')
    def test_yandex_visible_with_key(self):
        client = _try_demo()
        response = client.get('/generator/')
        html = response.content.decode('utf-8')
        self.assertIn('>YandexGPT<', html)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000)
class SingleTextPathTests(TestCase):
    """
    Один путь текста: тот же системный промпт и то же сообщение
    пользователя уходят во все три модели (Lite, Pro, YandexGPT)
    """

    def test_same_prompt_and_message_across_three_models(self):
        prompts = {}
        for model_code in (MODEL_GIGACHAT_LITE, MODEL_GIGACHAT_PRO, MODEL_YANDEXGPT):
            client = _try_demo(remote_addr=f'127.0.0.{len(prompts)+1}')
            with fake_gigachat() as giga, fake_yandexgpt() as yandex:
                response = client.post('/generator/',
                                       dict(FORM, model=model_code), **AJAX)
            self.assertEqual(response.status_code, 200, (model_code, response.content))
            if model_code == MODEL_YANDEXGPT:
                self.assertEqual(yandex.calls, 1)
                system_prompt, user_message = yandex.messages[0]
            else:
                self.assertEqual(giga.invoke_calls, 1)
                msgs = giga.invoke_messages[0]
                system_prompt = msgs[0].content
                user_message = msgs[1].content
            prompts[model_code] = (system_prompt, user_message)
        # Все три модели получают один и тот же промпт и сообщение
        values = list(prompts.values())
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[0], values[2])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000)
class ProviderCeilingsAreSeparateTests(TestCase):
    """
    При исчерпанном потолке YandexGPT — GigaChat работает, и наоборот.
    Pro упирается и в `GIGACHAT_PRO_DAILY_CALL_LIMIT`, и в общий
    `GIGACHAT_DAILY_CALL_LIMIT`.
    """

    @override_settings(YANDEX_DAILY_CALL_LIMIT=0, GIGACHAT_DAILY_CALL_LIMIT=50,
                       YANDEX_API_KEY='k', YANDEX_FOLDER_ID='f')
    def test_yandex_blocked_gigachat_works(self):
        client = _try_demo()
        # YandexGPT — 429
        with fake_gigachat() as giga, fake_yandexgpt() as yandex:
            yandex_response = client.post('/generator/',
                                          dict(FORM, model=MODEL_YANDEXGPT), **AJAX)
            gigachat_response = client.post('/generator/',
                                            dict(FORM, model=MODEL_GIGACHAT_LITE), **AJAX)
        self.assertEqual(yandex_response.status_code, 429)
        self.assertEqual(yandex.calls, 0)
        self.assertEqual(gigachat_response.status_code, 200)
        self.assertEqual(giga.invoke_calls, 1)

    @override_settings(YANDEX_DAILY_CALL_LIMIT=50, GIGACHAT_DAILY_CALL_LIMIT=0,
                       YANDEX_API_KEY='k', YANDEX_FOLDER_ID='f')
    def test_gigachat_blocked_yandex_works(self):
        client = _try_demo()
        with fake_gigachat() as giga, fake_yandexgpt() as yandex:
            gigachat_response = client.post('/generator/',
                                            dict(FORM, model=MODEL_GIGACHAT_LITE), **AJAX)
            yandex_response = client.post('/generator/',
                                          dict(FORM, model=MODEL_YANDEXGPT), **AJAX)
        self.assertEqual(gigachat_response.status_code, 429)
        self.assertEqual(giga.invoke_calls, 0)
        self.assertEqual(yandex_response.status_code, 200)
        self.assertEqual(yandex.calls, 1)

    def test_pro_hits_both_ceilings(self):
        # Сначала потолок Pro
        with override_settings(GIGACHAT_PRO_DAILY_CALL_LIMIT=0,
                               GIGACHAT_DAILY_CALL_LIMIT=50):
            result = check_provider_ceiling(PROVIDER_GIGACHAT_PRO)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], MSG_DAILY_LIMIT_GIGACHAT_PRO)
        # Теперь общий GigaChat (Pro — тоже GigaChat, попадает в общий)
        with override_settings(GIGACHAT_PRO_DAILY_CALL_LIMIT=50,
                               GIGACHAT_DAILY_CALL_LIMIT=0):
            result = check_provider_ceiling(PROVIDER_GIGACHAT_PRO)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], MSG_DAILY_LIMIT)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000,
                   YANDEX_API_KEY='k', YANDEX_FOLDER_ID='f')
class RegenerationGoesToSameModelTests(TestCase):
    """Перегенерация идёт в ту же модель, что первая генерация"""

    def test_regenerate_follows_last_model(self):
        client = _try_demo()
        with fake_yandexgpt() as yandex, fake_gigachat() as giga:
            response = client.post('/generator/',
                                   dict(FORM, model=MODEL_YANDEXGPT), **AJAX)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(yandex.calls, 1)
            response = client.post('/regenerate-text/', **AJAX)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(yandex.calls, 2)
            # GigaChat вообще не трогался
            self.assertEqual(giga.invoke_calls, 0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000,
                   YANDEX_API_KEY='k', YANDEX_FOLDER_ID='f')
class ImageAlwaysGigaChatTests(TestCase):
    """Картинка идёт всегда в GigaChat, даже если текст делал YandexGPT"""

    def test_image_uses_gigachat_when_text_is_yandex(self):
        client = _try_demo()
        with fake_yandexgpt() as yandex, fake_gigachat() as giga:
            response = client.post(
                '/generator/',
                dict(FORM, model=MODEL_YANDEXGPT, generate_image='on'),
                **AJAX,
            )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        # YandexGPT вызван один раз — текст
        self.assertEqual(yandex.calls, 1)
        # GigaChat получил промпт картинки и собственно картинку
        self.assertEqual(giga.invoke_calls, 1)  # промпт
        self.assertEqual(giga.chat_calls, 1)    # картинка


# =============================================================================
# Мутации (явно описано в плане)
# =============================================================================


class ProviderCeilingMutationsTests(TestCase):
    """
    Мутации обобщённого потолка — каждая должна ронять тест.
    Мутации в памяти через `patch.object`.
    """

    def test_remove_yandex_ceiling_check_lets_calls_through(self):
        """Снять проверку потолка YandexGPT → ceiling вернёт None, тест ронит"""
        from generator import access as _access
        # Прямая проверка: при потолке 0 функция сейчас возвращает (msg, 429).
        # Мутация — убрать branch провайдера yandexgpt. Проверяем, что без
        # мутации — None уйдёт только когда ресурс есть
        with override_settings(YANDEX_DAILY_CALL_LIMIT=0):
            result = _access.check_provider_ceiling(PROVIDER_YANDEXGPT)
            self.assertIsNotNone(result,
                                 'Если мутация убрала проверку YandexGPT — '
                                 'тест ронит её здесь')

    def test_yandex_logging_writes_provider_field(self):
        """
        Мутация: не писать `provider`/`model_code` → строка попадёт в учёт
        с пустым provider, не попадёт в общий потолок YandexGPT; тест ронит
        """
        from generator.gigachat_api import log_token_usage
        log_token_usage(
            operation_type='TEXT_GENERATION',
            prompt_text='prompt',
            response_text='response',
            provider=PROVIDER_YANDEXGPT,
            model_code=PROVIDER_YANDEXGPT,
        )
        entry = GigaChatTokenUsage.objects.get()
        self.assertEqual(entry.provider, PROVIDER_YANDEXGPT)
        self.assertEqual(entry.model_code, PROVIDER_YANDEXGPT)


class ProviderConstantsAreClosedListTests(TestCase):
    """
    Константы провайдера — ровно 3 строки, короткие (замечание 2)
    """

    def test_three_codes_exactly(self):
        from generator.models import GigaChatTokenUsage
        codes = [code for code, _label in GigaChatTokenUsage.PROVIDER_CHOICES]
        self.assertEqual(sorted(codes),
                         ['gigachat-lite', 'gigachat-pro', 'yandexgpt'])
        # Короткие — не длиннее max_length
        max_length = GigaChatTokenUsage._meta.get_field('provider').max_length
        for code in codes:
            self.assertLessEqual(len(code), max_length)

    def test_access_and_models_share_the_same_constants(self):
        from generator import access as _access
        from generator.models import GigaChatTokenUsage
        self.assertEqual(_access.PROVIDER_GIGACHAT_LITE,
                         GigaChatTokenUsage.PROVIDER_GIGACHAT_LITE)
        self.assertEqual(_access.PROVIDER_GIGACHAT_PRO,
                         GigaChatTokenUsage.PROVIDER_GIGACHAT_PRO)
        self.assertEqual(_access.PROVIDER_YANDEXGPT,
                         GigaChatTokenUsage.PROVIDER_YANDEXGPT)


# =============================================================================
# Раунд исправлений 2а.2 (2026-11-03) — три замечания повторного ревью
# =============================================================================


class LoadDotenvAbsentInAllGeneratorModulesTests(TestCase):
    """
    Раунд исправлений, замечание 1: `load_dotenv()` остался в
    `generator/yandex_image_api.py` и `generator/fastapi_client.py` —
    замечание 4 ревью безопасности было закрыто не полностью. Эти файлы
    импортируются из `generator/views.py` при старте Django и вызывали
    `load_dotenv()` без аргумента пути (ищет `.env` вверх по дереву).

    Критерий: единственный `load_dotenv(` во всём `generator/` и
    `ghostwriter/` — вызов в `ghostwriter/settings.py`.
    """

    def test_yandex_image_api_reload_does_not_call_load_dotenv(self):
        from generator import yandex_image_api
        with patch('dotenv.load_dotenv') as mock_load:
            importlib.reload(yandex_image_api)
        mock_load.assert_not_called()

    def test_fastapi_client_reload_does_not_call_load_dotenv(self):
        from generator import fastapi_client
        with patch('dotenv.load_dotenv') as mock_load:
            importlib.reload(fastapi_client)
        mock_load.assert_not_called()

    def test_grep_single_load_dotenv_in_project(self):
        """
        Единственный `load_dotenv(` в коде — `ghostwriter/settings.py`.
        Строки в комментариях (начинаются с `#`) и в тестах не считаются.

        Мутация «вернуть `load_dotenv()` в `yandex_image_api.py` или
        `fastapi_client.py`» → тест ронит.
        """
        from pathlib import Path
        from django.conf import settings as conf
        base = Path(conf.BASE_DIR)
        checked = []
        offenders = []
        for subdir in ('generator', 'ghostwriter'):
            for path in (base / subdir).rglob('*.py'):
                if '__pycache__' in path.parts:
                    continue
                text = path.read_text(encoding='utf-8')
                checked.append(path)
                for line in text.splitlines():
                    stripped = line.lstrip()
                    if stripped.startswith('#'):
                        continue
                    if 'load_dotenv(' in line:
                        offenders.append((path, line.strip()))
        self.assertTrue(checked)  # защита от «ничего не нашлось»
        # Разрешён ровно один файл: ghostwriter/settings.py
        allowed = base / 'ghostwriter' / 'settings.py'
        offender_paths = {str(p) for p, _ in offenders}
        self.assertEqual(offender_paths, {str(allowed)},
                         f'`load_dotenv(` вне settings.py: {offenders}')

    def test_no_dotenv_import_outside_settings(self):
        """
        `from dotenv import load_dotenv` — ровно в одном файле
        (`ghostwriter/settings.py`). В остальных Python-модулях этого
        импорта нет (ни `from dotenv`, ни `import dotenv`).
        """
        from pathlib import Path
        from django.conf import settings as conf
        base = Path(conf.BASE_DIR)
        allowed = base / 'ghostwriter' / 'settings.py'
        offenders = []
        for subdir in ('generator', 'ghostwriter'):
            for path in (base / subdir).rglob('*.py'):
                if '__pycache__' in path.parts or path == allowed:
                    continue
                text = path.read_text(encoding='utf-8')
                for line in text.splitlines():
                    stripped = line.lstrip()
                    if stripped.startswith('#'):
                        continue
                    if 'from dotenv' in line or stripped.startswith('import dotenv'):
                        offenders.append((path, line.strip()))
        self.assertFalse(offenders,
                         f'Импорт `dotenv` вне settings.py: {offenders}')


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    DEMO_TOKENS_PER_IP_PER_DAY=1000,
    GIGACHAT_DAILY_CALL_LIMIT=1,
    YANDEX_DAILY_CALL_LIMIT=50,
    YANDEX_API_KEY='test-key',
    YANDEX_FOLDER_ID='test-folder',
)
class GigaChatCeilingReCheckedBeforeImageTests(TestCase):
    """
    Раунд исправлений, замечание 2: `check_provider_ceiling` должен
    проверяться перед **каждым** звеном цепочки картинки, не только
    один раз на входе в блок. При `GIGACHAT_DAILY_CALL_LIMIT=1` и
    `model=yandexgpt+image=on`: промпт картинки создаёт первую строку
    GigaChat → ceiling (count=1 >= 1) должен остановить вторую.
    Без повторной проверки картинка проходит → count=2 (перерасход на 1).

    Мутация: убрать повторный `check_provider_ceiling` перед
    `generate_image_gigachat` → `giga.chat_calls=1`, count GigaChat=2;
    тест ронит.
    """

    def test_overrun_blocked_by_second_ceiling_check(self):
        client = _try_demo()
        GigaChatTokenUsage.objects.all().delete()
        with fake_gigachat() as giga, fake_yandexgpt() as yandex:
            response = client.post(
                '/generator/',
                dict(FORM, model=MODEL_YANDEXGPT, generate_image='on'),
                **AJAX,
            )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'], data)
        # YandexGPT — текст (один вызов)
        self.assertEqual(yandex.calls, 1)
        # GigaChat: промпт картинки состоялся (invoke=1), сама картинка — нет
        self.assertEqual(giga.invoke_calls, 1,
                         'Промпт картинки был записан — count GigaChat=1')
        self.assertEqual(giga.chat_calls, 0,
                         'Картинка должна быть остановлена вторым '
                         'check_provider_ceiling (замечание 2 раунда 1)')
        # В учёте — ровно 1 строка GigaChat (промпт), не 2
        gigachat_rows = GigaChatTokenUsage.objects.filter(
            provider__in=[PROVIDER_GIGACHAT_LITE, PROVIDER_GIGACHAT_PRO]
        ).count()
        self.assertEqual(gigachat_rows, 1,
                         'Перерасход потолка GigaChat на 1 вызов — '
                         'ровно та дыра, которую закрывает повторная проверка')
        # В ответе — пометка про лимит картинки
        self.assertIsNone(data['image_url'])
        self.assertEqual(data['image_error'], MSG_DAILY_LIMIT)


class LogTokenUsageProviderRequiredTests(TestCase):
    """
    Раунд исправлений, замечание 3: хрупкий `_PROVIDER_DEFAULT='gigachat-lite'`
    убран. `log_token_usage(..., provider=...)` — обязательный keyword-only
    параметр. Значение не из закрытого списка → `logger.error` + return,
    строка `GigaChatTokenUsage` не создана.

    Мутация: вернуть `_PROVIDER_DEFAULT='gigachat-lite'` и
    `provider or _PROVIDER_DEFAULT` → первый тест ронит (TypeError не
    бросается), второй тоже (строка создастся как gigachat-lite).
    """

    def test_call_without_provider_raises_type_error(self):
        from generator.gigachat_api import log_token_usage
        with self.assertRaises(TypeError):
            # Без keyword-only `provider` — TypeError из CPython
            log_token_usage('TEXT_GENERATION', 'prompt', 'response')
        self.assertEqual(GigaChatTokenUsage.objects.count(), 0,
                         'TypeError должен быть брошен до создания строки')

    def test_call_with_invalid_provider_logs_error_and_skips_row(self):
        from generator.gigachat_api import log_token_usage
        import logging as _logging
        with self.assertLogs('generator.gigachat_api', level=_logging.ERROR) as cm:
            log_token_usage(
                'TEXT_GENERATION', 'prompt', 'response',
                provider='openai',  # не из закрытого списка
            )
        self.assertEqual(GigaChatTokenUsage.objects.count(), 0,
                         'Невалидный provider не должен создавать строку')
        self.assertTrue(any('openai' in msg for msg in cm.output),
                        f'logger.error должен назвать невалидный код: {cm.output}')

    def test_call_with_none_provider_logs_error_and_skips_row(self):
        from generator.gigachat_api import log_token_usage
        import logging as _logging
        with self.assertLogs('generator.gigachat_api', level=_logging.ERROR):
            log_token_usage(
                'TEXT_GENERATION', 'prompt', 'response',
                provider=None,
            )
        self.assertEqual(GigaChatTokenUsage.objects.count(), 0)

    def test_valid_provider_still_writes_row(self):
        """
        Проверка, что защита не сломала штатные вызовы: с валидным
        `provider` строка пишется, как раньше
        """
        from generator.gigachat_api import log_token_usage
        log_token_usage(
            'TEXT_GENERATION', 'prompt', 'response',
            provider=PROVIDER_YANDEXGPT,
        )
        row = GigaChatTokenUsage.objects.get()
        self.assertEqual(row.provider, PROVIDER_YANDEXGPT)
        self.assertEqual(row.model_code, PROVIDER_YANDEXGPT)

    def test_provider_default_constant_removed(self):
        """
        Мутация-sentinel: имя `_PROVIDER_DEFAULT` в модуле отсутствует.
        Возврат константы для fallback-а ронит этот тест.
        """
        from generator import gigachat_api
        self.assertFalse(hasattr(gigachat_api, '_PROVIDER_DEFAULT'),
                         'Хрупкий дефолт провайдера должен быть убран')
