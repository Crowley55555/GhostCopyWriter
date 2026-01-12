"""
Middleware для безопасности

Применяет глобальные проверки безопасности ко всем запросам
"""

import logging
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from ipware import get_client_ip

from .security import (
    RateLimiter, 
    BlockList, 
    SecurityMonitor,
    log_security_event
)

logger = logging.getLogger('security')


class SecurityMiddleware(MiddlewareMixin):
    """
    Глобальный middleware для проверок безопасности
    
    Применяется ко всем запросам:
    - Проверка блокировки IP
    - Rate limiting
    - Логирование подозрительной активности
    """
    
    # Пути, которые не требуют проверки (статика, медиа)
    EXEMPT_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/robots.txt',
    ]
    
    def process_request(self, request):
        """Обработка входящего запроса"""
        
        # Пропускаем проверку для exempt путей
        if any(request.path.startswith(path) for path in self.EXEMPT_PATHS):
            return None
        
        # Получаем IP клиента
        client_ip, is_routable = get_client_ip(request)
        
        # Проверка 1: IP в черном списке
        if BlockList.is_ip_blocked(client_ip):
            block_info = BlockList.get_blocked_info(client_ip)
            
            log_security_event(
                'blocked_access',
                f"ip:{client_ip}",
                {
                    'path': request.path,
                    'method': request.method,
                    'block_info': block_info
                },
                'WARNING'
            )
            
            return JsonResponse({
                'error': 'Access Denied',
                'message': 'Ваш IP адрес временно заблокирован из-за подозрительной активности.',
                'reason': block_info.get('reason', 'Unknown'),
                'expires_at': block_info.get('expires_at', 'Unknown')
            }, status=403)
        
        # Проверка 2: Глобальный rate limit
        # Для API эндпоинтов используем более строгий лимит
        if request.path.startswith('/api/'):
            max_per_minute = 30
        elif request.path.startswith('/generator/'):
            max_per_minute = 20
        else:
            max_per_minute = 60
        
        limit_response = RateLimiter.check_rate_limit(request, max_per_minute)
        if limit_response:
            identifier = RateLimiter.get_client_identifier(request)
            log_security_event(
                'rate_limit_exceeded',
                identifier,
                {
                    'path': request.path,
                    'method': request.method,
                    'limit': max_per_minute
                },
                'WARNING'
            )
            return limit_response
        
        # Проверка 3: Подозрительные User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if self._is_suspicious_user_agent(user_agent):
            identifier = RateLimiter.get_client_identifier(request)
            SecurityMonitor.log_suspicious_activity(
                identifier,
                'suspicious_user_agent',
                f"User-Agent: {user_agent}"
            )
        
        # Проверка 4: Необычные HTTP методы
        if request.method not in ['GET', 'POST', 'HEAD', 'OPTIONS']:
            identifier = RateLimiter.get_client_identifier(request)
            SecurityMonitor.log_suspicious_activity(
                identifier,
                'unusual_http_method',
                f"Method: {request.method}, Path: {request.path}"
            )
        
        return None
    
    def process_response(self, request, response):
        """Добавление заголовков безопасности в ответ"""
        
        # Добавляем security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy
        if not request.path.startswith('/admin/'):
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self';"
            )
        
        # Rate limit информация в заголовках (для API)
        if request.path.startswith('/api/'):
            identifier = RateLimiter.get_client_identifier(request)
            # Не вызываем проверку снова, просто добавляем информационные заголовки
            response['X-RateLimit-Limit'] = '30'
        
        return response
    
    def _is_suspicious_user_agent(self, user_agent):
        """Проверить, подозрительный ли User-Agent"""
        if not user_agent:
            return True
        
        # Известные боты/сканеры
        suspicious_agents = [
            'sqlmap',
            'nikto',
            'nmap',
            'masscan',
            'nessus',
            'openvas',
            'metasploit',
            'burp',
            'zaproxy',
            'acunetix',
            'w3af'
        ]
        
        user_agent_lower = user_agent.lower()
        return any(agent in user_agent_lower for agent in suspicious_agents)


class TokenSecurityMiddleware(MiddlewareMixin):
    """
    Middleware для проверки безопасности токенов
    
    Применяется после TokenAccessMiddleware
    """
    
    def process_request(self, request):
        """Проверка безопасности токена"""
        
        # Проверяем только если есть токен в сессии
        token_str = request.session.get('access_token')
        if not token_str:
            return None
        
        # Проверяем, не заблокирован ли токен
        if BlockList.is_token_blocked(token_str):
            block_info = BlockList.get_blocked_info(token_str)
            
            log_security_event(
                'blocked_token_access',
                f"token:{token_str}",
                {
                    'path': request.path,
                    'block_info': block_info
                },
                'WARNING'
            )
            
            # Очищаем сессию
            request.session.flush()
            
            return JsonResponse({
                'error': 'Token Blocked',
                'message': 'Ваш токен заблокирован.',
                'reason': block_info.get('reason', 'Security violation')
            }, status=403)
        
        return None


class AuditLogMiddleware(MiddlewareMixin):
    """
    Middleware для аудита запросов
    
    Логирует все важные действия для анализа
    """
    
    # Пути, которые требуют аудита
    AUDIT_PATHS = [
        '/api/create-token/',
        '/api/generate/',
        '/auth/token/',
        '/telegram/webhook/',
    ]
    
    def process_request(self, request):
        """Логирование запроса"""
        
        # Проверяем, нужно ли логировать этот путь
        should_audit = any(
            request.path.startswith(path) 
            for path in self.AUDIT_PATHS
        )
        
        if should_audit:
            client_ip, _ = get_client_ip(request)
            identifier = RateLimiter.get_client_identifier(request)
            
            log_data = {
                'path': request.path,
                'method': request.method,
                'ip': client_ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'referer': request.META.get('HTTP_REFERER', ''),
            }
            
            # Для POST запросов логируем ключи (но не значения!)
            if request.method == 'POST':
                log_data['post_keys'] = list(request.POST.keys())
            
            log_security_event(
                'audit',
                identifier,
                log_data,
                'INFO'
            )
        
        return None
    
    def process_response(self, request, response):
        """Логирование ответа"""
        
        # Логируем ошибки
        if response.status_code >= 400:
            client_ip, _ = get_client_ip(request)
            identifier = RateLimiter.get_client_identifier(request)
            
            log_security_event(
                'error_response',
                identifier,
                {
                    'path': request.path,
                    'status_code': response.status_code,
                    'method': request.method,
                    'ip': client_ip
                },
                'WARNING' if response.status_code < 500 else 'ERROR'
            )
        
        return response
