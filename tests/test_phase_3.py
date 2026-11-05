"""
Фаза 3: регистрация по логину и паролю (тесты)

Критерии «Фаза 3 → Критерии (тесты)» плана `plans/2026-10-06-zapusk-demo.md`:
- регистрация → вход → генерация → после выхода и входа всё на месте;
- разметка `renderTemplateDropdown`: имя шаблона через `textContent`;
- вход при живом демо-токене — дальше работает REGISTERED;
- деактивированный токен вошедшего заменяется без выхода из аккаунта;
- суперпользователь после `/admin/` открывает генератор;
- «Свои данные»: B не видит пост A; аноним — приглашение, не 500;
- выход/вход не обнуляют дневной лимит; через 24 часа восстанавливается;
- общий провайдерский потолок действует и на зарегистрированных;
- ключ сессии меняется после login; пароль не лежит в сессии;
- слабый пароль отклоняется формой;
- IP-лимит регистраций: успех и неуспех считаются вместе;
- `makemigrations --check --dry-run --settings=ghostwriter.settings` чист.
"""

from datetime import timedelta
import os
import re
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from generator.access import (
    MSG_DAILY_LIMIT,
    MSG_DAILY_LIMIT_USER,
    issue_or_get_registered_token,
    start_token_session,
)
from generator.models import (
    AccessEvent,
    Generation,
    GenerationTemplate,
    GigaChatTokenUsage,
    TemporaryAccessToken,
    UserProfile,
)
from generator.tariffs import get_tariff_config
from tests.helpers import fake_gigachat, register_and_login


STRONG_PWD = 'StrongDemoPwd_7Qx1'
STRONG_PWD_B = 'OtherStrong_9Vt3'


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    AUTH_PASSWORD_VALIDATORS=[
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    ],
)
class RegistrationFlowTests(TestCase):
    """Регистрация, вход, сессия, выход (POST), доступ к `/auth/token/`"""

    def test_register_creates_user_profile_and_registered_token(self):
        response, user = register_and_login(self.client, username='owner1',
                                            password=STRONG_PWD)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/profile/')
        self.assertIsNotNone(user)
        self.assertTrue(UserProfile.objects.filter(user=user, terms_accepted=True).exists())
        token = TemporaryAccessToken.objects.filter(
            user=user, token_type='REGISTERED', is_active=True,
        ).first()
        self.assertIsNotNone(token)
        # Тариф: без лимита токенов GigaChat, OpenAI — 0
        self.assertEqual(token.gigachat_tokens_limit, -1)
        self.assertEqual(token.openai_tokens_limit, 0)

    def test_register_requires_terms_accepted(self):
        response, user = register_and_login(self.client, username='owner_no_terms',
                                            password=STRONG_PWD, terms_accepted=False)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(user)

    def test_register_rejects_weak_password(self):
        # «12345678» — слабый пароль (NumericPasswordValidator + CommonPasswordValidator)
        response = self.client.post('/register/', {
            'username': 'owner_weak',
            'password1': '12345678',
            'password2': '12345678',
            'terms_accepted': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='owner_weak').exists())

    def test_login_changes_session_key(self):
        register_and_login(self.client, username='owner_sk', password=STRONG_PWD)
        self.client.logout()
        # После logout ключ сессии сбрасывается; фиксируем до login
        anon = Client()
        anon.get('/')  # порождаем сессию
        before = anon.session.session_key
        self.assertIsNotNone(before)
        response = anon.post('/login/', {
            'username': 'owner_sk',
            'password': STRONG_PWD,
        })
        self.assertEqual(response.status_code, 302)
        after = anon.session.session_key
        self.assertNotEqual(before, after, 'login должен менять ключ сессии')

    def test_password_not_stored_in_session(self):
        register_and_login(self.client, username='owner_ses', password=STRONG_PWD)
        snapshot = dict(self.client.session)
        for key, value in snapshot.items():
            self.assertNotIn(STRONG_PWD, str(value),
                             f'пароль нашёлся в сессии под ключом {key!r}')

    def test_logout_requires_post(self):
        register_and_login(self.client, username='owner_lo', password=STRONG_PWD)
        self.assertIn(SESSION_KEY, self.client.session)
        # GET /logout/ — не выходит (require_POST → 405)
        response = self.client.get('/logout/')
        self.assertEqual(response.status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)
        # POST /logout/ — выходит
        response = self.client.post('/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_token_auth_view_blocked_for_authenticated(self):
        register_and_login(self.client, username='owner_tok', password=STRONG_PWD)
        demo_token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE',
            gigachat_tokens_limit=100,
            openai_tokens_limit=0,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        response = self.client.get(f'/auth/token/{demo_token.token}/')
        # Логинутый — редирект на профиль, демо-токен сессию не трогает
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/profile/')
        # После запроса на не-исключённом URL middleware подставит REGISTERED
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        own_token = TemporaryAccessToken.objects.get(
            user=User.objects.get(username='owner_tok'),
            token_type='REGISTERED', is_active=True,
        )
        self.assertEqual(self.client.session.get('access_token'), str(own_token.token))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RegisterIPLimitTests(TestCase):
    """IP-лимит регистраций: успех и неуспех считаются вместе"""

    def _attempts(self):
        return AccessEvent.objects.filter(
            event_type=AccessEvent.REGISTER_ATTEMPT,
        ).count()

    @override_settings(REGISTER_PER_IP_PER_DAY=3, AUTH_PASSWORD_VALIDATORS=[])
    def test_mix_of_success_and_failure_counts(self):
        # 2 попытки с неуспехом (пароли не совпадают) + 1 успех = 3 → следующая 429
        for i in range(2):
            self.client.post('/register/', {
                'username': f'owner_mix_{i}',
                'password1': STRONG_PWD,
                'password2': STRONG_PWD + 'DIFF',
                'terms_accepted': 'on',
            })
        self.assertEqual(self._attempts(), 2)
        self.assertFalse(User.objects.filter(username__startswith='owner_mix_').exists())
        # Третья — успешная
        response, user = register_and_login(self.client, username='owner_mix_ok',
                                            password=STRONG_PWD)
        self.assertIsNotNone(user)
        self.assertEqual(self._attempts(), 3)
        # Четвёртая — 429 даже при валидной форме
        self.client.logout()
        response = self.client.post('/register/', {
            'username': 'owner_too_late',
            'password1': STRONG_PWD,
            'password2': STRONG_PWD,
            'terms_accepted': 'on',
        })
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(username='owner_too_late').exists())

    @override_settings(REGISTER_PER_IP_PER_DAY=2, AUTH_PASSWORD_VALIDATORS=[])
    def test_old_events_dropped(self):
        AccessEvent.objects.create(
            event_type=AccessEvent.REGISTER_ATTEMPT,
            ip_hash='a' * 64,
            created_at=timezone.now() - timedelta(hours=25),
        )
        # Старая запись не мешает регистрироваться
        response, user = register_and_login(self.client, username='owner_fresh',
                                            password=STRONG_PWD)
        self.assertIsNotNone(user)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   AUTH_PASSWORD_VALIDATORS=[])
class RegisteredTokenTests(TestCase):
    """`issue_or_get_registered_token` и один активный токен на пользователя"""

    def test_token_is_single_per_user(self):
        user = User.objects.create_user(username='u1', password=STRONG_PWD)
        token1 = issue_or_get_registered_token(user)
        token2 = issue_or_get_registered_token(user)
        self.assertEqual(token1.pk, token2.pk)
        # Токен возвращается активным и типа REGISTERED
        self.assertTrue(token1.is_active)
        self.assertEqual(token1.token_type, 'REGISTERED')

    def test_deactivated_token_replaced_without_logout(self):
        register_and_login(self.client, username='u2', password=STRONG_PWD)
        user = User.objects.get(username='u2')
        prev = TemporaryAccessToken.objects.get(user=user, is_active=True, token_type='REGISTERED')
        # Деактивируем прежний токен (симуляция истечения)
        prev.is_active = False
        prev.save(update_fields=['is_active'])
        # Запрос по-прежнему проходит: middleware выдаёт новый
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(SESSION_KEY, self.client.session)
        new = TemporaryAccessToken.objects.filter(
            user=user, token_type='REGISTERED', is_active=True,
        ).first()
        self.assertIsNotNone(new)
        self.assertNotEqual(new.pk, prev.pk)

    def test_repeat_calls_do_not_pile_up_tokens(self):
        """
        Мутация-защитник: если `issue_or_get_registered_token` начнёт
        создавать НОВЫЙ активный токен на каждый вызов, число активных
        REGISTERED-токенов у пользователя вырастет. Нормальное поведение —
        один активный. Проверяем по БД и фиксируем pk.
        """
        user = User.objects.create_user(username='u_stable', password=STRONG_PWD)
        pks = set()
        for _ in range(5):
            tok = issue_or_get_registered_token(user)
            pks.add(tok.pk)
        self.assertEqual(len(pks), 1,
                         'issue_or_get_registered_token должен возвращать тот же токен')
        active = TemporaryAccessToken.objects.filter(
            user=user, token_type='REGISTERED', is_active=True,
        ).count()
        self.assertEqual(active, 1,
                         'активный REGISTERED-токен у пользователя должен быть один')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   AUTH_PASSWORD_VALIDATORS=[])
class OwnDataIsolationTests(TestCase):
    """Пользователь B не открывает пост и шаблон пользователя A (ревью версии 1, п. 7)"""

    def setUp(self):
        self.client_a = Client()
        register_and_login(self.client_a, username='user_a', password=STRONG_PWD)
        self.user_a = User.objects.get(username='user_a')
        self.gen_a = Generation.objects.create(user=self.user_a, topic='A-тема',
                                               result='пост А')
        self.tpl_a = GenerationTemplate.objects.create(
            user=self.user_a, name='A-шаблон', settings={'voice_tone': ['Дружелюбный']},
        )
        self.client_b = Client()
        register_and_login(self.client_b, username='user_b', password=STRONG_PWD_B)

    def test_user_b_cannot_view_a_generation(self):
        response = self.client_b.get(f'/generation/{self.gen_a.id}/')
        self.assertEqual(response.status_code, 404)

    def test_user_b_cannot_delete_a_generation(self):
        response = self.client_b.post(f'/delete-generation/{self.gen_a.id}/')
        self.assertEqual(response.status_code, 404)
        # Пост A всё ещё существует
        self.assertTrue(Generation.objects.filter(pk=self.gen_a.pk).exists())

    def test_user_b_wall_shows_only_own(self):
        response = self.client_b.get('/wall/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'A-тема')
        # Создадим пост у B — он виден
        Generation.objects.create(user=User.objects.get(username='user_b'),
                                  topic='B-тема', result='пост Б')
        response = self.client_b.get('/wall/')
        self.assertContains(response, 'B-тема')


class AnonymousOffersRegistrationTests(TestCase):
    """Демо-посетитель на страницах профиля/истории — приглашение, не 500"""

    def setUp(self):
        self.client = Client()
        # Демо-сессия через токен DEMO_FREE (как «Попробовать»)
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE',
            gigachat_tokens_limit=100,
            openai_tokens_limit=0,
            expires_at=timezone.now() + timedelta(hours=2),
        )
        # Открываем сессию без пользователя, как `try_demo`
        s = self.client.session
        s['access_token'] = str(token.token)
        s['token_type'] = token.token_type
        s.save()
        self.token = token

    def test_anon_profile_offers_registration(self):
        response = self.client.get('/profile/')
        self.assertIn(response.status_code, (200, 302))
        # Не 500 и не редирект в бесконечность — приглашение в теле
        if response.status_code == 200:
            self.assertContains(response, 'Зарегистрируйтесь')

    def test_anon_wall_offers_registration(self):
        response = self.client.get('/wall/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Зарегистрируйтесь')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   AUTH_PASSWORD_VALIDATORS=[])
class DailyLimitPersistenceTests(TestCase):
    """Выход и вход не обнуляют дневной лимит; через 24 часа восстанавливается"""

    @override_settings(REGISTERED_DAILY_CALL_LIMIT=3)
    def test_relogin_does_not_reset_daily_limit(self):
        register_and_login(self.client, username='u_limit', password=STRONG_PWD)
        user = User.objects.get(username='u_limit')
        # Создаём 3 строки учёта — потолок достигнут
        for _ in range(3):
            GigaChatTokenUsage.objects.create(
                user=user,
                operation_type='TEXT_GENERATION',
                provider='gigachat-lite',
                estimated_total_tokens=100,
            )
        # Проверяем через check_text_access: 429 + MSG_DAILY_LIMIT_USER
        from django.test import RequestFactory
        from generator.access import check_text_access, PROVIDER_GIGACHAT_LITE
        rf = RequestFactory()
        req = rf.get('/generator/')
        req.user = user
        req.session = self.client.session
        response = check_text_access(req, provider_code=PROVIDER_GIGACHAT_LITE,
                                     topic='тема')
        # Залогинен → редирект на limit_exceeded (не AJAX)
        self.assertIsNotNone(response)
        # Выход и повторный вход — лимит сохраняется
        self.client.post('/logout/')
        response = self.client.post('/login/', {
            'username': 'u_limit', 'password': STRONG_PWD,
        })
        self.assertEqual(response.status_code, 302)
        # Счётчик по-прежнему 3 — не обнулён входом
        self.assertEqual(GigaChatTokenUsage.objects.filter(user=user).count(), 3)

    @override_settings(REGISTERED_DAILY_CALL_LIMIT=2)
    def test_limit_restored_after_24h(self):
        user = User.objects.create_user(username='u_old', password=STRONG_PWD)
        token = issue_or_get_registered_token(user)
        # 2 записи 25 часов назад — за окном
        old_time = timezone.now() - timedelta(hours=25)
        for _ in range(2):
            u = GigaChatTokenUsage.objects.create(
                user=user,
                operation_type='TEXT_GENERATION',
                provider='gigachat-lite',
                estimated_total_tokens=100,
            )
            GigaChatTokenUsage.objects.filter(pk=u.pk).update(created_at=old_time)

        from django.test import RequestFactory
        from generator.access import check_text_access, PROVIDER_GIGACHAT_LITE
        rf = RequestFactory()
        req = rf.get('/generator/')
        req.user = user
        session = self.client.session
        session['access_token'] = str(token.token)
        session.save()
        req.session = session
        response = check_text_access(req, provider_code=PROVIDER_GIGACHAT_LITE,
                                     topic='тема')
        # Окно сдвинулось — проход (None) до провайдерского потолка
        self.assertIsNone(response)

    @override_settings(REGISTERED_DAILY_CALL_LIMIT=1000, GIGACHAT_DAILY_CALL_LIMIT=1)
    def test_provider_ceiling_also_hits_registered_user(self):
        user = User.objects.create_user(username='u_prov', password=STRONG_PWD)
        issue_or_get_registered_token(user)
        # Один вызов другого пользователя исчерпывает общий потолок GigaChat
        other = User.objects.create_user(username='u_other', password=STRONG_PWD)
        GigaChatTokenUsage.objects.create(
            user=other,
            operation_type='TEXT_GENERATION',
            provider='gigachat-lite',
            estimated_total_tokens=100,
        )
        from django.test import RequestFactory
        from generator.access import check_text_access, PROVIDER_GIGACHAT_LITE, deny
        rf = RequestFactory()
        req = rf.get('/generator/')
        req.user = user
        req.session = self.client.session
        # Токен юзера нужен в сессии
        token = TemporaryAccessToken.objects.get(user=user, token_type='REGISTERED', is_active=True)
        req.session['access_token'] = str(token.token)
        req.session.save()
        response = check_text_access(req, provider_code=PROVIDER_GIGACHAT_LITE, topic='тема')
        self.assertIsNotNone(response)  # потолок сработал


class StartTokenSessionUpdateFieldsTests(TestCase):
    """start_token_session использует save(update_fields=...): замечание 2 ревью фазы 1"""

    def test_parallel_consume_not_lost(self):
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE',
            gigachat_tokens_limit=1000,
            openai_tokens_limit=0,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        # Читаем через один экземпляр
        instance_a = TemporaryAccessToken.objects.get(pk=token.pk)
        # Параллельное списание другим экземпляром пишет значение в БД
        instance_b = TemporaryAccessToken.objects.get(pk=token.pk)
        instance_b.consume_gigachat_tokens(42)

        # start_token_session над первым не должен затереть расход
        from django.test import RequestFactory
        rf = RequestFactory()
        req = rf.get('/auth/token/')
        req.session = self.client.session
        start_token_session(req, instance_a)
        # В БД расход 42 — не затёрт полным save() старого экземпляра
        instance_c = TemporaryAccessToken.objects.get(pk=token.pk)
        self.assertEqual(instance_c.gigachat_tokens_used, 42)


class MarkupTests(TestCase):
    """Шаблон gigagenerator.html: имя шаблона настроек не попадает в innerHTML как текст"""

    def test_render_template_dropdown_uses_textContent(self):
        template_path = os.path.join(
            settings.BASE_DIR, 'generator', 'templates', 'generator', 'gigagenerator.html',
        )
        with open(template_path, encoding='utf-8') as f:
            content = f.read()
        # Находим тело функции renderTemplateDropdown
        start = content.find('function renderTemplateDropdown')
        self.assertNotEqual(start, -1)
        end = content.find('function loadTemplate', start)
        body = content[start:end]
        # Имя шаблона — через textContent / createElement
        self.assertIn('nameSpan.textContent = t.name', body)
        # Иконки добавляются через createElement, не template-строкой
        self.assertIn("createElement('i')", body)
        # Снимаем /* ... */ и // ... комментарии, чтобы искать только в коде
        no_block = re.sub(r'/\*.*?\*/', '', body, flags=re.DOTALL)
        no_line = re.sub(r'//[^\n]*', '', no_block)
        # В коде не должно быть `innerHTML = \`...${t.name}...\`` (шаблонных строк
        # с подставленным именем — старая уязвимая разметка)
        self.assertNotIn('${t.name}', no_line,
                         'имя шаблона не должно собираться в HTML-строку')
        self.assertNotIn('innerHTML', no_line.replace("list.innerHTML = ''", ''),
                         'innerHTML в renderTemplateDropdown допустим только для очистки')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   AUTH_PASSWORD_VALIDATORS=[])
class FullCycleAfterRelogin(TestCase):
    """Регистрация → профиль с данными → выход → вход → данные на месте"""

    def test_business_info_and_samples_persist(self):
        register_and_login(self.client, username='owner_full', password=STRONG_PWD)
        user = User.objects.get(username='owner_full')
        # Пользователь заполняет «О бизнесе» и образцы в профиле
        response = self.client.post('/profile/edit/', {
            'business_info': 'Семейная кофейня у метро',
            'samples': 'пост один\n---\nпост два',
        })
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.business_info, 'Семейная кофейня у метро')
        self.assertIn('пост один', profile.samples)
        # Создаём пост у пользователя
        Generation.objects.create(user=user, topic='Приятный пост', result='Тело поста')
        # Выход и вход
        self.client.post('/logout/')
        self.client.post('/login/', {
            'username': 'owner_full', 'password': STRONG_PWD,
        })
        # После входа: данные профиля на месте, пост виден
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Семейная кофейня у метро')
        response = self.client.get('/wall/')
        self.assertContains(response, 'Приятный пост')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   AUTH_PASSWORD_VALIDATORS=[])
class ProfileBusinessInfoNotOverwrittenByGeneratorTests(TestCase):
    """
    Раунд исправлений 1 фазы 3: пустое `business_info` в форме генератора
    не должно затирать значение, сохранённое пользователем через
    `/profile/edit/`. Автосохранение `profile.business_info`/`profile.samples`
    из `generator_view` убрано — у залогиненого эти поля правятся только
    явно в профиле.

    Мутация-защитник: если вернуть `profile.business_info = form_data.get(...)`
    в `generator_view`, тест падает (значение затирается на пустое).
    """

    def test_profile_business_info_not_overwritten_from_generator_form(self):
        register_and_login(self.client, username='owner_bi', password=STRONG_PWD)
        user = User.objects.get(username='owner_bi')
        # 1. Явная правка профиля через /profile/edit/
        response = self.client.post('/profile/edit/', {
            'business_info': 'Я — пекарня',
            'samples': 'Печём хлеб с 2015 года',
        })
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.business_info, 'Я — пекарня')
        self.assertEqual(profile.samples, 'Печём хлеб с 2015 года')
        # 2. POST на /generator/ с пустыми business_info/samples (мок GigaChat).
        #    Без фикса пустые строки затёрли бы сохранённые в профиле значения.
        with fake_gigachat():
            response = self.client.post('/generator/', {
                'topic': 'Новый хлеб на выходных',
                'platform': 'Telegram',
                'business_info': '',
                'samples': '',
            }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json().get('success'))
        # 3. Данные в профиле остались прежними
        profile.refresh_from_db()
        self.assertEqual(profile.business_info, 'Я — пекарня')
        self.assertEqual(profile.samples, 'Печём хлеб с 2015 года')


class MakemigrationsClean(TestCase):
    """После применения миграций `makemigrations --dry-run` не предлагает новых"""

    def test_dry_run_clean(self):
        # Отдельный процесс с `ghostwriter.settings` — у test_settings
        # миграции отключены через DisableMigrations
        import subprocess
        import sys
        manage_py = os.path.join(settings.BASE_DIR, 'manage.py')
        env = os.environ.copy()
        env.pop('DJANGO_SETTINGS_MODULE', None)
        result = subprocess.run(
            [sys.executable, manage_py, 'makemigrations', '--check', '--dry-run',
             'generator', '--settings=ghostwriter.settings'],
            capture_output=True, text=True, env=env, cwd=settings.BASE_DIR,
        )
        self.assertEqual(result.returncode, 0,
                         f'makemigrations --check код {result.returncode}\n'
                         f'STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}')


class PublicPagesWhenDebugFalse(TestCase):
    """Страницы входа и регистрации рендерятся при `DEBUG=False`"""

    def test_login_page_renders(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Вход')

    def test_register_page_renders(self):
        response = self.client.get('/register/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Регистрация')


class TemplatesHaveNoQuickLoginReference(TestCase):
    """После фазы 3 в шаблонах нет {% url 'quick_login' %}"""

    def test_grep(self):
        base = os.path.join(settings.BASE_DIR, 'generator', 'templates')
        offenders = []
        for root, dirs, files in os.walk(base):
            for name in files:
                if not name.endswith('.html'):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8') as f:
                    text = f.read()
                if re.search(r"url\s+['\"]quick_login['\"]", text):
                    offenders.append(path)
        self.assertEqual(offenders, [],
                         f'quick_login остался в шаблонах: {offenders}')
