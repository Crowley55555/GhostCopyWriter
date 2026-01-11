"""
Команда для очистки просроченных токенов доступа

Использование:
    python manage.py cleanup_tokens
    
Можно добавить в cron для автоматического выполнения:
    0 2 * * * cd /path/to/project && python manage.py cleanup_tokens
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from generator.models import TemporaryAccessToken


class Command(BaseCommand):
    """
    Команда для деактивации просроченных токенов доступа
    
    Находит все токены с истекшим сроком действия и деактивирует их,
    освобождая место в базе данных и улучшая производительность.
    """
    
    help = 'Деактивирует просроченные токены доступа'
    
    def add_arguments(self, parser):
        """
        Добавляет аргументы командной строки
        
        Args:
            parser: Парсер аргументов командной строки
        """
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Удалять токены вместо деактивации (необратимо)',
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Удалять токены, деактивированные более N дней назад (только с --delete)',
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без реального изменения данных',
        )
    
    def handle(self, *args, **options):
        """
        Основная логика команды
        
        Args:
            *args: Позиционные аргументы
            **options: Именованные аргументы из add_arguments
        """
        now = timezone.now()
        dry_run = options['dry_run']
        delete = options['delete']
        days_old = options['days']
        
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('🧹 Очистка токенов доступа'))
        self.stdout.write('=' * 70)
        
        # Деактивация просроченных токенов
        expired_tokens = TemporaryAccessToken.objects.filter(
            expires_at__lt=now,
            is_active=True
        )
        
        expired_count = expired_tokens.count()
        
        if expired_count > 0:
            self.stdout.write(f'\n📊 Найдено просроченных токенов: {expired_count}')
            
            if not dry_run:
                expired_tokens.update(is_active=False)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Деактивировано токенов: {expired_count}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'🔍 [DRY RUN] Будет деактивировано: {expired_count}')
                )
        else:
            self.stdout.write(
                self.style.WARNING('\n⚠️ Просроченных активных токенов не найдено')
            )
        
        # Удаление старых деактивированных токенов (опционально)
        if delete:
            from datetime import timedelta
            cutoff_date = now - timedelta(days=days_old)
            
            old_inactive_tokens = TemporaryAccessToken.objects.filter(
                is_active=False,
                expires_at__lt=cutoff_date
            )
            
            old_count = old_inactive_tokens.count()
            
            if old_count > 0:
                self.stdout.write(
                    f'\n📊 Найдено старых деактивированных токенов (>{days_old} дней): {old_count}'
                )
                
                if not dry_run:
                    old_inactive_tokens.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'🗑️ Удалено токенов: {old_count}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'🔍 [DRY RUN] Будет удалено: {old_count}')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️ Старых деактивированных токенов (>{days_old} дней) не найдено'
                    )
                )
        
        # Статистика по активным токенам
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 Статистика активных токенов'))
        self.stdout.write('=' * 70)
        
        active_tokens = TemporaryAccessToken.objects.filter(
            is_active=True,
            expires_at__gte=now
        )
        
        total_active = active_tokens.count()
        demo_count = active_tokens.filter(token_type='DEMO').count()
        monthly_count = active_tokens.filter(token_type='MONTHLY').count()
        yearly_count = active_tokens.filter(token_type='YEARLY').count()
        
        self.stdout.write(f'\n✅ Всего активных токенов: {total_active}')
        self.stdout.write(f'   - DEMO (5 дней): {demo_count}')
        self.stdout.write(f'   - MONTHLY (30 дней): {monthly_count}')
        self.stdout.write(f'   - YEARLY (365 дней): {yearly_count}')
        
        # Статистика использования
        total_generations = TemporaryAccessToken.objects.aggregate(
            total=models.Sum('total_used')
        )['total'] or 0
        
        self.stdout.write(f'\n🎨 Всего генераций через токены: {total_generations}')
        
        # Предупреждения
        if dry_run:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(
                self.style.WARNING(
                    '⚠️ DRY RUN режим: изменения не были применены.\n'
                    'Запустите без --dry-run для реального выполнения.'
                )
            )
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('✅ Очистка завершена успешно'))
        self.stdout.write('=' * 70 + '\n')


# Импортируем models для использования в aggregate
from django.db import models
