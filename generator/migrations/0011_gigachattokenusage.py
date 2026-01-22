# Generated migration for GigaChat token usage tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('generator', '0010_temporaryaccesstoken_telegram_user_id_hash'),
    ]

    operations = [
        migrations.CreateModel(
            name='GigaChatTokenUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_type', models.CharField(choices=[('TEXT_GENERATION', 'Генерация текста'), ('IMAGE_PROMPT', 'Промпт для изображения'), ('IMAGE_GENERATION', 'Генерация изображения')], max_length=20, verbose_name='Тип операции')),
                ('estimated_prompt_tokens', models.IntegerField(default=0, verbose_name='Токенов в промпте (оценка)')),
                ('estimated_completion_tokens', models.IntegerField(default=0, verbose_name='Токенов в ответе (оценка)')),
                ('estimated_total_tokens', models.IntegerField(default=0, verbose_name='Всего токенов (оценка)')),
                ('prompt_length', models.IntegerField(default=0, help_text='Общая длина промпта в символах', verbose_name='Длина промпта (символов)')),
                ('response_length', models.IntegerField(default=0, help_text='Длина ответа от API в символах', verbose_name='Длина ответа (символов)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('topic', models.CharField(blank=True, max_length=255, null=True, verbose_name='Тема генерации')),
                ('platform', models.CharField(blank=True, max_length=50, null=True, verbose_name='Платформа')),
                ('generation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='token_usages', to='generator.generation', verbose_name='Генерация')),
                ('token', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gigachat_token_usages', to='generator.temporaryaccesstoken', verbose_name='Токен доступа')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gigachat_token_usages', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Использование токенов GigaChat',
                'verbose_name_plural': 'Использование токенов GigaChat',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='gigachattokenusage',
            index=models.Index(fields=['operation_type', 'created_at'], name='generator_g_operati_created_idx'),
        ),
        migrations.AddIndex(
            model_name='gigachattokenusage',
            index=models.Index(fields=['user', 'created_at'], name='generator_g_user_id_created_idx'),
        ),
        migrations.AddIndex(
            model_name='gigachattokenusage',
            index=models.Index(fields=['token', 'created_at'], name='generator_g_token_i_created_idx'),
        ),
        migrations.AddIndex(
            model_name='gigachattokenusage',
            index=models.Index(fields=['generation'], name='generator_g_generat_idx'),
        ),
    ]
