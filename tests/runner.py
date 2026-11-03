"""
Тестовый раннер с предохранителем от сети

На время прогона ставит глобальные заглушки:
- клиенты GigaChat (`_init_client`, `_init_direct_client`) и YandexGPT;
- `requests.Session.request`;
- сокет (`socket.socket.connect`, `connect_ex`, `create_connection`,
  `getaddrinfo`, `gethostbyname`, `gethostbyname_ex`) — замечание 3 ревью
  безопасности: мок DNS в тесте не снимет этот заслон;
- `httpx.Client.send` и `urllib.request.urlopen` — те же причины.

Тесты, которым нужны живые объекты (например, конструктор клиента),
берут их из `UNGUARDED` или снимают часть заглушек явно.
"""

from unittest import mock

from django.test.runner import DiscoverRunner

GIGACHAT_MESSAGE = 'Тест обратился к GigaChat без мока'
YANDEX_MESSAGE = 'Тест обратился к YandexGPT без мока'
NETWORK_MESSAGE = 'Тест обратился к сети без мока'

# Настоящие функции под заглушками. Берёт их тест создания клиента: он
# мокает конструктор и проверяет аргументы (test_init_client_passes_model
# и подобные)
UNGUARDED = {}


class NetworkAccessBlocked(BaseException):
    """
    Обращение теста к LLM-клиенту или к сети без мока

    Наследник BaseException, а не Exception: `generate_text` и
    `generate_image_gigachat` ловят Exception и превращают ошибку
    в `GigaChatError` или `None`, и тогда тест прошёл бы молча.
    """


def _block_gigachat(*args, **kwargs):
    raise NetworkAccessBlocked(GIGACHAT_MESSAGE)


def _block_yandex(*args, **kwargs):
    raise NetworkAccessBlocked(YANDEX_MESSAGE)


def _block_network(*args, **kwargs):
    raise NetworkAccessBlocked(NETWORK_MESSAGE)


def _build_network_guards():
    """
    Полный список заглушек. Собран функцией, чтобы `test_network_guard`
    и ручной прогон (`setup_test_environment()` в scratchpad) могли
    применить его отдельно, без запуска всего раннера
    """
    guards = [
        mock.patch('generator.gigachat_api._init_client', new=_block_gigachat),
        mock.patch('generator.gigachat_api._init_direct_client', new=_block_gigachat),
        mock.patch('generator.yandexgpt_api._call_completion', new=_block_yandex),
        mock.patch('requests.sessions.Session.request', new=_block_network),
    ]
    # Сокет — на уровне класса/модуля, чтобы ловить любое соединение,
    # даже если тест замокал DNS (замечание 3 ревью безопасности).
    # Патч на классе: заглушка применится ко всем экземплярам
    import socket as _socket
    guards.extend([
        mock.patch.object(_socket.socket, 'connect', new=_block_network),
        mock.patch.object(_socket.socket, 'connect_ex', new=_block_network),
        mock.patch('socket.create_connection', new=_block_network),
        mock.patch('socket.getaddrinfo', new=_block_network),
        mock.patch('socket.gethostbyname', new=_block_network),
        mock.patch('socket.gethostbyname_ex', new=_block_network),
    ])
    # httpx — отдельный HTTP-клиент; есть в проектных и чужих библиотеках.
    # Патчим `HTTPTransport.handle_request`: он перехватывает и sync,
    # и async (у `AsyncHTTPTransport` своё `handle_async_request`,
    # для sync-тестов довольно одного).
    try:
        import httpx  # noqa: F401
        guards.append(mock.patch('httpx.HTTPTransport.handle_request', new=_block_network))
    except ImportError:
        pass
    guards.append(mock.patch('urllib.request.urlopen', new=_block_network))
    return guards


class NoNetworkTestRunner(DiscoverRunner):
    """DiscoverRunner, который запрещает тестам LLM-клиенты и сеть без мока"""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        from generator import gigachat_api
        from generator import yandexgpt_api
        UNGUARDED.update(
            _init_client=gigachat_api._init_client,
            _init_direct_client=gigachat_api._init_direct_client,
            _call_completion=yandexgpt_api._call_completion,
        )
        self._network_guards = _build_network_guards()
        for guard in self._network_guards:
            guard.start()

    def teardown_test_environment(self, **kwargs):
        for guard in reversed(self._network_guards):
            guard.stop()
        super().teardown_test_environment(**kwargs)
