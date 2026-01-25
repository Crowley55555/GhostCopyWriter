# Generated migration for new tariff system

import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from datetime import timedelta


def migrate_existing_tokens(apps, schema_editor):
    """
    Миграция существующих токенов в новую систему
    
    - DEMO -> HIDDEN_14D (если создан через manual)
    - MONTHLY -> BASIC
    - YEARLY -> PRO (временно, потом можно изменить)
    """
    TemporaryAccessToken = apps.get_model('generator', 'TemporaryAccessToken')
    
    # Мигрируем DEMO в HIDDEN_14D
    TemporaryAccessToken.objects.filter(token_type='DEMO').update(
        token_type='HIDDEN_14D',
        gigachat_tokens_limit=-1,
        openai_tokens_limit=0,
        gigachat_tokens_used=0,
        openai_tokens_used=0
    )
    
    # Мигрируем MONTHLY в BASIC
    TemporaryAccessToken.objects.filter(token_type='MONTHLY').update(
        token_type='BASIC',
        gigachat_tokens_limit=50000,
        openai_tokens_limit=3000,
        gigachat_tokens_used=0,
        openai_tokens_used=0
    )
    
    # Мигрируем YEARLY в PRO (временно)
    TemporaryAccessToken.objects.filter(token_type='YEARLY').update(
        token_type='PRO',
        gigachat_tokens_limit=200000,
        openai_tokens_limit=15000,
        gigachat_tokens_used=0,
        openai_tokens_used=0
    )
    
    # DEVELOPER остаётся как есть, но обновляем лимиты
    TemporaryAccessToken.objects.filter(token_type='DEVELOPER').update(
        gigachat_tokens_limit=-1,
        openai_tokens_limit=-1,
        gigachat_tokens_used=0,
        openai_tokens_used=0
    )


def reverse_migration(apps, schema_editor):
    """
    Обратная миграция (для rollback)
    """
    TemporaryAccessToken = apps.get_model('generator', 'TemporaryAccessToken')
    
    # Обратная миграция
    TemporaryAccessToken.objects.filter(token_type='HIDDEN_14D').update(token_type='DEMO')
    TemporaryAccessToken.objects.filter(token_type='BASIC').update(token_type='MONTHLY')
    TemporaryAccessToken.objects.filter(token_type='PRO').update(token_type='YEARLY')


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0013_payment'),
    ]

    operations = [
        # Увеличиваем max_length для token_type
        migrations.AlterField(
            model_name='temporaryaccesstoken',
            name='token_type',
            field=models.CharField(max_length=20, choices=[
                ('DEMO_FREE', 'Бесплатный старт'),
                ('BASIC', 'Базовый (500₽/мес)'),
                ('PRO', 'Про (1500₽/мес)'),
                ('UNLIMITED', 'Безлимит (3500₽/мес)'),
                ('HIDDEN_14D', 'Скрытый 14 дней'),
                ('HIDDEN_30D', 'Скрытый 30 дней'),
                ('DEVELOPER', 'Разработчик'),
            ], verbose_name='Тип токена'),
        ),
        
        # Добавляем новые поля для лимитов токенов
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='gigachat_tokens_limit',
            field=models.IntegerField(default=-1, help_text='-1 = безлимит, 0+ = количество токенов', verbose_name='Лимит токенов GigaChat'),
        ),
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='gigachat_tokens_used',
            field=models.IntegerField(default=0, help_text='Текущее использование токенов GigaChat', verbose_name='Использовано токенов GigaChat'),
        ),
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='openai_tokens_limit',
            field=models.IntegerField(default=0, help_text='-1 = безлимит, 0 = недоступен, 0+ = количество токенов', verbose_name='Лимит токенов OpenAI'),
        ),
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='openai_tokens_used',
            field=models.IntegerField(default=0, help_text='Текущее использование токенов OpenAI', verbose_name='Использовано токенов OpenAI'),
        ),
        
        # Добавляем поля для подписок
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='subscription_start',
            field=models.DateTimeField(blank=True, help_text='Дата начала подписки (для автопополнения)', null=True, verbose_name='Дата начала подписки'),
        ),
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='next_renewal',
            field=models.DateTimeField(blank=True, help_text='Дата следующего автоматического пополнения лимитов', null=True, verbose_name='Следующее пополнение'),
        ),
        
        # Делаем expires_at nullable для бессрочных токенов
        migrations.AlterField(
            model_name='temporaryaccesstoken',
            name='expires_at',
            field=models.DateTimeField(blank=True, help_text='Токен становится недействительным после этой даты (None = бессрочный)', null=True, verbose_name='Дата истечения'),
        ),
        
        # Мигрируем существующие токены
        migrations.RunPython(migrate_existing_tokens, reverse_migration),
        
        # Удаляем устаревшие поля (оставляем для обратной совместимости, но помечаем как deprecated)
        # Не удаляем сразу, чтобы не сломать существующий код
        # migrations.RemoveField(
        #     model_name='temporaryaccesstoken',
        #     name='daily_generations_left',
        # ),
        # migrations.RemoveField(
        #     model_name='temporaryaccesstoken',
        #     name='generations_reset_date',
        # ),
    ]
