"""
Модуль безопасности для Ghostwriter

Включает:
- Rate limiting
- IP блокировка
- Обнаружение подозрительной активности
- Защита от брутфорса
- Логирование безопасности
"""

import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from ipware import get_client_ip

logger = logging.getLogger('security')


# =============================================================================
# КОНСТАНТЫ БЕЗОПАСНОСТИ
# =============================================================================

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 60
MAX_REQUESTS_PER_HOUR = 1000
MAX_GENERATIONS_PER_HOUR = 50

# Блокировка
MAX_FAILED_ATTEMPTS = 5
BLOCK_DURATION_MINUTES = 30
SUSPICIOUS_ACTIVITY_THRESHOLD = 10

# Webhook безопасность
WEBHOOK_RATE_LIMIT = 100  # запросов в минуту


# =============================================================================
# КЛАСС ДЛЯ RATE LIMITING
# =============================================================================

class RateLimiter:
    """
    Класс для ограничения частоты запросов (Rate Limiting)
    Использует Redis/Cache для хранения счетчиков
    """
    
    @staticmethod
    def get_client_identifier(request):
        """Получить уникальный идентификатор клиента"""
        # Пытаемся получить IP
        client_ip, is_routable = get_client_ip(request)
        
        # Если есть токен в сессии, используем его
        token = request.session.get('access_token')
        if token:
            return f"token:{token}"
        
        # Иначе используем IP
        return f"ip:{client_ip or 'unknown'}"
    
    @staticmethod
    def is_rate_limited(identifier, max_requests, window_seconds):
        """
        Проверить, не превышен ли лимит запросов
        
        Args:
            identifier: Уникальный идентификатор клиента
            max_requests: Максимальное количество запросов
            window_seconds: Временное окно в секундах
        
        Returns:
            (is_limited, remaining, reset_time)
        """
        cache_key = f"ratelimit:{identifier}:{window_seconds}"
        
        # Получаем текущий счетчик
        current = cache.get(cache_key, 0)
        
        if current >= max_requests:
            # Лимит превышен
            ttl = cache.ttl(cache_key) or window_seconds
            reset_time = datetime.now() + timedelta(seconds=ttl)
            return True, 0, reset_time
        
        # Увеличиваем счетчик
        if current == 0:
            cache.set(cache_key, 1, window_seconds)
        else:
            cache.incr(cache_key)
        
        remaining = max_requests - current - 1
        reset_time = datetime.now() + timedelta(seconds=window_seconds)
        
        return False, remaining, reset_time
    
    @staticmethod
    def check_rate_limit(request, max_per_minute=MAX_REQUESTS_PER_MINUTE):
        """
        Проверить rate limit для запроса
        
        Returns:
            None если OK, JsonResponse если превышен лимит
        """
        identifier = RateLimiter.get_client_identifier(request)
        
        # Проверяем минутный лимит
        is_limited, remaining, reset_time = RateLimiter.is_rate_limited(
            identifier, max_per_minute, 60
        )
        
        if is_limited:
            logger.warning(
                f"Rate limit exceeded for {identifier}. "
                f"Reset at {reset_time}"
            )
            return JsonResponse({
                'error': 'Too many requests',
                'message': 'Вы превысили лимит запросов. Попробуйте позже.',
                'retry_after': int((reset_time - datetime.now()).total_seconds())
            }, status=429)
        
        return None


# =============================================================================
# СИСТЕМА БЛОКИРОВКИ IP И ТОКЕНОВ
# =============================================================================

class BlockList:
    """Управление черным списком IP и токенов"""
    
    @staticmethod
    def block_ip(ip, reason, duration_minutes=BLOCK_DURATION_MINUTES):
        """Заблокировать IP адрес"""
        cache_key = f"blocked_ip:{ip}"
        cache.set(cache_key, {
            'reason': reason,
            'blocked_at': timezone.now().isoformat(),
            'expires_at': (timezone.now() + timedelta(minutes=duration_minutes)).isoformat()
        }, duration_minutes * 60)
        
        logger.warning(f"IP {ip} blocked for {duration_minutes} minutes. Reason: {reason}")
    
    @staticmethod
    def is_ip_blocked(ip):
        """Проверить, заблокирован ли IP"""
        cache_key = f"blocked_ip:{ip}"
        blocked_data = cache.get(cache_key)
        return blocked_data is not None
    
    @staticmethod
    def block_token(token, reason):
        """Заблокировать токен навсегда"""
        cache_key = f"blocked_token:{token}"
        cache.set(cache_key, {
            'reason': reason,
            'blocked_at': timezone.now().isoformat()
        }, None)  # Бессрочно
        
        logger.critical(f"Token {token} permanently blocked. Reason: {reason}")
    
    @staticmethod
    def is_token_blocked(token):
        """Проверить, заблокирован ли токен"""
        cache_key = f"blocked_token:{token}"
        return cache.get(cache_key) is not None
    
    @staticmethod
    def get_blocked_info(identifier):
        """Получить информацию о блокировке"""
        # Проверяем IP
        ip_key = f"blocked_ip:{identifier}"
        ip_data = cache.get(ip_key)
        if ip_data:
            return ip_data
        
        # Проверяем токен
        token_key = f"blocked_token:{identifier}"
        token_data = cache.get(token_key)
        if token_data:
            return token_data
        
        return None


# =============================================================================
# ОБНАРУЖЕНИЕ ПОДОЗРИТЕЛЬНОЙ АКТИВНОСТИ
# =============================================================================

class SecurityMonitor:
    """Мониторинг и обнаружение подозрительной активности"""
    
    @staticmethod
    def log_failed_attempt(identifier, reason):
        """Залогировать неудачную попытку доступа"""
        cache_key = f"failed_attempts:{identifier}"
        
        attempts = cache.get(cache_key, 0)
        attempts += 1
        
        # Сохраняем на 1 час
        cache.set(cache_key, attempts, 3600)
        
        logger.warning(f"Failed attempt #{attempts} for {identifier}. Reason: {reason}")
        
        # Если превышен порог - блокируем
        if attempts >= MAX_FAILED_ATTEMPTS:
            if identifier.startswith('ip:'):
                ip = identifier.split(':', 1)[1]
                BlockList.block_ip(ip, f"Too many failed attempts ({attempts})")
            elif identifier.startswith('token:'):
                token = identifier.split(':', 1)[1]
                BlockList.block_token(token, f"Too many failed attempts ({attempts})")
            
            return True  # Заблокирован
        
        return False  # Еще не заблокирован
    
    @staticmethod
    def log_suspicious_activity(identifier, activity_type, details):
        """Залогировать подозрительную активность"""
        cache_key = f"suspicious:{identifier}:{activity_type}"
        
        count = cache.get(cache_key, 0)
        count += 1
        cache.set(cache_key, count, 3600)
        
        logger.warning(
            f"Suspicious activity detected: {activity_type} "
            f"from {identifier}. Count: {count}. Details: {details}"
        )
        
        # Если слишком много подозрительной активности
        if count >= SUSPICIOUS_ACTIVITY_THRESHOLD:
            if identifier.startswith('ip:'):
                ip = identifier.split(':', 1)[1]
                BlockList.block_ip(
                    ip, 
                    f"Suspicious activity: {activity_type} (count: {count})"
                )
    
    @staticmethod
    def check_token_validity(token_obj, request):
        """
        Проверить валидность токена и обнаружить аномалии
        
        Returns:
            (is_valid, error_message)
        """
        # Проверка 1: Токен в черном списке
        if BlockList.is_token_blocked(str(token_obj.token)):
            block_info = BlockList.get_blocked_info(str(token_obj.token))
            return False, f"Токен заблокирован: {block_info.get('reason', 'Unknown')}"
        
        # Проверка 2: Истек срок действия
        if token_obj.is_expired():
            return False, "Срок действия токена истек"
        
        # Проверка 3: Токен деактивирован
        if not token_obj.is_active:
            return False, "Токен деактивирован"
        
        # Проверка 4: Необычная активность (слишком много запросов)
        identifier = f"token:{token_obj.token}"
        
        # Проверяем лимит генераций в час
        is_limited, remaining, reset_time = RateLimiter.is_rate_limited(
            identifier, MAX_GENERATIONS_PER_HOUR, 3600
        )
        
        if is_limited:
            SecurityMonitor.log_suspicious_activity(
                identifier,
                'excessive_generations',
                f'Exceeded {MAX_GENERATIONS_PER_HOUR} generations per hour'
            )
            return False, f"Превышен лимит генераций. Попробуйте через {int((reset_time - datetime.now()).total_seconds() / 60)} минут"
        
        return True, None


# =============================================================================
# ЗАЩИТА WEBHOOK
# =============================================================================

class WebhookSecurity:
    """Безопасность для Telegram webhook"""
    
    @staticmethod
    def verify_telegram_request(request, secret_token):
        """
        Верифицировать запрос от Telegram
        
        Args:
            request: Django request объект
            secret_token: Секретный токен из настроек
        
        Returns:
            (is_valid, error_message)
        """
        # Проверка 1: Метод должен быть POST
        if request.method != 'POST':
            return False, "Invalid request method"
        
        # Проверка 2: Secret token в заголовке
        token_header = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if token_header != secret_token:
            logger.warning(
                f"Invalid webhook secret token from IP: "
                f"{get_client_ip(request)[0]}"
            )
            return False, "Invalid secret token"
        
        # Проверка 3: Rate limiting для webhook
        client_ip, _ = get_client_ip(request)
        identifier = f"webhook:{client_ip}"
        
        is_limited, remaining, reset_time = RateLimiter.is_rate_limited(
            identifier, WEBHOOK_RATE_LIMIT, 60
        )
        
        if is_limited:
            return False, f"Webhook rate limit exceeded"
        
        return True, None
    
    @staticmethod
    def validate_telegram_update(update_data):
        """
        Валидировать структуру update от Telegram
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(update_data, dict):
            return False, "Invalid update format"
        
        if 'update_id' not in update_data:
            return False, "Missing update_id"
        
        # Проверяем, что есть хотя бы одно поле с данными
        valid_fields = ['message', 'edited_message', 'callback_query', 
                       'inline_query', 'chosen_inline_result']
        
        if not any(field in update_data for field in valid_fields):
            return False, "No valid data fields in update"
        
        return True, None


# =============================================================================
# ЗАЩИТА ОТ SQL INJECTION И XSS
# =============================================================================

class InputSanitizer:
    """Очистка и валидация пользовательского ввода"""
    
    @staticmethod
    def sanitize_text(text, max_length=5000):
        """
        Очистить текст от потенциально опасных символов
        
        Args:
            text: Входной текст
            max_length: Максимальная длина
        
        Returns:
            Очищенный текст
        """
        if not text:
            return ""
        
        # Обрезаем по длине
        text = str(text)[:max_length]
        
        # Убираем null bytes
        text = text.replace('\x00', '')
        
        # Убираем управляющие символы (кроме переносов строк и табов)
        text = ''.join(char for char in text 
                      if char.isprintable() or char in '\n\r\t')
        
        return text.strip()
    
    @staticmethod
    def validate_uuid(uuid_string):
        """Валидировать UUID токена"""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(str(uuid_string)))
    
    @staticmethod
    def validate_platform(platform):
        """Валидировать платформу социальной сети"""
        VALID_PLATFORMS = [
            'vk', 'dzen', 'telegram', 'tiktok', 
            'instagram', 'facebook', 'twitter', 'linkedin'
        ]
        return platform.lower() in VALID_PLATFORMS
    
    @staticmethod
    def is_suspicious_input(text):
        """
        Проверить, содержит ли текст подозрительные паттерны
        
        Returns:
            (is_suspicious, reason)
        """
        import re
        
        # SQL injection паттерны
        sql_patterns = [
            r'(\bUNION\b.*\bSELECT\b)',
            r'(\bDROP\b.*\bTABLE\b)',
            r'(\bINSERT\b.*\bINTO\b)',
            r'(\bDELETE\b.*\bFROM\b)',
            r'(--|\#|\/\*)',
            r'(\bOR\b.*=.*)',
            r'(\bAND\b.*=.*)',
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"Potential SQL injection: {pattern}"
        
        # XSS паттерны
        xss_patterns = [
            r'<script[^>]*>',
            r'javascript:',
            r'onerror\s*=',
            r'onclick\s*=',
            r'<iframe[^>]*>',
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"Potential XSS: {pattern}"
        
        # Чрезмерное количество специальных символов
        special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
        if special_char_ratio > 0.5:
            return True, f"Too many special characters ({special_char_ratio:.1%})"
        
        return False, None


# =============================================================================
# ЛОГИРОВАНИЕ БЕЗОПАСНОСТИ
# =============================================================================

def log_security_event(event_type, identifier, details, severity='INFO'):
    """
    Централизованное логирование событий безопасности
    
    Args:
        event_type: Тип события (login, failed_login, block, etc.)
        identifier: Идентификатор (IP, токен, пользователь)
        details: Детали события
        severity: Уровень серьезности (INFO, WARNING, ERROR, CRITICAL)
    """
    log_entry = {
        'timestamp': timezone.now().isoformat(),
        'event_type': event_type,
        'identifier': identifier,
        'details': details,
        'severity': severity
    }
    
    # Выбираем метод логирования в зависимости от серьезности
    if severity == 'CRITICAL':
        logger.critical(f"SECURITY: {log_entry}")
    elif severity == 'ERROR':
        logger.error(f"SECURITY: {log_entry}")
    elif severity == 'WARNING':
        logger.warning(f"SECURITY: {log_entry}")
    else:
        logger.info(f"SECURITY: {log_entry}")
    
    # Сохраняем в кеш для последующего анализа
    cache_key = f"security_log:{event_type}:{int(time.time())}"
    cache.set(cache_key, log_entry, 86400)  # 24 часа


# =============================================================================
# ДЕКОРАТОРЫ ДЛЯ ЗАЩИТЫ VIEW
# =============================================================================

from functools import wraps

def rate_limit(max_per_minute=MAX_REQUESTS_PER_MINUTE):
    """Декоратор для rate limiting view"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Проверяем rate limit
            limit_response = RateLimiter.check_rate_limit(request, max_per_minute)
            if limit_response:
                return limit_response
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def check_ip_block(view_func):
    """Декоратор для проверки блокировки IP"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        client_ip, _ = get_client_ip(request)
        
        if BlockList.is_ip_blocked(client_ip):
            block_info = BlockList.get_blocked_info(client_ip)
            log_security_event(
                'blocked_access_attempt',
                f"ip:{client_ip}",
                f"Attempted access while blocked: {block_info}",
                'WARNING'
            )
            return HttpResponseForbidden(
                "Ваш IP адрес временно заблокирован из-за подозрительной активности. "
                "Пожалуйста, попробуйте позже."
            )
        
        return view_func(request, *args, **kwargs)
    return wrapped_view


def sanitize_input(view_func):
    """Декоратор для очистки пользовательского ввода"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Проверяем POST данные
        if request.method == 'POST':
            for key, value in request.POST.items():
                if isinstance(value, str):
                    is_suspicious, reason = InputSanitizer.is_suspicious_input(value)
                    if is_suspicious:
                        identifier = RateLimiter.get_client_identifier(request)
                        SecurityMonitor.log_suspicious_activity(
                            identifier,
                            'malicious_input',
                            f"Key: {key}, Reason: {reason}"
                        )
                        return JsonResponse({
                            'error': 'Invalid input',
                            'message': 'Обнаружен потенциально опасный ввод'
                        }, status=400)
        
        return view_func(request, *args, **kwargs)
    return wrapped_view
