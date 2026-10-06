"""
Вспомогательный код тестов: вход по токену доступа

Тесты входят тем же путём, что и пользователь: создают
TemporaryAccessToken и открывают /auth/token/<uuid>/ (token_auth_view).
"""

from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User

from generator.models import TemporaryAccessToken
from generator.tariffs import get_tariff_config


class TokenAuthMixin:
    """Вход тестового клиента по токену доступа (для django.test.TestCase)"""

    def login_by_token(self, telegram_user_id, token_type='DEMO_FREE'):
        """
        Создаёт токен с лимитами тарифа и входит по нему через /auth/token/<uuid>/

        token_auth_view создаёт пользователя Django tg_<telegram_user_id>
        и выполняет вход. Возвращает (token, user).
        """
        tariff = get_tariff_config(token_type)
        token = TemporaryAccessToken.objects.create(
            token_type=token_type,
            gigachat_tokens_limit=tariff['gigachat_tokens'],
            openai_tokens_limit=tariff['openai_tokens'],
            telegram_user_id=telegram_user_id,
        )

        response = self.client.get(f'/auth/token/{token.token}/')
        self.assertRedirects(response, '/generator/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['access_token'], str(token.token))

        user = User.objects.get(username=f'tg_{telegram_user_id}')
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        return token, user
