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
        
        # URL-паттерны, которые не требуют токена
        self.exempt_urls = [
            '/auth/token/',      # Вход по токену
            '/admin/',           # Админ-панель Django
            '/static/',          # Статические файлы
            '/media/',           # Медиа файлы
            '/telegram/webhook/',  # Telegram webhook
            '/token-required/',  # Страница с требованием токена
            '/invalid-token/',   # Страница неверного токена
            '/limit-exceeded/',  # Страница превышения лимита
        ]
    
    def __call__(self, request):
        """Обработка каждого запроса"""
        
        # Пропускаем исключённые URLs
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
            
            # Для DEMO токенов проверяем дневной лимит
            if token.token_type == 'DEMO':
                # Сбрасываем счетчик если новый день
                token.reset_daily_limit()
                
                # Обновляем данные в сессии
                request.session['daily_generations_left'] = token.daily_generations_left
                
                # Проверяем лимит только для запросов генерации
                # (остальные страницы доступны даже при исчерпании лимита)
                if request.path.startswith('/generator/') or request.path.startswith('/regenerate-'):
                    if token.daily_generations_left <= 0:
                        return redirect('limit_exceeded_page')
        
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
