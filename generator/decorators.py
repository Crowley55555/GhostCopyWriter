"""
Декораторы для системы токенов доступа

Предоставляет функциональность для управления лимитами генераций
и проверки прав доступа на основе временных токенов.
"""

from functools import wraps
from django.shortcuts import redirect
from django.utils import timezone
from .access import MSG_TOKEN_LIMIT, deny, get_client_ip, issue_or_get_registered_token  # get_client_ip — единая функция IP
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
        # Фаза 3: для залогиненого всегда REGISTERED-токен
        if request.user.is_authenticated:
            token = issue_or_get_registered_token(request.user)
        else:
            token_str = request.session.get('access_token')
            if not token_str:
                return redirect('token_required_page')
            try:
                token = TemporaryAccessToken.objects.get(
                    token=token_str,
                    is_active=True,
                )
            except TemporaryAccessToken.DoesNotExist:
                request.session.flush()
                return redirect('invalid_token_page')

        if token.is_expired():
            if request.user.is_authenticated:
                # У вошедшего истёкший токен выдаётся заново — без выхода
                token.is_active = False
                token.save(update_fields=['is_active'])
                token = issue_or_get_registered_token(request.user)
            else:
                request.session.flush()
                return redirect('invalid_token_page')

        # Проверяем лимиты токенов GigaChat и OpenAI
        can_gc, _ = token.can_use_gigachat()
        can_oa, _ = token.can_use_openai()

        # Если оба лимита исчерпаны - перенаправляем на страницу лимита (AJAX — JSON)
        if not can_gc and not can_oa:
            return deny(request, MSG_TOKEN_LIMIT, 429, 'limit_exceeded_page')

        # Редирект на openai_limit_exceeded только если OpenAI был в тарифе, но лимит исчерпан.
        # Для скрытых токенов (openai_tokens_limit == 0) не редиректим — страница генератора с заглушенным OpenAI.
        if token.openai_tokens_limit > 0 and not can_oa and can_gc:
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

        # Выполняем оригинальную функцию представления
        return view_func(request, *args, **kwargs)

    return wrapper


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
        # Фаза 3: залогиненому — всегда токен REGISTERED (без flush сессии
        # при любой проблеме). Демо-посетителю — как было
        if request.user.is_authenticated:
            token = issue_or_get_registered_token(request.user)
            if token.is_expired():
                token.is_active = False
                token.save(update_fields=['is_active'])
                token = issue_or_get_registered_token(request.user)
            request.token = token
            return view_func(request, *args, **kwargs)

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
