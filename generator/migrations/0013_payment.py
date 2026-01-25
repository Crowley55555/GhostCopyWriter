# Generated manually for Payment model

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('generator', '0012_subscriptionbuttonclick'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID платежа')),
                ('external_id', models.CharField(help_text='ID платежа в платёжной системе (ЮКасса/Тинькофф)', max_length=255, unique=True, verbose_name='Внешний ID')),
                ('telegram_user_id', models.BigIntegerField(help_text='ID пользователя в Telegram', verbose_name='Telegram User ID')),
                ('telegram_username', models.CharField(blank=True, help_text='Username пользователя в Telegram (если есть)', max_length=100, null=True, verbose_name='Telegram Username')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Сумма платежа в рублях', max_digits=10, verbose_name='Сумма')),
                ('currency', models.CharField(default='RUB', max_length=3, verbose_name='Валюта')),
                ('status', models.CharField(choices=[('pending', 'Ожидает оплаты'), ('succeeded', 'Оплачен'), ('canceled', 'Отменён'), ('refunded', 'Возврат')], default='pending', max_length=20, verbose_name='Статус')),
                ('payment_system', models.CharField(choices=[('yookassa', 'ЮКасса'), ('tinkoff', 'Тинькофф Касса')], default='yookassa', max_length=20, verbose_name='Платёжная система')),
                ('description', models.CharField(blank=True, help_text="Описание платежа (например, '30 дней подписки')", max_length=255, null=True, verbose_name='Описание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='Оплачен')),
                ('payment_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='Ссылка на оплату')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Дополнительные данные от платёжной системы', verbose_name='Метаданные')),
                ('token', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment', to='generator.temporaryaccesstoken', verbose_name='Выданный токен')),
            ],
            options={
                'verbose_name': 'Платёж',
                'verbose_name_plural': 'Платежи',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['telegram_user_id'], name='generator_p_telegra_8cc4d0_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['status', 'created_at'], name='generator_p_status_1b1f8e_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['external_id'], name='generator_p_externa_e8e8b5_idx'),
        ),
    ]
