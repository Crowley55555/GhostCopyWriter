"""
Постоянный тест-страж предохранителя сети (замечание 3 ревью безопасности)

Фаза 2а.2: раннер `tests/runner.NoNetworkTestRunner` ставит заглушки на
уровне сокета (`socket.socket.connect`, `getaddrinfo`, ...), `httpx`,
`urllib`, клиенты GigaChat и YandexGPT. Эти тесты проверяют, что без
отдельного мока обращения к сети **не доходят** до реального стека:

- `test_socket_connect_blocked` — сырой `socket.socket.connect` к
  тестовому адресу (RFC 5737 192.0.2.0/24) → `NetworkAccessBlocked`;
- `test_getaddrinfo_blocked` — разрешение DNS без мока → блок;
- `test_urllib3_blocked_via_mocked_dns` — DNS замокан, `urllib3` пробует
  соединиться по IP, страж `socket.connect` ловит;
- `test_httpx_blocked` — вызов `httpx.get(...)` → блок;
- `test_urllib_blocked` — `urllib.request.urlopen(...)` → блок;
- `test_yandexgpt_client_blocked` — вызов `generate_text_yandex` без
  мока `_call_completion` → блок.

Тесты **постоянные** и не удаляются: будущие доработки (например, SSRF
в 2а.4 из «Возможных доработок») будут трогать раннер, страж не должен
ослабевать.
"""

import socket
from unittest import mock

from django.test import TestCase, override_settings

from tests.runner import NetworkAccessBlocked


# RFC 5737 тестовые адреса: соединение туда никогда не удастся и ничему
# не навредит, если страж вдруг пропустит. Публичного смысла не несёт
_TEST_IPV4 = '192.0.2.1'
_TEST_PORT = 80


class NetworkGuardTests(TestCase):

    def test_socket_connect_blocked(self):
        """Сырой socket.socket.connect без мока → NetworkAccessBlocked"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(NetworkAccessBlocked):
                s.connect((_TEST_IPV4, _TEST_PORT))
        finally:
            s.close()

    def test_getaddrinfo_blocked(self):
        """`socket.getaddrinfo` без мока → NetworkAccessBlocked"""
        with self.assertRaises(NetworkAccessBlocked):
            socket.getaddrinfo('example.com', _TEST_PORT)

    def test_urllib3_blocked_via_mocked_dns(self):
        """
        Даже с замоканным DNS `urllib3` упрётся в `socket.connect`

        Если бы страж стоял только на `getaddrinfo` (как было до фазы 2а.2),
        тест с моком DNS мог бы послать настоящий запрос. Теперь связь
        рвётся на этапе соединения с IP (замечание 3 ревью безопасности).
        """
        import urllib3
        # Мокаем DNS: `getaddrinfo` отдаёт заранее подготовленный адрес
        with mock.patch(
            'socket.getaddrinfo',
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '',
                           (_TEST_IPV4, _TEST_PORT))],
        ):
            pool = urllib3.PoolManager()
            # Любое из этих исключений должно сработать: NetworkAccessBlocked
            # пробрасывается в urllib3 как BaseException, а она может завернуть
            # его. Главное — реальный HTTP не ушёл
            try:
                pool.request('GET', f'http://{_TEST_IPV4}/')
                self.fail('urllib3 запрос прошёл — предохранитель не сработал')
            except NetworkAccessBlocked:
                pass
            except BaseException as exc:
                # Разворачиваем цепочку: `NetworkAccessBlocked` может быть
                # внутри urllib3-ошибки
                root = exc
                while root.__context__ is not None:
                    root = root.__context__
                if isinstance(root, NetworkAccessBlocked):
                    return
                raise

    def test_httpx_blocked(self):
        """`httpx.get(...)` без мока → NetworkAccessBlocked"""
        import httpx
        with self.assertRaises((NetworkAccessBlocked, httpx.HTTPError)) as ctx:
            httpx.get('https://example.com')
        # Если `httpx.HTTPError` — убедимся, что внутри лежит `NetworkAccessBlocked`
        exc = ctx.exception
        if not isinstance(exc, NetworkAccessBlocked):
            root = exc
            while root.__context__ is not None:
                root = root.__context__
            self.assertIsInstance(root, NetworkAccessBlocked)

    def test_urllib_blocked(self):
        """`urllib.request.urlopen(...)` без мока → NetworkAccessBlocked"""
        import urllib.request
        with self.assertRaises(NetworkAccessBlocked):
            urllib.request.urlopen('http://example.com')

    @override_settings(YANDEX_API_KEY='test-key-abc', YANDEX_FOLDER_ID='folder-id')
    def test_yandexgpt_client_blocked(self):
        """
        `generate_text_yandex(...)` без мока `_call_completion` → NetworkAccessBlocked

        Параметры `YANDEX_API_KEY`/`YANDEX_FOLDER_ID` подставлены через
        `override_settings`, чтобы функция не упала на ранней проверке
        «ключ не настроен», а дошла до фейкового HTTP-клиента.
        """
        from generator.yandexgpt_api import generate_text_yandex
        data = {
            'topic': 'Кофе', 'platform': 'VK',
            'business_info': '',
        }
        with self.assertRaises(NetworkAccessBlocked):
            generate_text_yandex(data)
