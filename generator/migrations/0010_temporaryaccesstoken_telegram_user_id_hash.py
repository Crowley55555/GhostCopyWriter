# Generated manually for preventing duplicate DEMO tokens

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0009_alter_temporaryaccesstoken_token_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='temporaryaccesstoken',
            name='telegram_user_id_hash',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='SHA-256 хеш Telegram user_id для отслеживания без сбора ПДн',
                max_length=64,
                null=True,
                verbose_name='Хеш Telegram user_id'
            ),
        ),
    ]
