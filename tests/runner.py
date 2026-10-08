"""
Тестовый раннер с предохранителем от сети

На время прогона ставит глобальные заглушки: клиенты GigaChat и
requests бросают исключение, если тест не замокал их сам.
Моки внутри тестов ставятся позже и срабатывают раньше заглушек.
"""

from unittest import mock

from django.test.runner import DiscoverRunner

GIGACHAT_MESSAGE = 'Тест обратился к GigaChat без мока'
NETWORK_MESSAGE = 'Тест обратился к сети без мока'

# Настоящие _init_client и _init_direct_client под заглушками. Берёт тест
# создания клиента: он мокает конструктор GigaChat и проверяет аргументы
UNGUARDED = {}


class NetworkAccessBlocked(BaseException):
    """
    Обращение теста к GigaChat или к сети без мока

    Наследник BaseException, а не Exception: generate_text и
    generate_image_gigachat ловят Exception и превращают ошибку в текст
    или None, и тогда тест прошёл бы молча.
    """


def _block_gigachat(*args, **kwargs):
    raise NetworkAccessBlocked(GIGACHAT_MESSAGE)


def _block_network(*args, **kwargs):
    raise NetworkAccessBlocked(NETWORK_MESSAGE)


class NoNetworkTestRunner(DiscoverRunner):
    """DiscoverRunner, который запрещает тестам GigaChat и сеть без мока"""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        from generator import gigachat_api
        UNGUARDED.update(
            _init_client=gigachat_api._init_client,
            _init_direct_client=gigachat_api._init_direct_client,
        )
        self._network_guards = [
            mock.patch('generator.gigachat_api._init_client', new=_block_gigachat),
            mock.patch('generator.gigachat_api._init_direct_client', new=_block_gigachat),
            mock.patch('requests.sessions.Session.request', new=_block_network),
        ]
        for guard in self._network_guards:
            guard.start()

    def teardown_test_environment(self, **kwargs):
        for guard in reversed(self._network_guards):
            guard.stop()
        super().teardown_test_environment(**kwargs)
