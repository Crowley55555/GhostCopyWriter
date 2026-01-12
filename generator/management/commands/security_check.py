"""
Management команда для проверки состояния безопасности

Использование:
    python manage.py security_check
    python manage.py security_check --detailed
    python manage.py security_check --blocked-only
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings
import json


class Command(BaseCommand):
    help = 'Проверка состояния системы безопасности'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Показать детальную информацию',
        )
        parser.add_argument(
            '--blocked-only',
            action='store_true',
            help='Показать только заблокированные IP и токены',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🔒 GHOSTWRITER SECURITY CHECK'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        # Проверка настроек
        if not options['blocked_only']:
            self._check_settings()
            self.stdout.write('')

        # Проверка блокировок
        self._check_blocked_ips(options['detailed'])
        self.stdout.write('')
        
        self._check_blocked_tokens(options['detailed'])
        self.stdout.write('')

        # Проверка последних событий безопасности
        if options['detailed'] and not options['blocked_only']:
            self._check_security_events()
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ Проверка завершена'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

    def _check_settings(self):
        """Проверка настроек безопасности"""
        self.stdout.write(self.style.HTTP_INFO('📋 Настройки безопасности:'))
        self.stdout.write('')

        # DEBUG режим
        debug = getattr(settings, 'DEBUG', True)
        if debug:
            self.stdout.write(self.style.WARNING(
                '  ⚠️  DEBUG=True (небезопасно для production!)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ DEBUG=False'))

        # HTTPS настройки
        ssl_redirect = getattr(settings, 'SECURE_SSL_REDIRECT', False)
        if ssl_redirect:
            self.stdout.write(self.style.SUCCESS('  ✅ SSL Redirect включен'))
        else:
            self.stdout.write(self.style.WARNING('  ⚠️  SSL Redirect выключен'))

        # Session security
        session_secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)
        if session_secure:
            self.stdout.write(self.style.SUCCESS('  ✅ Secure Session Cookies'))
        else:
            self.stdout.write(self.style.WARNING('  ⚠️  Session Cookies не secure'))

        # HSTS
        hsts = getattr(settings, 'SECURE_HSTS_SECONDS', 0)
        if hsts > 0:
            self.stdout.write(self.style.SUCCESS(f'  ✅ HSTS включен ({hsts}s)'))
        else:
            self.stdout.write(self.style.WARNING('  ⚠️  HSTS выключен'))

        # Rate limiting
        max_per_min = getattr(settings, 'MAX_REQUESTS_PER_MINUTE', 60)
        self.stdout.write(f'  📊 Rate Limit: {max_per_min} req/min')

        # Cache backend
        cache_backend = settings.CACHES['default']['BACKEND']
        if 'redis' in cache_backend.lower():
            self.stdout.write(self.style.SUCCESS(f'  ✅ Cache: Redis'))
        else:
            self.stdout.write(self.style.WARNING(
                f'  ⚠️  Cache: {cache_backend.split(".")[-1]} '
                f'(рекомендуется Redis для production)'
            ))

    def _check_blocked_ips(self, detailed=False):
        """Проверка заблокированных IP"""
        self.stdout.write(self.style.HTTP_INFO('🚫 Заблокированные IP адреса:'))
        self.stdout.write('')

        try:
            # Получаем все ключи с заблокированными IP
            blocked_keys = []
            # Пробуем разные методы в зависимости от backend
            try:
                blocked_keys = list(cache.keys('blocked_ip:*'))
            except AttributeError:
                # LocMemCache не поддерживает keys(), используем iter_keys
                try:
                    blocked_keys = [k for k in cache._cache.keys() if k.startswith('blocked_ip:')]
                except:
                    pass

            if not blocked_keys:
                self.stdout.write(self.style.SUCCESS('  ✅ Нет заблокированных IP'))
                return

            self.stdout.write(self.style.WARNING(
                f'  ⚠️  Найдено заблокированных IP: {len(blocked_keys)}'
            ))
            self.stdout.write('')

            for key in blocked_keys:
                ip = key.replace('blocked_ip:', '')
                block_data = cache.get(key)
                
                if block_data:
                    self.stdout.write(f'  🔴 {ip}')
                    if detailed and isinstance(block_data, dict):
                        self.stdout.write(f'     Причина: {block_data.get("reason", "Unknown")}')
                        self.stdout.write(f'     Заблокирован: {block_data.get("blocked_at", "Unknown")}')
                        if 'expires_at' in block_data:
                            self.stdout.write(f'     Истекает: {block_data.get("expires_at")}')
                    self.stdout.write('')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Ошибка при проверке: {e}'))

    def _check_blocked_tokens(self, detailed=False):
        """Проверка заблокированных токенов"""
        self.stdout.write(self.style.HTTP_INFO('🎫 Заблокированные токены:'))
        self.stdout.write('')

        try:
            blocked_keys = []
            try:
                blocked_keys = list(cache.keys('blocked_token:*'))
            except AttributeError:
                try:
                    blocked_keys = [k for k in cache._cache.keys() if k.startswith('blocked_token:')]
                except:
                    pass

            if not blocked_keys:
                self.stdout.write(self.style.SUCCESS('  ✅ Нет заблокированных токенов'))
                return

            self.stdout.write(self.style.WARNING(
                f'  ⚠️  Найдено заблокированных токенов: {len(blocked_keys)}'
            ))
            self.stdout.write('')

            for key in blocked_keys:
                token = key.replace('blocked_token:', '')
                block_data = cache.get(key)
                
                if block_data:
                    # Показываем только первые и последние 4 символа токена
                    masked_token = f'{token[:8]}...{token[-8:]}'
                    self.stdout.write(f'  🔴 {masked_token}')
                    if detailed and isinstance(block_data, dict):
                        self.stdout.write(f'     Причина: {block_data.get("reason", "Unknown")}')
                        self.stdout.write(f'     Заблокирован: {block_data.get("blocked_at", "Unknown")}')
                    self.stdout.write('')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Ошибка при проверке: {e}'))

    def _check_security_events(self):
        """Проверка последних событий безопасности"""
        self.stdout.write(self.style.HTTP_INFO('📊 Последние события безопасности:'))
        self.stdout.write('')

        try:
            event_keys = []
            try:
                event_keys = list(cache.keys('security_log:*'))
            except AttributeError:
                try:
                    event_keys = [k for k in cache._cache.keys() if k.startswith('security_log:')]
                except:
                    pass

            if not event_keys:
                self.stdout.write('  ℹ️  Нет записей о событиях (или кеш очищен)')
                return

            # Берем последние 10 событий
            recent_events = sorted(event_keys, reverse=True)[:10]

            for key in recent_events:
                event = cache.get(key)
                if event and isinstance(event, dict):
                    severity = event.get('severity', 'INFO')
                    event_type = event.get('event_type', 'unknown')
                    timestamp = event.get('timestamp', 'unknown')
                    
                    # Цвет в зависимости от серьезности
                    if severity == 'CRITICAL':
                        style = self.style.ERROR
                    elif severity == 'WARNING':
                        style = self.style.WARNING
                    else:
                        style = self.style.SUCCESS
                    
                    self.stdout.write(style(
                        f'  [{severity}] {event_type} - {timestamp}'
                    ))
                    
                    details = event.get('details', {})
                    if isinstance(details, dict):
                        for k, v in details.items():
                            self.stdout.write(f'    {k}: {v}')
                    
                    self.stdout.write('')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Ошибка при проверке: {e}'))
