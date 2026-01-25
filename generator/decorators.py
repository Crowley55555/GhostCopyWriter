"""
Декораторы для системы токенов доступа

Предоставляет функциональность для управления лимитами генераций
и проверки прав доступа на основе временных токенов.
"""

from functools import wraps
from django.shortcuts import redirect
from django.utils import timezone
from .models import TemporaryAccessToken


def consume_generation(view_func):
    """
    Декоратор для уменьшения счётчика генераций
    
    Применяется к views, которые выполняют генерацию контента.
    Для DEMO токенов уменьшает счетчик доступных генераций.
    Для платных токенов только обновляет статистику использования.
    
    Args:
        view_func: Функция представления для оборачивания
    
    Returns:
        Обёрнутая функция с проверкой и уменьшением счетчика
    
    Пример использования:
        @consume_generation
        def generate_content_view(request):
            # ваша логика генерации
            pass
    """
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Получаем токен из сессии
        token_str = request.session.get('access_token')
        
        if not token_str:
            # Нет токена - перенаправляем на страницу требования токена
            return redirect('token_required_page')
        
        try:
            # Получаем объект токена из базы данных
            token = TemporaryAccessToken.objects.get(
                token=token_str,
                is_active=True
            )
            
            # Проверяем срок действия
            if token.is_expired():
                # Токен истек - очищаем сессию и перенаправляем
                request.session.flush()
                return redirect('invalid_token_page')
            
            # Проверяем лимиты токенов GigaChat и OpenAI
            can_gc, gc_reason = token.can_use_gigachat()
            can_oa, oa_reason = token.can_use_openai()
            
            # Если оба лимита исчерпаны - перенаправляем на страницу лимита
            if not can_gc and not can_oa:
                return redirect('limit_exceeded_page')
            
            # Если только OpenAI исчерпан, но GigaChat доступен - показываем специальную страницу
            if not can_oa and can_gc:
                return redirect('openai_limit_exceeded_page')
            
            # Сохраняем токен в request для использования в views
            request.token = token
            
            # Получаем IP адрес пользователя
            ip_address = get_client_ip(request)
            
            # Обновляем статистику использования (legacy)
            token.consume_generation(ip_address=ip_address)
            
            # Обновляем данные в сессии
            request.session['gigachat_tokens_limit'] = token.gigachat_tokens_limit
            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
            request.session['openai_tokens_limit'] = token.openai_tokens_limit
            request.session['openai_tokens_used'] = token.openai_tokens_used
            request.session['total_used'] = token.total_used
            
        except TemporaryAccessToken.DoesNotExist:
            # Токен не найден - очищаем сессию
            request.session.flush()
            return redirect('invalid_token_page')
        
        # Выполняем оригинальную функцию представления
        return view_func(request, *args, **kwargs)
    
    return wrapper


def get_client_ip(request):
    """
    Получает IP адрес клиента из запроса
    
    Учитывает возможность работы за прокси-сервером или load balancer,
    проверяя заголовки X-Forwarded-For и X-Real-IP.
    
    Args:
        request: HTTP запрос
    
    Returns:
        str: IP адрес клиента
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Берем первый IP из списка (реальный клиент)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        # Прямое подключение без прокси
        ip = request.META.get('REMOTE_ADDR')
    return ip


def token_required(view_func):
    """
    Декоратор для проверки наличия активного токена
    
    Применяется к views, которые требуют аутентификации по токену,
    но не расходуют генерации (например, страницы профиля, настроек).
    
    Args:
        view_func: Функция представления для оборачивания
    
    Returns:
        Обёрнутая функция с проверкой токена
    
    Пример использования:
        @token_required
        def profile_view(request):
            # доступ к профилю
            pass
    """
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Получаем токен из сессии
        token_str = request.session.get('access_token')
        
        if not token_str:
            return redirect('token_required_page')
        
        try:
            # Проверяем существование и валидность токена
            token = TemporaryAccessToken.objects.get(
                token=token_str,
                is_active=True
            )
            
            # Проверяем срок действия
            if token.is_expired():
                request.session.flush()
                return redirect('invalid_token_page')
            
            # Добавляем информацию о токене в request для использования в view
            request.token = token
            
        except TemporaryAccessToken.DoesNotExist:
            request.session.flush()
            return redirect('invalid_token_page')
        
        # Выполняем оригинальную функцию
        return view_func(request, *args, **kwargs)
    
    return wrapper
