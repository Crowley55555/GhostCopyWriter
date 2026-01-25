"""
Middleware для системы токенов доступа

Обеспечивает проверку временных токенов доступа для всех запросов,
кроме специально исключенных URL (админка, статика, публичные страницы).
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from .models import TemporaryAccessToken


class TokenAccessMiddleware:
    """
    Middleware для проверки доступа по временным токенам
    
    Проверяет наличие активного токена в сессии для каждого запроса.
    Для DEMO токенов дополнительно проверяет лимит генераций.
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
        
        # Точные URL без токена (публичные страницы)
        self.exact_exempt_urls = [
            '/',                 # Главная страница (landing)
        ]
    
    def __call__(self, request):
        """Обработка каждого запроса"""
        
        # Пропускаем точные совпадения (публичные страницы)
        if request.path in self.exact_exempt_urls:
            return self.get_response(request)
        
        # Пропускаем исключённые URLs по префиксу
        if self._is_exempt_url(request.path):
            return self.get_response(request)
        
        # Проверяем наличие активного токена в сессии
        token_str = request.session.get('access_token')
        
        if not token_str:
            # Нет токена - перенаправляем на страницу требования токена
            return redirect('token_required_page')
        
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
                return redirect('invalid_token_page')
            
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
            return redirect('invalid_token_page')
        
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
