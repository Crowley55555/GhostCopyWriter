"""
Middleware для системы токенов доступа

Обеспечивает проверку временных токенов доступа для всех запросов,
кроме специально исключенных URL (админка, статика, публичные страницы).

Фаза 3: при `request.user.is_authenticated` — токен всегда REGISTERED
пользователя (`issue_or_get_registered_token(user)`), демо-токен в
сессии игнорируется, `session.flush()` не вызывается. `/login/`,
`/register/`, `/logout/` — в точных исключениях.
"""

from django.urls import reverse
from django.utils import timezone
from .access import MSG_NO_TOKEN, MSG_TOKEN_INVALID, deny, issue_or_get_registered_token
from .models import TemporaryAccessToken


class TokenAccessMiddleware:
    """
    Middleware для проверки доступа по временным токенам

    Проверяет наличие активного токена в сессии для каждого запроса.
    Для DEMO токенов дополнительно проверяет лимит генераций.
    AJAX-запросы при отказе получают JSON с ошибкой вместо редиректа.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # URL-паттерны, которые не требуют токена (префиксы)
        self.exempt_urls = [
            '/auth/token/',      # Вход по токену
            '/admin/',           # Админ-панель Django
            '/static/',          # Статические файлы
            '/media/',           # Медиа файлы
            '/telegram/webhook/',  # Telegram webhook
            '/token-required/',  # Страница с требованием токена
            '/invalid-token/',   # Страница неверного токена
            '/limit-exceeded/',  # Страница превышения лимита
            '/api/',             # API endpoints
        ]

        # Точные URL без токена (публичные страницы).
        # Фаза 3: `/login/`, `/register/`, `/logout/` — доступ без токена
        # (на этих страницах выдаётся регистрация/вход).
        self.exact_exempt_urls = [
            '/',                 # Главная страница (landing)
            '/try/',             # «Попробовать»: выдача демо-токена (POST с CSRF)
            '/login/',           # Фаза 3: вход
            '/register/',        # Фаза 3: регистрация
            '/logout/',          # Фаза 3: выход (POST)
        ]

    def __call__(self, request):
        """Обработка каждого запроса"""

        # Пропускаем точные совпадения (публичные страницы)
        if request.path in self.exact_exempt_urls:
            return self.get_response(request)

        # Пропускаем исключённые URLs по префиксу
        if self._is_exempt_url(request.path):
            return self.get_response(request)

        # Фаза 3: залогиненный пользователь всегда ходит под REGISTERED-токеном,
        # демо-токен сессии при этом не учитывается и сессия не сбрасывается
        if request.user.is_authenticated:
            token = issue_or_get_registered_token(request.user)
            if token.is_expired():
                token.is_active = False
                token.save(update_fields=['is_active'])
                token = issue_or_get_registered_token(request.user)
            request.token = token
            # Кладём в сессию актуальные лимиты токена REGISTERED
            request.session['access_token'] = str(token.token)
            request.session['token_type'] = token.token_type
            request.session['gigachat_tokens_limit'] = token.gigachat_tokens_limit
            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
            request.session['openai_tokens_limit'] = token.openai_tokens_limit
            request.session['openai_tokens_used'] = token.openai_tokens_used
            request.session['is_demo'] = False
            request.session['daily_generations_left'] = -1
            return self.get_response(request)

        # Проверяем наличие активного токена в сессии
        token_str = request.session.get('access_token')

        if not token_str:
            # Нет токена - перенаправляем на страницу требования токена
            return deny(request, MSG_NO_TOKEN, 403, 'token_required_page')

        # Проверяем валидность токена в базе данных
        try:
            token = TemporaryAccessToken.objects.get(
                token=token_str,
                is_active=True
            )

            # Проверяем срок действия
            if token.is_expired():
                # Токен истек - деактивируем его автоматически
                token.is_active = False
                token.save(update_fields=['is_active'])

                # Очищаем сессию и перенаправляем
                self._clear_session(request)
                return deny(request, MSG_TOKEN_INVALID, 403, 'invalid_token_page')

            # Сохраняем токен в request для использования в views
            request.token = token

            # Обновляем сессию с информацией о лимитах токенов
            request.session['token_type'] = token.token_type
            request.session['gigachat_tokens_limit'] = token.gigachat_tokens_limit
            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
            request.session['openai_tokens_limit'] = token.openai_tokens_limit
            request.session['openai_tokens_used'] = token.openai_tokens_used

            # Для обратной совместимости
            request.session['is_demo'] = (token.token_type == 'DEMO_FREE' or token.token_type.startswith('HIDDEN'))
            request.session['daily_generations_left'] = -1  # Устаревшее поле

        except TemporaryAccessToken.DoesNotExist:
            # Токен не найден в базе - очищаем сессию
            self._clear_session(request)
            return deny(request, MSG_TOKEN_INVALID, 403, 'invalid_token_page')

        # Всё хорошо - пропускаем запрос дальше
        response = self.get_response(request)
        return response
    
    def _is_exempt_url(self, path):
        """
        Проверяет, является ли URL исключённым из проверки токенов
        
        Args:
            path (str): Путь запроса
        
        Returns:
            bool: True если URL исключён, False в противном случае
        """
        # Проверяем точные совпадения (публичные страницы)
        if path in self.exact_exempt_urls:
            return True
        
        # Проверяем префиксы (админка, статика и т.д.)
        return any(path.startswith(url) for url in self.exempt_urls)
    
    def _clear_session(self, request):
        """
        Очищает данные токена из сессии
        
        Args:
            request: HTTP запрос
        """
        request.session.pop('access_token', None)
        request.session.pop('token_type', None)
        request.session.pop('is_demo', None)
        request.session.pop('daily_generations_left', None)
        request.session.pop('gigachat_tokens_limit', None)
        request.session.pop('gigachat_tokens_used', None)
        request.session.pop('openai_tokens_limit', None)
        request.session.pop('openai_tokens_used', None)
