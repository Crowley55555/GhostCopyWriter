"""
Утилиты для работы с системой токенов и аутентификацией
"""

from django.utils import timezone
from .models import TemporaryAccessToken


def is_temporary_token_access(request):
    """
    Проверяет, использует ли пользователь временный токен для доступа
    
    ПРИМЕЧАНИЕ: Обычная Django аутентификация отключена, поэтому
    все пользователи используют временные токены (кроме админов).
    
    Args:
        request: HTTP запрос
    
    Returns:
        bool: True если используется временный токен, False если нет доступа
    """
    # Проверяем наличие токена в сессии
    token_str = request.session.get('access_token')
    if not token_str:
        return False
    
    # Проверяем что токен существует и активен
    try:
        token = TemporaryAccessToken.objects.get(
            token=token_str,
            is_active=True
        )
        return not token.is_expired()
    except TemporaryAccessToken.DoesNotExist:
        return False


def get_token_from_request(request):
    """
    Получает объект токена из запроса
    
    ПРИМЕЧАНИЕ: Обычная Django аутентификация отключена,
    поэтому все пользователи используют токены.
    
    Args:
        request: HTTP запрос
    
    Returns:
        TemporaryAccessToken или None
    """
    token_str = request.session.get('access_token')
    if not token_str:
        return None
    
    try:
        return TemporaryAccessToken.objects.get(
            token=token_str,
            is_active=True
        )
    except TemporaryAccessToken.DoesNotExist:
        return None


def get_user_for_generation(request):
    """
    Возвращает пользователя для сохранения генерации
    
    ПРИМЕЧАНИЕ: Обычная Django аутентификация отключена.
    Все пользователи используют временные токены, поэтому
    генерации сохраняются без привязки к пользователю (None).
    
    Args:
        request: HTTP запрос
    
    Returns:
        None (все генерации анонимные)
    """
    # Для временных токенов генерации сохраняются без привязки к пользователю
    return None


def is_demo_token(request):
    """
    Проверяет, используется ли бесплатный или скрытый токен
    
    Args:
        request: HTTP запрос
    
    Returns:
        bool: True если используется бесплатный или скрытый токен
    """
    token = get_token_from_request(request)
    if token:
        return token.token_type in ['DEMO_FREE', 'HIDDEN_14D', 'HIDDEN_30D']
    return False


def get_access_type(request):
    """
    Определяет тип доступа пользователя
    
    ПРИМЕЧАНИЕ: Обычная Django аутентификация отключена.
    Все пользователи используют временные токены.
    
    Args:
        request: HTTP запрос
    
    Returns:
        str: Тип токена в нижнем регистре или 'anonymous'
    """
    token = get_token_from_request(request)
    if token:
        return token.token_type.lower()
    
    return 'anonymous'
