"""
Тесты фазы 1: демо-доступ «Попробовать» и защита генерации

Проверяют:
- сценарий лендинг → «Попробовать» → генератор → пост;
- выдачу демо-токенов: один на сессию, не больше N на IP в сутки;
- определение IP клиента без доверия к X-Forwarded-For;
- снятые маршруты бота, оплаты и API токенов;
- единую проверку перед каждым вызовом GigaChat;
- учёт каждого вызова GigaChat и списание без потерянных обновлений;
- CSRF на «Попробовать» и на эндпоинтах генерации.

GigaChat везде замокан; без мока раннер бросает NetworkAccessBlocked.
Тесты учёта мокают клиент (tests.helpers.fake_gigachat), чтобы работал
настоящий код gigachat_api.
"""

import base64
import json
import tempfile
import uuid
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import get_resolver, resolve, reverse
from django.utils import timezone

from generator.access import check_gigachat_access
from generator.gigachat_api import (
    generate_image_gigachat,
    generate_image_prompt_from_text,
    generate_text,
    log_token_usage,
)
from generator.models import GigaChatTokenUsage, TemporaryAccessToken
from tests.helpers import FakeGigaChat, fake_gigachat, postgres_varchar_lengths

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

TOPIC = 'Кофейня у дома: новый сезонный напиток'

# Эндпоинты генерации и данные запроса, с которыми они доходят до GigaChat
GENERATION_ENDPOINTS = {
    '/generator/': {'topic': TOPIC},
    '/regenerate-text/': {'topic': TOPIC},
    '/generate-image-from-text/': {'topic': TOPIC, 'result_text': 'Готовый пост про кофейню'},
    '/regenerate-image/': {'topic': TOPIC},
}

# Функции GigaChat: и имена, импортированные в views, и сам модуль API
GIGACHAT_TARGETS = (
    'generator.views.generate_text',
    'generator.views.generate_image_gigachat',
    'generator.gigachat_api.generate_text',
    'generator.gigachat_api.generate_image_prompt_from_text',
    'generator.gigachat_api.generate_image_gigachat',
)


@contextmanager
def gigachat_mocks():
    """Мокает все входы в GigaChat и паузу перед картинкой; отдаёт список моков"""
    with ExitStack() as stack:
        mocks = [stack.enter_context(patch(target)) for target in GIGACHAT_TARGETS]
        for mock in mocks:
            mock.return_value = 'https://example.com/image.jpg'
        mocks[0].return_value = 'Готовый пост'
        mocks[3].return_value = 'Промпт для картинки'
        stack.enter_context(patch('generator.views.time.sleep'))
        yield mocks


def gigachat_called(mocks):
    return any(mock.called for mock in mocks)


def demo_token_of(client):
    """Токен из сессии клиента"""
    return TemporaryAccessToken.objects.get(token=client.session['access_token'])


def try_demo(remote_addr='127.0.0.1', **extra):
    """Новый клиент без cookies нажимает «Попробовать»; возвращает (client, response)"""
    client = Client()
    response = client.post('/try/', REMOTE_ADDR=remote_addr, **extra)
    return client, response


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TryDemoFlowTests(TestCase):
    """Сценарий «Попробовать» и свойства демо-токена"""

    def test_landing_try_generator_post(self):
        """Лендинг → POST «Попробовать» → генератор → AJAX-генерация с success: true"""
        client = Client(enforce_csrf_checks=True)

        response = client.get('/')
        self.assertContains(response, 'action="/try/"')
        csrf = client.cookies['csrftoken'].value

        response = client.post('/try/', {'csrfmiddlewaretoken': csrf})
        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)

        response = client.get('/generator/')
        self.assertEqual(response.status_code, 200)

        with patch('generator.views.generate_text', return_value='Готовый пост про кофейню') as mock_text:
            response = client.post(
                '/generator/',
                {'topic': TOPIC, 'csrfmiddlewaretoken': csrf},
                **AJAX,
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['result'], 'Готовый пост про кофейню')
        mock_text.assert_called_once()

    def test_try_button_on_token_required_page(self):
        """На странице требования токена — POST-форма «Попробовать» с CSRF"""
        response = self.client.get('/token-required/')
        self.assertContains(response, 'action="/try/"')
        self.assertContains(response, 'csrfmiddlewaretoken')

    @override_settings(DEMO_GIGACHAT_TOKENS_LIMIT=12345)
    def test_demo_token_fields(self):
        """Демо-токен: DEMO_FREE без Telegram, без OpenAI, 24 часа, лимит GigaChat из настроек"""
        before = timezone.now()
        client, response = try_demo()
        after = timezone.now()

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        token = TemporaryAccessToken.objects.get()
        self.assertEqual(token.token_type, 'DEMO_FREE')
        self.assertIsNone(token.telegram_user_id)
        self.assertEqual(token.openai_tokens_limit, 0)
        self.assertEqual(token.gigachat_tokens_limit, 12345)
        self.assertEqual(token.gigachat_tokens_used, 0)
        self.assertTrue(token.is_active)
        self.assertGreaterEqual(token.expires_at, before + timedelta(hours=24))
        self.assertLessEqual(token.expires_at, after + timedelta(hours=24))

        session = client.session
        self.assertEqual(session['access_token'], str(token.token))
        self.assertEqual(session['token_type'], 'DEMO_FREE')
        self.assertTrue(session['is_demo'])
        self.assertNotIn(SESSION_KEY, session)

    def test_repeat_try_with_live_token(self):
        """Повторное «Попробовать» с живым токеном ведёт в генератор без нового токена"""
        client, _ = try_demo()
        token = demo_token_of(client)

        response = client.post('/try/')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(TemporaryAccessToken.objects.count(), 1)
        self.assertEqual(client.session['access_token'], str(token.token))

    def test_repeat_try_with_exhausted_token(self):
        """Исчерпанный, но действующий токен не заменяется новым: лимит не сбросить"""
        client, _ = try_demo()
        token = demo_token_of(client)
        token.gigachat_tokens_used = token.gigachat_tokens_limit
        token.save()

        response = client.post('/try/')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(TemporaryAccessToken.objects.count(), 1)

    def test_try_after_expired_token(self):
        """Истёкший токен в сессии — выдаётся новый"""
        client, _ = try_demo()
        old = demo_token_of(client)
        old.expires_at = timezone.now() - timedelta(minutes=1)
        old.save()

        response = client.post('/try/')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(TemporaryAccessToken.objects.count(), 2)
        self.assertNotEqual(client.session['access_token'], str(old.token))

    def test_try_get_redirects_to_landing(self):
        """GET на «Попробовать» токен не выдаёт"""
        response = self.client.get('/try/')

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertEqual(TemporaryAccessToken.objects.count(), 0)


@override_settings(DEMO_TOKENS_PER_IP_PER_DAY=3, BEHIND_PROXY=False)
class DemoTokenIpLimitTests(TestCase):
    """Не больше N демо-токенов с одного IP за 24 часа"""

    def assert_ip_limit_reached(self, response):
        self.assertContains(response, 'Лимит демо-доступа', status_code=429)

    def test_limit_for_new_clients_from_one_ip(self):
        """Новые клиенты без cookies с одного IP сверх N токен не получают"""
        for _ in range(3):
            _, response = try_demo('203.0.113.5')
            self.assertRedirects(response, '/generator/', fetch_redirect_response=False)

        client, response = try_demo('203.0.113.5')

        self.assert_ip_limit_reached(response)
        self.assertEqual(TemporaryAccessToken.objects.count(), 3)
        self.assertNotIn('access_token', client.session)

    def test_other_ip_not_affected(self):
        """Лимит одного IP не мешает другому"""
        for _ in range(3):
            try_demo('203.0.113.5')

        _, response = try_demo('203.0.113.6')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(TemporaryAccessToken.objects.count(), 4)

    def test_forwarded_for_ignored_without_proxy(self):
        """Без прокси разные X-Forwarded-For при одном REMOTE_ADDR — один IP"""
        for i in range(3):
            try_demo('203.0.113.5', HTTP_X_FORWARDED_FOR=f'198.51.100.{i}')

        _, response = try_demo('203.0.113.5', HTTP_X_FORWARDED_FOR='198.51.100.99')

        self.assert_ip_limit_reached(response)
        self.assertEqual(TemporaryAccessToken.objects.count(), 3)

    @override_settings(BEHIND_PROXY=True)
    def test_behind_proxy_one_real_ip(self):
        """За прокси один X-Real-IP с разными X-Forwarded-For — один IP"""
        for i in range(3):
            try_demo('172.18.0.5', HTTP_X_REAL_IP='198.51.100.7',
                     HTTP_X_FORWARDED_FOR=f'10.0.0.{i}')

        _, response = try_demo('172.18.0.5', HTTP_X_REAL_IP='198.51.100.7',
                               HTTP_X_FORWARDED_FOR='10.0.0.99')

        self.assert_ip_limit_reached(response)
        self.assertEqual(TemporaryAccessToken.objects.count(), 3)

    @override_settings(BEHIND_PROXY=True)
    def test_behind_proxy_counts_real_ip_not_proxy(self):
        """За прокси счётчик идёт по X-Real-IP, а не по адресу прокси"""
        for i in range(4):
            _, response = try_demo('172.18.0.5', HTTP_X_REAL_IP=f'198.51.100.{i}')
            self.assertRedirects(response, '/generator/', fetch_redirect_response=False)

        self.assertEqual(TemporaryAccessToken.objects.count(), 4)

    def test_ip_stored_only_as_hash(self):
        """Счётчик выдачи хранит HMAC-хэш IP, а не сам IP"""
        from generator.models import AccessEvent

        try_demo('203.0.113.5')
        try_demo('203.0.113.6')

        events = list(AccessEvent.objects.order_by('created_at'))
        self.assertEqual(len(events), 2)
        for event, ip in zip(events, ('203.0.113.5', '203.0.113.6')):
            self.assertEqual(len(event.ip_hash), 64)
            for field in AccessEvent._meta.fields:
                self.assertNotIn(ip, str(getattr(event, field.attname)))
        self.assertNotEqual(events[0].ip_hash, events[1].ip_hash)

    def test_old_events_not_counted_and_removed(self):
        """Выдачи старше суток не считаются и удаляются при новой записи"""
        from generator.models import AccessEvent

        for _ in range(3):
            try_demo('203.0.113.5')
        AccessEvent.objects.update(created_at=timezone.now() - timedelta(hours=25))

        _, response = try_demo('203.0.113.5')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(AccessEvent.objects.count(), 1)


class ClientIpTests(TestCase):
    """Одна функция определения IP клиента"""

    def setUp(self):
        self.factory = RequestFactory()

    def client_ip(self, **meta):
        from generator.access import get_client_ip
        return get_client_ip(self.factory.get('/', **meta))

    @override_settings(BEHIND_PROXY=False)
    def test_without_proxy_remote_addr(self):
        ip = self.client_ip(REMOTE_ADDR='203.0.113.5',
                            HTTP_X_FORWARDED_FOR='198.51.100.1',
                            HTTP_X_REAL_IP='198.51.100.2')
        self.assertEqual(ip, '203.0.113.5')

    @override_settings(BEHIND_PROXY=True)
    def test_behind_proxy_x_real_ip(self):
        ip = self.client_ip(REMOTE_ADDR='172.18.0.5',
                            HTTP_X_FORWARDED_FOR='198.51.100.1',
                            HTTP_X_REAL_IP='198.51.100.2')
        self.assertEqual(ip, '198.51.100.2')

    @override_settings(BEHIND_PROXY=True)
    def test_behind_proxy_without_header_or_invalid(self):
        """Без X-Real-IP или с мусором в нём — REMOTE_ADDR (строже, а не мягче)"""
        self.assertEqual(self.client_ip(REMOTE_ADDR='172.18.0.5'), '172.18.0.5')
        self.assertEqual(self.client_ip(REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='не адрес'),
                         '172.18.0.5')

    @override_settings(BEHIND_PROXY=False)
    def test_decorators_get_client_ip_ignores_forwarded_for(self):
        """Прежний get_client_ip из decorators больше не верит X-Forwarded-For"""
        from generator.decorators import get_client_ip
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.5',
                                   HTTP_X_FORWARDED_FOR='198.51.100.1')
        self.assertEqual(get_client_ip(request), '203.0.113.5')


class RemovedRoutesTests(TestCase):
    """Маршруты бота, оплаты, поддержки и API токенов сняты"""

    REMOVED_URLS = (
        '/api/tokens/create/',
        f'/api/tokens/{uuid.uuid4()}/',
        '/api/track-subscription-click/',
        '/api/payments/create/',
        '/api/payments/yookassa/webhook/',
        '/api/payments/test-payment-id/confirm/',
        '/api/support/create/',
        '/api/reviews/create/',
        '/api/support/stats/',
        '/api/regenerate-text/',
        '/api/regenerate-image/',
        '/telegram/webhook/',
    )

    REMOVED_NAMES = (
        'api_create_token',
        'api_token_info',
        'api_track_subscription_click',
        'api_create_payment',
        'api_yookassa_webhook',
        'api_confirm_payment',
        'api_support_create',
        'api_reviews_create',
        'api_support_stats',
        'telegram_webhook',
    )

    def test_create_developer_token_404(self):
        """POST /api/tokens/create/ с DEVELOPER → 404, токен не создан"""
        response = self.client.post(
            '/api/tokens/create/',
            data='{"token_type": "DEVELOPER"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(TemporaryAccessToken.objects.count(), 0)

    def test_removed_urls_404(self):
        for url in self.REMOVED_URLS:
            for method in (self.client.get, self.client.post):
                with self.subTest(url=url, method=method.__name__):
                    self.assertEqual(method(url).status_code, 404)

    def test_removed_names_not_registered(self):
        """Имён снятых маршрутов нет в URLconf: {% url %} на них упал бы"""
        names = get_resolver().reverse_dict
        for name in self.REMOVED_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, names)

    def test_template_api_routes_kept(self):
        """Маршруты шаблонов под /api/ не тронуты (их переделает фаза 3)"""
        for url in ('/api/save-template/', '/api/get-templates/', '/api/load-template/',
                    '/api/delete-template/', '/api/rename-template/',
                    '/api/set-default-template/'):
            with self.subTest(url=url):
                resolve(url)

    def test_root_generation_routes_kept(self):
        for url in ('/regenerate-text/', '/regenerate-image/', '/generate-image-from-text/'):
            with self.subTest(url=url):
                resolve(url)


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    DEMO_TOKENS_PER_IP_PER_DAY=1000,
    DEMO_GIGACHAT_TOKENS_LIMIT=20000,
    GIGACHAT_DAILY_CALL_LIMIT=50,
    GENERATION_MAX_TOPIC_LENGTH=100,
    GENERATION_MAX_TEXT_LENGTH=300,
)
class GenerationGuardTests(TestCase):
    """Единая проверка перед вызовом GigaChat на всех четырёх эндпоинтах"""

    def post_each_endpoint(self, make_client, data_override=None, ajax=True):
        """
        Для каждого эндпоинта: свежий клиент, POST, ответ и были ли вызовы GigaChat
        """
        results = {}
        for url, data in GENERATION_ENDPOINTS.items():
            client = make_client()
            payload = dict(data, **(data_override or {}))
            with gigachat_mocks() as mocks:
                response = client.post(url, payload, **(AJAX if ajax else {}))
            results[url] = (response, gigachat_called(mocks))
        return results

    def assert_all_denied(self, results, status):
        for url, (response, called) in results.items():
            with self.subTest(url=url):
                self.assertFalse(called, 'GigaChat вызван при отказе')
                self.assertEqual(response.status_code, status)
                data = response.json()
                self.assertFalse(data['success'])
                self.assertTrue(data['error'])

    def demo_client(self):
        client, _ = try_demo()
        return client

    def test_allowed_reaches_gigachat(self):
        """Контроль: с живым токеном и коротким вводом GigaChat вызывается"""
        results = self.post_each_endpoint(self.demo_client)

        for url, (response, called) in results.items():
            with self.subTest(url=url):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'], response.json())
                self.assertTrue(called)

    def test_without_token(self):
        self.assert_all_denied(self.post_each_endpoint(Client), 403)

    def test_expired_token(self):
        def make_client():
            client = self.demo_client()
            token = demo_token_of(client)
            token.expires_at = timezone.now() - timedelta(minutes=1)
            token.save()
            return client

        self.assert_all_denied(self.post_each_endpoint(make_client), 403)

    def test_gigachat_limit_exhausted(self):
        def make_client():
            client = self.demo_client()
            token = demo_token_of(client)
            token.gigachat_tokens_used = token.gigachat_tokens_limit
            token.save()
            return client

        self.assert_all_denied(self.post_each_endpoint(make_client), 429)

    def test_gigachat_limit_exhausted_with_openai_left(self):
        """Остаток OpenAI не открывает GigaChat: лимиты не смешиваются"""
        def make_client():
            token = TemporaryAccessToken.objects.create(
                token_type='DEMO_FREE',
                gigachat_tokens_limit=1000,
                gigachat_tokens_used=1000,
                openai_tokens_limit=30000,
            )
            client = Client()
            client.get(f'/auth/token/{token.token}/')
            return client

        self.assert_all_denied(self.post_each_endpoint(make_client), 429)

    @override_settings(GIGACHAT_DAILY_CALL_LIMIT=2)
    def test_daily_ceiling_reached(self):
        for _ in range(2):
            GigaChatTokenUsage.objects.create(operation_type='TEXT_GENERATION')

        self.assert_all_denied(self.post_each_endpoint(self.demo_client), 429)

    @override_settings(GIGACHAT_DAILY_CALL_LIMIT=2)
    def test_daily_ceiling_counts_last_24_hours(self):
        """Вызовы старше суток в потолок не входят"""
        for _ in range(2):
            GigaChatTokenUsage.objects.create(operation_type='TEXT_GENERATION')
        GigaChatTokenUsage.objects.update(created_at=timezone.now() - timedelta(hours=25))

        client = self.demo_client()
        with gigachat_mocks() as mocks:
            response = client.post('/regenerate-text/', {'topic': TOPIC}, **AJAX)

        self.assertTrue(response.json()['success'])
        self.assertTrue(gigachat_called(mocks))

    def test_topic_too_long(self):
        results = self.post_each_endpoint(self.demo_client, {'topic': 'т' * 101})
        self.assert_all_denied(results, 400)

    def test_result_text_too_long(self):
        client = self.demo_client()
        with gigachat_mocks() as mocks:
            response = client.post('/generate-image-from-text/',
                                   {'topic': TOPIC, 'result_text': 'п' * 301}, **AJAX)

        self.assertFalse(gigachat_called(mocks))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_max_length_allowed(self):
        """Ввод ровно на границе лимита проходит"""
        client = self.demo_client()
        with gigachat_mocks() as mocks:
            response = client.post('/generate-image-from-text/',
                                   {'topic': 'т' * 100, 'result_text': 'п' * 300}, **AJAX)

        self.assertTrue(response.json()['success'], response.json())
        self.assertTrue(gigachat_called(mocks))

    def test_non_ajax_denied_redirects_to_limit_page(self):
        """Обычный запрос при исчерпанном лимите — редирект на страницу лимита"""
        def make_client():
            client = self.demo_client()
            token = demo_token_of(client)
            token.gigachat_tokens_used = token.gigachat_tokens_limit
            token.save()
            return client

        results = self.post_each_endpoint(make_client, ajax=False)

        for url, (response, called) in results.items():
            with self.subTest(url=url):
                self.assertFalse(called)
                self.assertRedirects(response, '/limit-exceeded/', fetch_redirect_response=False)


class GigaChatAccountingTests(TestCase):
    """Вызов, перешедший лимит токена, всё равно учитывается"""

    def test_crossing_call_exhausts_token(self):
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE',
            gigachat_tokens_limit=100,
            gigachat_tokens_used=90,
            openai_tokens_limit=0,
        )

        self.assertFalse(token.consume_gigachat_tokens(50))

        token.refresh_from_db()
        self.assertEqual(token.gigachat_tokens_used, 140)
        self.assertFalse(token.can_use_gigachat()[0])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CsrfTests(TestCase):
    """POST без CSRF на «Попробовать» и генерацию → 403"""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def login_by_link(self):
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE', gigachat_tokens_limit=20000, openai_tokens_limit=0,
        )
        self.client.get(f'/auth/token/{token.token}/')
        return token

    def test_try_without_csrf(self):
        response = self.client.post('/try/')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(TemporaryAccessToken.objects.count(), 0)

    def test_generation_without_csrf(self):
        self.login_by_link()

        for url, data in GENERATION_ENDPOINTS.items():
            with self.subTest(url=url), gigachat_mocks() as mocks:
                response = self.client.post(url, data, **AJAX)
                self.assertEqual(response.status_code, 403)
                self.assertFalse(gigachat_called(mocks))

    def test_generation_with_csrf_header(self):
        """Контроль: с заголовком X-CSRFToken, как шлёт фронтенд, запрос проходит"""
        self.login_by_link()
        self.client.get('/generator/')
        csrf = self.client.cookies['csrftoken'].value

        with gigachat_mocks() as mocks:
            response = self.client.post('/regenerate-text/', {'topic': TOPIC},
                                        HTTP_X_CSRFTOKEN=csrf, **AJAX)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(gigachat_called(mocks))


class TokenAuthViewTests(TestCase):
    """token_auth_view после выноса общего кода ведёт себя как раньше"""

    def test_session_and_login_for_telegram_token(self):
        expires = timezone.now() + timedelta(days=14)
        token = TemporaryAccessToken.objects.create(
            token_type='HIDDEN_14D',
            gigachat_tokens_limit=-1,
            gigachat_tokens_used=7,
            openai_tokens_limit=0,
            expires_at=expires,
            telegram_user_id=555001,
        )

        response = self.client.get(f'/auth/token/{token.token}/', REMOTE_ADDR='203.0.113.9')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        session = self.client.session
        self.assertEqual(session['access_token'], str(token.token))
        self.assertEqual(session['token_type'], 'HIDDEN_14D')
        self.assertTrue(session['is_demo'])
        self.assertEqual(session['gigachat_tokens_limit'], -1)
        self.assertEqual(session['gigachat_tokens_used'], 7)
        self.assertEqual(session['openai_tokens_limit'], 0)
        self.assertEqual(session['openai_tokens_used'], 0)
        self.assertEqual(session['expires_at'], expires.isoformat())
        self.assertEqual(session['daily_generations_left'], -1)
        user = User.objects.get(username='tg_555001')
        self.assertEqual(session[SESSION_KEY], str(user.pk))
        self.assertFalse(user.has_usable_password())

        token.refresh_from_db()
        self.assertIsNotNone(token.last_used)
        self.assertEqual(token.current_ip, '203.0.113.9')

    def test_session_without_telegram(self):
        token = TemporaryAccessToken.objects.create(
            token_type='DEVELOPER', gigachat_tokens_limit=-1, openai_tokens_limit=-1,
        )

        response = self.client.get(f'/auth/token/{token.token}/')

        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        session = self.client.session
        self.assertFalse(session['is_demo'])
        self.assertIsNone(session['expires_at'])
        self.assertNotIn(SESSION_KEY, session)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000)
class LongTopicAccountingTests(TestCase):
    """
    Тема предельной длины не выключает учёт и дневной потолок

    Запись строки учёта проверяет длину, как PostgreSQL: на SQLite без этого
    слишком длинная тема записалась бы молча.
    """

    URLS = ('/generator/', '/regenerate-text/')

    def setUp(self):
        self.topic = 'т' * settings.GENERATION_MAX_TOPIC_LENGTH
        self.max_length = GigaChatTokenUsage._meta.get_field('topic').max_length

    def test_row_written_for_max_topic(self):
        """Строка учёта есть, тема в ней не длиннее поля"""
        for url in self.URLS:
            with self.subTest(url=url):
                GigaChatTokenUsage.objects.all().delete()
                client, _ = try_demo()
                with postgres_varchar_lengths(GigaChatTokenUsage), fake_gigachat() as fake:
                    response = client.post(url, {'topic': self.topic}, **AJAX)

                self.assertTrue(response.json()['success'], response.json())
                self.assertEqual(fake.calls, 1)
                row = GigaChatTokenUsage.objects.get()
                self.assertLessEqual(len(row.topic), self.max_length)
                self.assertEqual(row.topic, self.topic[:self.max_length])

    @override_settings(GIGACHAT_DAILY_CALL_LIMIT=1)
    def test_daily_ceiling_with_max_topic(self):
        """При потолке 1 второй запрос с той же темой — 429, клиент не вызван"""
        for url in self.URLS:
            with self.subTest(url=url):
                GigaChatTokenUsage.objects.all().delete()
                client, _ = try_demo()
                with postgres_varchar_lengths(GigaChatTokenUsage), fake_gigachat() as fake:
                    first = client.post(url, {'topic': self.topic}, **AJAX)
                    second = client.post(url, {'topic': self.topic}, **AJAX)

                self.assertTrue(first.json()['success'], first.json())
                self.assertEqual(second.status_code, 429)
                self.assertFalse(second.json()['success'])
                self.assertEqual(fake.calls, 1)

    def test_topic_and_platform_truncated(self):
        """log_token_usage обрезает тему и платформу до длины полей"""
        platform_max = GigaChatTokenUsage._meta.get_field('platform').max_length

        with postgres_varchar_lengths(GigaChatTokenUsage):
            log_token_usage('TEXT_GENERATION', 'промпт', 'ответ',
                            topic='т' * (self.max_length + 1),
                            platform='п' * (platform_max + 1))

        row = GigaChatTokenUsage.objects.get()
        self.assertEqual(len(row.topic), self.max_length)
        self.assertEqual(len(row.platform), platform_max)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), DEMO_TOKENS_PER_IP_PER_DAY=1000)
class CallChainAccountingTests(TestCase):
    """
    Каждый вызов GigaChat учтён; после пересечения лимита токена
    следующие вызовы цепочки к клиенту не обращаются
    """

    def near_limit_client(self):
        """Демо-клиент, которому до лимита GigaChat остался один токен"""
        client, _ = try_demo()
        token = demo_token_of(client)
        token.gigachat_tokens_used = token.gigachat_tokens_limit - 1
        token.save()
        return client, token

    def test_full_chain_with_ample_limit(self):
        """Контроль: с запасом лимита фейк проходит текст, промпт и картинку"""
        client, _ = try_demo()

        with fake_gigachat() as fake:
            response = client.post('/generator/', {'topic': TOPIC, 'generate_image': 'on'}, **AJAX)

        data = response.json()
        self.assertTrue(data['success'], data)
        self.assertTrue(data['image_url'])
        self.assertEqual((fake.invoke_calls, fake.chat_calls), (2, 1))
        self.assertEqual(
            sorted(GigaChatTokenUsage.objects.values_list('operation_type', flat=True)),
            ['IMAGE_GENERATION', 'IMAGE_PROMPT', 'TEXT_GENERATION'],
        )

    def test_generator_with_image_near_limit(self):
        """Текст пересёк лимит: он отдаётся, промпт и картинка не запрашиваются"""
        client, token = self.near_limit_client()

        with fake_gigachat() as fake:
            response = client.post('/generator/', {'topic': TOPIC, 'generate_image': 'on'}, **AJAX)

        data = response.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['result'], FakeGigaChat.TEXT)
        self.assertIsNone(data['image_url'])
        self.assertEqual((fake.invoke_calls, fake.chat_calls), (1, 0))
        row = GigaChatTokenUsage.objects.get()
        self.assertEqual(row.operation_type, 'TEXT_GENERATION')
        self.assertEqual(row.token, token)
        token.refresh_from_db()
        self.assertGreater(token.gigachat_tokens_used, token.gigachat_tokens_limit)

    def test_image_from_text_near_limit(self):
        """Промпт картинки пересёк лимит: картинка не запрашивается"""
        client, _ = self.near_limit_client()

        with fake_gigachat() as fake:
            client.post('/generate-image-from-text/',
                        {'topic': TOPIC, 'result_text': 'Готовый пост про кофейню'}, **AJAX)

        self.assertEqual((fake.invoke_calls, fake.chat_calls), (1, 0))
        self.assertEqual(GigaChatTokenUsage.objects.get().operation_type, 'IMAGE_PROMPT')

    def test_other_endpoints_near_limit(self):
        """Перегенерация текста и картинки у края лимита: 1 обращение, 1 строка"""
        for url in ('/regenerate-text/', '/regenerate-image/'):
            with self.subTest(url=url):
                GigaChatTokenUsage.objects.all().delete()
                client, _ = self.near_limit_client()

                with fake_gigachat() as fake:
                    response = client.post(url, GENERATION_ENDPOINTS[url], **AJAX)

                self.assertEqual(fake.calls, 1, response.json())
                self.assertEqual(GigaChatTokenUsage.objects.count(), 1)


class GigaChatFunctionLimitTests(TestCase):
    """Функции gigachat_api проверяют лимит токена перед каждым обращением к клиенту"""

    CALLS = {
        'generate_text': lambda token: generate_text({'topic': TOPIC}, token=token),
        'generate_image_prompt_from_text': lambda token: generate_image_prompt_from_text(
            'Готовый пост про кофейню', {'topic': TOPIC}, token=token),
        'generate_image_gigachat': lambda token: generate_image_gigachat(
            'Промпт для картинки', token=token),
    }

    def make_token(self, **fields):
        values = {
            'token_type': 'DEMO_FREE',
            'gigachat_tokens_limit': 5000,
            'gigachat_tokens_used': 0,
            'openai_tokens_limit': 0,
        }
        values.update(fields)
        return TemporaryAccessToken.objects.create(**values)

    def assert_limit_result(self, name, result):
        """Результат функции, которая вышла без обращения к клиенту"""
        if name == 'generate_text':
            self.assertTrue(result.startswith('WARNING: Лимит токенов GigaChat исчерпан'), result)
        else:
            self.assertIsNone(result)

    def test_no_client_calls_without_limit(self):
        """Исчерпанный, истёкший или неактивный токен: 0 обращений у всех трёх функций"""
        cases = {
            'исчерпан': {'gigachat_tokens_used': 5000},
            'истёк': {'expires_at': timezone.now() - timedelta(minutes=1)},
            'неактивен': {'is_active': False},
        }
        for case, fields in cases.items():
            token = self.make_token(**fields)
            for name, call in self.CALLS.items():
                with self.subTest(case=case, function=name):
                    with fake_gigachat() as fake:
                        result = call(token)

                    self.assertEqual(fake.calls, 0)
                    self.assert_limit_result(name, result)
        self.assertEqual(GigaChatTokenUsage.objects.count(), 0)

    def test_crossing_call_returns_result(self):
        """Вызов, пересёкший лимит, отдаёт результат и учтён; следующий — без обращения"""
        expected = {
            'generate_text': FakeGigaChat.TEXT,
            'generate_image_prompt_from_text': FakeGigaChat.TEXT,
            'generate_image_gigachat': 'data:image/jpeg;base64,'
                                       + base64.b64encode(FakeGigaChat.IMAGE_BYTES).decode(),
        }
        for name, call in self.CALLS.items():
            with self.subTest(function=name):
                GigaChatTokenUsage.objects.all().delete()
                token = self.make_token(gigachat_tokens_used=4999)

                with fake_gigachat() as fake:
                    result = call(token)
                    repeat = call(token)

                self.assertEqual(result, expected[name])
                self.assertEqual(fake.calls, 1)
                self.assertEqual(GigaChatTokenUsage.objects.filter(token=token).count(), 1)
                self.assertFalse(token.can_use_gigachat()[0])
                self.assert_limit_result(name, repeat)


class CheckGigachatAccessTests(TestCase):
    """check_gigachat_access сама отказывает без действующего токена, не полагаясь на middleware"""

    def make_request(self, token=None, ajax=True):
        request = RequestFactory().post('/regenerate-text/', {'topic': TOPIC},
                                        **(AJAX if ajax else {}))
        SessionMiddleware(lambda r: None).process_request(request)
        if token is not None:
            request.session['access_token'] = str(token.token)
        return request

    def make_token(self, **fields):
        return TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE', gigachat_tokens_limit=5000, openai_tokens_limit=0, **fields,
        )

    def denied_cases(self):
        return {
            'нет токена': None,
            'токен истёк': self.make_token(expires_at=timezone.now() - timedelta(minutes=1)),
            'токен неактивен': self.make_token(is_active=False),
        }

    def test_denied_ajax(self):
        """AJAX: 403 и JSON с ошибкой, request.token не выставлен"""
        for case, token in self.denied_cases().items():
            with self.subTest(case=case):
                request = self.make_request(token)

                response = check_gigachat_access(request, topic=TOPIC)

                self.assertIsNotNone(response)
                self.assertEqual(response.status_code, 403)
                data = json.loads(response.content)
                self.assertFalse(data['success'])
                self.assertTrue(data['error'])
                self.assertFalse(hasattr(request, 'token'))

    def test_denied_regular_request(self):
        """Обычный запрос: редирект на страницу требования токена"""
        for case, token in self.denied_cases().items():
            with self.subTest(case=case):
                request = self.make_request(token, ajax=False)

                response = check_gigachat_access(request, topic=TOPIC)

                self.assertIsNotNone(response)
                self.assertRedirects(response, reverse('token_required_page'),
                                     fetch_redirect_response=False)
                self.assertFalse(hasattr(request, 'token'))

    def test_valid_token_allowed(self):
        """Контроль: действующий токен проходит и кладётся в request.token"""
        token = self.make_token()
        request = self.make_request(token)

        self.assertIsNone(check_gigachat_access(request, topic=TOPIC))
        self.assertEqual(request.token, token)


class ConsumeAtomicTests(TestCase):
    """Списание атомарно: параллельные запросы одного токена не теряют расход"""

    def two_copies(self):
        """Два экземпляра одного токена, загруженные до списания (как в двух запросах)"""
        token = TemporaryAccessToken.objects.create(
            token_type='BASIC', gigachat_tokens_limit=10000, openai_tokens_limit=10000,
        )
        return (TemporaryAccessToken.objects.get(pk=token.pk),
                TemporaryAccessToken.objects.get(pk=token.pk))

    def stored(self, token):
        return TemporaryAccessToken.objects.get(pk=token.pk)

    def test_gigachat_tokens(self):
        first, second = self.two_copies()

        self.assertTrue(first.consume_gigachat_tokens(100))
        self.assertTrue(second.consume_gigachat_tokens(200))

        self.assertEqual(self.stored(first).gigachat_tokens_used, 300)
        self.assertEqual(second.gigachat_tokens_used, 300)

    def test_openai_tokens(self):
        first, second = self.two_copies()

        self.assertTrue(first.consume_openai_tokens(100))
        self.assertTrue(second.consume_openai_tokens(200))

        self.assertEqual(self.stored(first).openai_tokens_used, 300)
        self.assertEqual(second.openai_tokens_used, 300)

    def test_generation_counter(self):
        first, second = self.two_copies()

        first.consume_generation(ip_address='203.0.113.5')
        second.consume_generation()

        stored = self.stored(first)
        self.assertEqual(stored.total_used, 2)
        self.assertEqual(second.total_used, 2)
        self.assertEqual(stored.current_ip, '203.0.113.5')
        self.assertIsNotNone(stored.last_used)

    def test_consume_keeps_other_fields(self):
        """Списание не затирает поля, которые изменил другой запрос (например, деактивацию)"""
        first, second = self.two_copies()
        second.is_active = False
        second.save(update_fields=['is_active'])

        first.consume_gigachat_tokens(10)
        first.consume_openai_tokens(10)
        first.consume_generation()

        self.assertFalse(self.stored(first).is_active)


class ConsumeSemanticsTests(TestCase):
    """Прежняя семантика списания: что считается, что нет и что возвращается"""

    def make_token(self, token_type='BASIC', **fields):
        return TemporaryAccessToken.objects.create(token_type=token_type, **fields)

    def stored(self, token):
        return TemporaryAccessToken.objects.get(pk=token.pk)

    def test_gigachat_not_counted_types(self):
        for token_type in ('HIDDEN_14D', 'HIDDEN_30D', 'DEVELOPER', 'UNLIMITED'):
            with self.subTest(token_type=token_type):
                token = self.make_token(token_type, gigachat_tokens_limit=100)

                self.assertTrue(token.consume_gigachat_tokens(500))
                self.assertEqual(self.stored(token).gigachat_tokens_used, 0)

    def test_gigachat_unlimited_counts(self):
        token = self.make_token(gigachat_tokens_limit=-1)

        self.assertTrue(token.consume_gigachat_tokens(500))
        self.assertTrue(token.consume_gigachat_tokens(500))
        self.assertEqual(self.stored(token).gigachat_tokens_used, 1000)

    def test_gigachat_limit(self):
        """В пределах лимита — True; пересечение записывается и даёт False"""
        token = self.make_token(gigachat_tokens_limit=100)

        self.assertTrue(token.consume_gigachat_tokens(60))
        self.assertTrue(token.consume_gigachat_tokens(40))
        self.assertFalse(token.consume_gigachat_tokens(1))
        self.assertEqual(self.stored(token).gigachat_tokens_used, 101)

    def test_openai_not_counted_types(self):
        for token_type in ('HIDDEN_14D', 'HIDDEN_30D', 'DEVELOPER'):
            with self.subTest(token_type=token_type):
                token = self.make_token(token_type, openai_tokens_limit=100)

                self.assertTrue(token.consume_openai_tokens(500))
                self.assertEqual(self.stored(token).openai_tokens_used, 0)

    def test_openai_unavailable(self):
        token = self.make_token(openai_tokens_limit=0)

        self.assertFalse(token.consume_openai_tokens(10))
        self.assertEqual(self.stored(token).openai_tokens_used, 0)

    def test_openai_unlimited_counts(self):
        token = self.make_token(openai_tokens_limit=-1)

        self.assertTrue(token.consume_openai_tokens(500))
        self.assertEqual(self.stored(token).openai_tokens_used, 500)

    def test_openai_limit(self):
        """Сверх лимита OpenAI не списывается и возвращает False"""
        token = self.make_token(openai_tokens_limit=100)

        self.assertTrue(token.consume_openai_tokens(60))
        self.assertFalse(token.consume_openai_tokens(50))
        self.assertTrue(token.consume_openai_tokens(40))
        self.assertEqual(self.stored(token).openai_tokens_used, 100)
