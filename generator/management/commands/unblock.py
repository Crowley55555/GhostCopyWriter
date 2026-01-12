"""
Management команда для разблокировки IP и токенов

Использование:
    python manage.py unblock --ip 192.168.1.1
    python manage.py unblock --token uuid-токена
    python manage.py unblock --all
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Разблокировка IP адресов или токенов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ip',
            type=str,
            help='IP адрес для разблокировки',
        )
        parser.add_argument(
            '--token',
            type=str,
            help='Токен для разблокировки',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Разблокировать все IP и токены',
        )

    def handle(self, *args, **options):
        if not any([options['ip'], options['token'], options['all']]):
            raise CommandError(
                'Укажите --ip, --token или --all. '
                'Используйте --help для справки.'
            )

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🔓 РАЗБЛОКИРОВКА'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')

        if options['all']:
            self._unblock_all()
        elif options['ip']:
            self._unblock_ip(options['ip'])
        elif options['token']:
            self._unblock_token(options['token'])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ Готово'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

    def _unblock_ip(self, ip):
        """Разблокировать конкретный IP"""
        cache_key = f'blocked_ip:{ip}'
        
        # Проверяем, заблокирован ли
        block_data = cache.get(cache_key)
        if not block_data:
            self.stdout.write(self.style.WARNING(
                f'⚠️  IP {ip} не был заблокирован'
            ))
            return

        # Показываем информацию о блокировке
        if isinstance(block_data, dict):
            self.stdout.write(f'📋 Информация о блокировке:')
            self.stdout.write(f'   IP: {ip}')
            self.stdout.write(f'   Причина: {block_data.get("reason", "Unknown")}')
            self.stdout.write(f'   Заблокирован: {block_data.get("blocked_at", "Unknown")}')
            self.stdout.write('')

        # Удаляем блокировку
        cache.delete(cache_key)
        
        # Очищаем также счетчик неудачных попыток
        cache.delete(f'failed_attempts:ip:{ip}')
        
        self.stdout.write(self.style.SUCCESS(f'✅ IP {ip} разблокирован'))

    def _unblock_token(self, token):
        """Разблокировать конкретный токен"""
        cache_key = f'blocked_token:{token}'
        
        # Проверяем, заблокирован ли
        block_data = cache.get(cache_key)
        if not block_data:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Токен не был заблокирован'
            ))
            return

        # Показываем информацию о блокировке
        masked_token = f'{token[:8]}...{token[-8:]}'
        if isinstance(block_data, dict):
            self.stdout.write(f'📋 Информация о блокировке:')
            self.stdout.write(f'   Токен: {masked_token}')
            self.stdout.write(f'   Причина: {block_data.get("reason", "Unknown")}')
            self.stdout.write(f'   Заблокирован: {block_data.get("blocked_at", "Unknown")}')
            self.stdout.write('')

        # Удаляем блокировку
        cache.delete(cache_key)
        
        # Очищаем также счетчик неудачных попыток
        cache.delete(f'failed_attempts:token:{token}')
        
        self.stdout.write(self.style.SUCCESS(f'✅ Токен {masked_token} разблокирован'))

    def _unblock_all(self):
        """Разблокировать все IP и токены"""
        self.stdout.write(self.style.WARNING(
            '⚠️  ВНИМАНИЕ: Будут разблокированы ВСЕ IP адреса и токены!'
        ))
        
        confirm = input('Продолжить? (yes/no): ')
        if confirm.lower() not in ['yes', 'y', 'да']:
            self.stdout.write(self.style.ERROR('❌ Отменено'))
            return

        self.stdout.write('')
        self.stdout.write('🔄 Разблокировка...')
        self.stdout.write('')

        # Подсчитываем количество
        ip_count = 0
        token_count = 0

        try:
            # Пытаемся получить все ключи
            try:
                all_keys = list(cache.keys('blocked_*'))
            except AttributeError:
                # LocMemCache
                try:
                    all_keys = [k for k in cache._cache.keys() if k.startswith('blocked_')]
                except:
                    all_keys = []

            for key in all_keys:
                if key.startswith('blocked_ip:'):
                    ip_count += 1
                elif key.startswith('blocked_token:'):
                    token_count += 1
                cache.delete(key)

            # Очищаем также счетчики неудачных попыток
            try:
                failed_keys = list(cache.keys('failed_attempts:*'))
            except AttributeError:
                try:
                    failed_keys = [k for k in cache._cache.keys() if k.startswith('failed_attempts:')]
                except:
                    failed_keys = []

            for key in failed_keys:
                cache.delete(key)

            self.stdout.write(self.style.SUCCESS(
                f'✅ Разблокировано IP: {ip_count}'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'✅ Разблокировано токенов: {token_count}'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'✅ Очищено счетчиков: {len(failed_keys)}'
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка: {e}'))
