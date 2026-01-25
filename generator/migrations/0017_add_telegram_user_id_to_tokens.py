# Generated manually for anti-multiaccount protection

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0016_remove_legacy_token_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='telegram_user_id',
            field=models.BigIntegerField(blank=True, help_text='ID пользователя в Telegram (для защиты от мультиаккаунтов)', null=True, verbose_name='Telegram User ID'),
        ),
        migrations.AddIndex(
            model_name='temporaryaccesstoken',
            index=models.Index(fields=['telegram_user_id', 'token_type', 'is_active'], name='generator_t_telegram_4a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='temporaryaccesstoken',
            index=models.Index(fields=['telegram_user_id', 'is_active'], name='generator_t_telegram_5a2b3c_idx'),
        ),
    ]
