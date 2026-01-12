"""
Команда для создания бессрочного токена разработчика

Использование:
    python manage.py create_dev_token
    python manage.py create_dev_token --name="Артём Лавров"
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from generator.models import TemporaryAccessToken


class Command(BaseCommand):
    """
    Команда для создания DEVELOPER токена без ограничений
    
    DEVELOPER токены:
    - Бессрочные (expires_at установлен на +100 лет)
    - Безлимитные генерации
    - Не деактивируются автоматически
    - Идеальны для разработки и тестирования
    """
    
    help = 'Создает бессрочный токен разработчика с неограниченными генерациями'
    
    def add_arguments(self, parser):
        """Добавляет аргументы командной строки"""
        parser.add_argument(
            '--name',
            type=str,
            default='Developer',
            help='Имя разработчика для идентификации токена',
        )
        
        parser.add_argument(
            '--list',
            action='store_true',
            help='Показать все существующие DEVELOPER токены',
        )
        
        parser.add_argument(
            '--deactivate',
            type=str,
            help='Деактивировать DEVELOPER токен по UUID',
        )
    
    def handle(self, *args, **options):
        """Основная логика команды"""
        
        # Показать список существующих токенов
        if options['list']:
            self._list_developer_tokens()
            return
        
        # Деактивировать токен
        if options['deactivate']:
            self._deactivate_token(options['deactivate'])
            return
        
        # Создать новый DEVELOPER токен
        self._create_developer_token(options['name'])
    
    def _create_developer_token(self, name):
        """Создает новый DEVELOPER токен"""
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('>> Создание токена разработчика'))
        self.stdout.write('=' * 70)
        
        # Создаем токен с очень далёкой датой истечения (100 лет)
        expires_at = timezone.now() + timedelta(days=365 * 100)
        
        token = TemporaryAccessToken.objects.create(
            token_type='DEVELOPER',
            expires_at=expires_at,
            daily_generations_left=0,  # Не используется для DEVELOPER
            is_active=True
        )
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('>> DEVELOPER token uspeshno sozdan!'))
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'\nRazrabotchik: {name}')
        self.stdout.write(f'Token: {token.token}')
        self.stdout.write(f'Tip: {token.get_token_type_display()}')
        self.stdout.write(f'Sozdan: {token.created_at.strftime("%d.%m.%Y %H:%M:%S")}')
        self.stdout.write(f'Istekaet: {token.expires_at.strftime("%d.%m.%Y")} (bessrochniy)')
        self.stdout.write(f'Aktiven: Da')
        self.stdout.write(f'Limit generaciy: Bezlimit')
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.WARNING('>> VASHA SSYLKA DOSTUPA:'))
        self.stdout.write('=' * 70)
        
        # Формируем ссылку
        link = f'http://localhost:8000/auth/token/{token.token}/'
        
        self.stdout.write(f'\n{link}\n')
        
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('>> INSTRUKCII:'))
        self.stdout.write('=' * 70)
        
        self.stdout.write('\n1. Skopiruyte ssylku vyshe')
        self.stdout.write('2. Otkroyte v brauzere')
        self.stdout.write('3. Nachnite rabotu bez ogranicheniy!')
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.WARNING('>> VAZHNO:'))
        self.stdout.write('=' * 70)
        
        self.stdout.write('\n- Etot token BESSROCHNIY - ne istechet')
        self.stdout.write('- Generacii BEZLIMITNYE - bez ogranicheniy')
        self.stdout.write('- Sohranite ssylku v nadezhnom meste')
        self.stdout.write('- Ne delites tokenom s drugimi')
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('>> Gotovo k ispolzovaniyu!'))
        self.stdout.write('=' * 70 + '\n')
    
    def _list_developer_tokens(self):
        """Показывает все DEVELOPER токены"""
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('>> Spisok DEVELOPER tokenov'))
        self.stdout.write('=' * 70 + '\n')
        
        tokens = TemporaryAccessToken.objects.filter(token_type='DEVELOPER')
        
        if not tokens.exists():
            self.stdout.write(
                self.style.WARNING('>> DEVELOPER tokeny ne naydeny.\n')
            )
            self.stdout.write('Sozdayte token: python manage.py create_dev_token\n')
            return
        
        for i, token in enumerate(tokens, 1):
            status = '[OK] Aktiven' if token.is_active else '[X] Deaktivirovan'
            
            self.stdout.write(f'{i}. {status}')
            self.stdout.write(f'   Token: {token.token}')
            self.stdout.write(f'   Sozdan: {token.created_at.strftime("%d.%m.%Y %H:%M")}')
            self.stdout.write(f'   Ispolzovan: {token.total_used} raz')
            self.stdout.write(f'   Poslednee ispolzovanie: {token.last_used or "Nikogda"}')
            self.stdout.write(f'   Ssylka: http://localhost:8000/auth/token/{token.token}/')
            self.stdout.write('')
        
        self.stdout.write('=' * 70)
        self.stdout.write(f'Vsego DEVELOPER tokenov: {tokens.count()}')
        self.stdout.write('=' * 70 + '\n')
    
    def _deactivate_token(self, token_uuid):
        """Деактивирует DEVELOPER токен"""
        try:
            token = TemporaryAccessToken.objects.get(
                token=token_uuid,
                token_type='DEVELOPER'
            )
            
            if not token.is_active:
                self.stdout.write(
                    self.style.WARNING(f'>> Token {token_uuid} uzhe deaktivirovan')
                )
                return
            
            token.is_active = False
            token.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'>> Token {token_uuid} uspeshno deaktivirovan')
            )
        
        except TemporaryAccessToken.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'>> DEVELOPER token {token_uuid} ne nayden')
            )
