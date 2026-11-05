"""
Вспомогательный код тестов

- TokenAuthMixin: вход по токену доступа тем же путём, что и пользователь —
  TemporaryAccessToken и /auth/token/<uuid>/ (token_auth_view);
- FakeGigaChat и fake_gigachat: клиенты GigaChat без сети, со счётчиком
  обращений; настоящий код gigachat_api (проверки, учёт) при этом работает;
- postgres_varchar_lengths: проверка длины строк, как в PostgreSQL.
"""

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.db import DataError
from django.db.models import CharField

from generator.models import TemporaryAccessToken
from generator.tariffs import get_tariff_config


class TokenAuthMixin:
    """Вход тестового клиента по токену доступа (для django.test.TestCase)"""

    def login_by_token(self, telegram_user_id, token_type='DEMO_FREE'):
        """
        Создаёт токен с лимитами тарифа и входит по нему через /auth/token/<uuid>/

        token_auth_view создаёт пользователя Django tg_<telegram_user_id>
        и выполняет вход. Возвращает (token, user).
        """
        tariff = get_tariff_config(token_type)
        token = TemporaryAccessToken.objects.create(
            token_type=token_type,
            gigachat_tokens_limit=tariff['gigachat_tokens'],
            openai_tokens_limit=tariff['openai_tokens'],
            telegram_user_id=telegram_user_id,
        )

        response = self.client.get(f'/auth/token/{token.token}/')
        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['access_token'], str(token.token))

        user = User.objects.get(username=f'tg_{telegram_user_id}')
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        return token, user


def register_and_login(client, username='demo_owner_test',
                       password='StrongDemoPwd_7Qx1', terms_accepted=True):
    """
    Регистрация + вход через `/register/` (фаза 3).

    После POST'а на `/register/` при валидной форме view сам вызывает
    `django.contrib.auth.login` (смена ключа сессии встроена). Возвращает
    `(response, user)` — у `response` можно проверять `redirect_chain`,
    статус и сессию.
    """
    data = {
        'username': username,
        'password1': password,
        'password2': password,
    }
    if terms_accepted:
        data['terms_accepted'] = 'on'
    response = client.post('/register/', data)
    user = User.objects.filter(username=username).first()
    return response, user


class FakeGigaChat:
    """
    Клиент GigaChat без сети: отвечает как настоящий и считает обращения

    Один объект подменяет оба клиента:
    - _init_client() → invoke(messages): текст и промпт картинки, у ответа
      читается .content;
    - _init_direct_client() → chat(payload): картинка. Ответ — <img src="...">,
      его разбирает extract_image_id, а download_image скачивает через get_image.

    Обращения к GigaChat — вызовы invoke и chat; get_image только скачивает
    уже готовую картинку. Сообщения каждого invoke сохраняются в
    invoke_messages: по ним тесты видят, что ушло бы в GigaChat.
    """

    TEXT = 'Сгенерированный пост про кофейню'
    FILE_ID = '3f2b8c1e-6a4d-4e5f-9b7a-1c2d3e4f5a6b'
    IMAGE_BYTES = b'\xff\xd8\xff\xe0fake-jpeg'

    def __init__(self):
        self.invoke_calls = 0
        self.chat_calls = 0
        self.invoke_messages = []

    @property
    def calls(self):
        return self.invoke_calls + self.chat_calls

    def invoke(self, messages):
        self.invoke_calls += 1
        self.invoke_messages.append(list(messages))
        return SimpleNamespace(content=self.TEXT)

    def chat(self, payload):
        self.chat_calls += 1
        message = SimpleNamespace(content=f'<img src="{self.FILE_ID}" fuse="true"/>')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def get_image(self, file_id):
        return SimpleNamespace(content=self.IMAGE_BYTES)


@contextmanager
def fake_gigachat():
    """
    Подменяет клиенты GigaChat фейком и отдаёт его

    Перекрывает предохранитель раннера. Паузы перед картинкой (time.sleep
    в gigachat_api и views — это один модуль time) не ждут.
    """
    fake = FakeGigaChat()
    with ExitStack() as stack:
        # `_init_client(model=...)` вызывается с кварг — надо игнорировать
        stack.enter_context(patch('generator.gigachat_api._init_client',
                                  side_effect=lambda *a, **kw: fake))
        stack.enter_context(patch('generator.gigachat_api._init_direct_client', return_value=fake))
        stack.enter_context(patch('generator.gigachat_api.time.sleep'))
        yield fake


class FakeYandexGPT:
    """
    Клиент YandexGPT без сети: отвечает как настоящий и считает обращения

    Один фейк подменяет `_call_completion` в `yandexgpt_api`: функция
    получает `system_prompt` и `user_message` и возвращает текст. Сообщения
    (system/user) каждого вызова сохраняются в `.messages` — по ним тесты
    видят, что ушло бы в YandexGPT (сравнение с FakeGigaChat.invoke_messages).

    Атрибуты (контракт того же вида, что у FakeGigaChat):
    - `.calls` — число вызовов текстового клиента;
    - `.messages` — список `[(system_prompt, user_message), ...]`.
    """

    TEXT = 'Сгенерированный пост про кофейню (yandex)'

    def __init__(self, response_text=None):
        self.calls = 0
        self.messages = []
        self.response_text = response_text if response_text is not None else self.TEXT

    def __call__(self, system_prompt, user_message, **kwargs):
        self.calls += 1
        self.messages.append((system_prompt, user_message))
        return self.response_text


@contextmanager
def fake_yandexgpt(response_text=None, override_keys=True):
    """
    Подменяет HTTP-клиент YandexGPT фейком и отдаёт его

    Параметры:
      response_text: ответ фейка (по умолчанию `FakeYandexGPT.TEXT`);
      override_keys: подставить фиктивные `YANDEX_API_KEY` и `YANDEX_FOLDER_ID`
        на время теста (иначе проверка в `generate_text_yandex` отдаст 400
        «ключ не настроен» до фейка).
    """
    from django.test import override_settings
    fake = FakeYandexGPT(response_text=response_text)
    with ExitStack() as stack:
        if override_keys:
            stack.enter_context(override_settings(
                YANDEX_API_KEY='test-yandex-key',
                YANDEX_FOLDER_ID='test-folder-id',
            ))
        stack.enter_context(patch('generator.yandexgpt_api._call_completion', side_effect=fake))
        yield fake


@contextmanager
def postgres_varchar_lengths(model):
    """
    Запись строки длиннее max_length CharField падает с DataError, как в PostgreSQL

    SQLite длину varchar не проверяет, поэтому без этого тесты не видят,
    что запись в продакшене упадёт.
    """
    original_save = model.save

    def save(instance, *args, **kwargs):
        for field in instance._meta.concrete_fields:
            if isinstance(field, CharField) and field.max_length:
                value = getattr(instance, field.attname)
                if value is not None and len(str(value)) > field.max_length:
                    raise DataError(
                        f'value too long for type character varying({field.max_length})'
                    )
        return original_save(instance, *args, **kwargs)

    with patch.object(model, 'save', save):
        yield
