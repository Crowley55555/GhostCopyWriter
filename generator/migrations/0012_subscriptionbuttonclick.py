# Generated migration for subscription button click tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('generator', '0011_gigachattokenusage'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionButtonClick',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_url', models.CharField(help_text='Страница, с которой был сделан клик', max_length=500, verbose_name='URL страницы')),
                ('page_name', models.CharField(blank=True, help_text="Название страницы (например, 'profile', 'landing')", max_length=100, null=True, verbose_name='Название страницы')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP адрес')),
                ('user_agent', models.CharField(blank=True, max_length=500, null=True, verbose_name='User-Agent')),
                ('referer', models.CharField(blank=True, max_length=500, null=True, verbose_name='Referer')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата и время клика')),
                ('token', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscription_clicks', to='generator.temporaryaccesstoken', verbose_name='Токен доступа')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscription_clicks', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Клик по кнопке подписки',
                'verbose_name_plural': 'Клики по кнопке подписки',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='subscriptionbuttonclick',
            index=models.Index(fields=['created_at'], name='generator_s_created_idx'),
        ),
        migrations.AddIndex(
            model_name='subscriptionbuttonclick',
            index=models.Index(fields=['page_name', 'created_at'], name='generator_s_page_na_created_idx'),
        ),
        migrations.AddIndex(
            model_name='subscriptionbuttonclick',
            index=models.Index(fields=['user', 'created_at'], name='generator_s_user_id_created_idx'),
        ),
        migrations.AddIndex(
            model_name='subscriptionbuttonclick',
            index=models.Index(fields=['token', 'created_at'], name='generator_s_token_i_created_idx'),
        ),
    ]
