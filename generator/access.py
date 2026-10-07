"""
Доступ к генерации: демо-токены «Попробовать» и проверка перед GigaChat

- get_client_ip: единственное место, где определяется IP клиента;
- start_token_session: сессия по токену (вход по ссылке и «Попробовать»);
- issue_demo_token: выдача демо-токена с лимитом на IP за сутки;
- check_gigachat_access: единая проверка перед каждым вызовом GigaChat.
"""

import ipaddress
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import AccessEvent, GigaChatTokenUsage, TemporaryAccessToken

# Окно лимита выдачи на IP и общего потолка; AccessEvent старше него удаляются
ACCESS_WINDOW = timedelta(hours=24)

# Срок жизни демо-токена «Попробовать»
DEMO_TOKEN_LIFETIME = timedelta(hours=24)

MSG_NO_TOKEN = 'Нет доступа к генерации. Нажмите «Попробовать» на главной странице.'
MSG_TOKEN_INVALID = 'Доступ закончился или недействителен. Получите новый на главной странице.'
MSG_TOKEN_LIMIT = 'Лимит генераций для вашего доступа исчерпан.'
MSG_DAILY_LIMIT = 'Сервис исчерпал дневной лимит генераций. Попробуйте позже.'
MSG_TOPIC_TOO_LONG = 'Слишком длинная тема: не больше {max_length} символов.'
MSG_TEXT_TOO_LONG = 'Слишком длинный текст поста: не больше {max_length} символов.'


def get_client_ip(request):
    """
    IP клиента: за прокси (BEHIND_PROXY) — из X-Real-IP, иначе REMOTE_ADDR

    X-Forwarded-For не используется: его первый элемент задаёт клиент.
    Если X-Real-IP нет или это не адрес — REMOTE_ADDR, то есть адрес прокси:
    такие клиенты делят один лимит (строже, а не мягче).
    """
    if settings.BEHIND_PROXY:
        real_ip = request.META.get('HTTP_X_REAL_IP', '').strip()
        try:
            return str(ipaddress.ip_address(real_ip))
        except ValueError:
            pass
    return request.META.get('REMOTE_ADDR', '')


def hash_ip(ip):
    """HMAC-SHA256 от IP с ключом из SECRET_KEY: IP в открытом виде не хранится"""
    return salted_hmac('generator.access.ip', ip, algorithm='sha256').hexdigest()


def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def deny(request, message, status, redirect_to):
    """Отказ: AJAX получает JSON с ошибкой, обычный запрос — редирект"""
    if is_ajax(request):
        return JsonResponse({'success': False, 'error': message}, status=status)
    return redirect(redirect_to)


def get_session_token(request):
    """Действующий токен из сессии (активен, не истёк) или None"""
    token_str = request.session.get('access_token')
    if not token_str:
        return None
    token = TemporaryAccessToken.objects.filter(token=token_str, is_active=True).first()
    if token is None or token.is_expired():
        return None
    return token


def start_token_session(request, access_token):
    """
    Открывает сессию по токену доступа

    Записывает в сессию токен и его лимиты, отмечает использование токена.
    Для токена с telegram_user_id создаёт пользователя Django tg_<id>
    и выполняет вход (для сохранения истории). Демо-токены без
    telegram_user_id остаются без привязки к пользователю.
    """
    request.session['access_token'] = str(access_token.token)
    request.session['token_type'] = access_token.token_type
    request.session['is_demo'] = (access_token.token_type == 'DEMO_FREE' or access_token.token_type.startswith('HIDDEN'))
    request.session['gigachat_tokens_limit'] = access_token.gigachat_tokens_limit
    request.session['gigachat_tokens_used'] = access_token.gigachat_tokens_used
    request.session['openai_tokens_limit'] = access_token.openai_tokens_limit
    request.session['openai_tokens_used'] = access_token.openai_tokens_used
    if access_token.expires_at:
        request.session['expires_at'] = access_token.expires_at.isoformat()
    else:
        request.session['expires_at'] = None
    # Для обратной совместимости
    request.session['daily_generations_left'] = -1

    # Обновляем информацию о последнем использовании
    access_token.last_used = timezone.now()
    access_token.current_ip = request.META.get('REMOTE_ADDR')
    access_token.save()

    # Привязка к пользователю Django по telegram_user_id (для сохранения истории)
    if access_token.telegram_user_id and not request.user.is_authenticated:
        # Создаём уникальное имя пользователя на основе telegram_user_id
        username = f"tg_{access_token.telegram_user_id}"

        # Ищем или создаём пользователя Django
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f"tg{access_token.telegram_user_id}@ghostwriter.local",  # Фиктивный email
                'is_active': True,
                'is_staff': False,
                'is_superuser': False,
            }
        )

        # Вход только по токену, пароль не используется
        if created:
            user.set_unusable_password()
            user.save()

        # Авторизуем пользователя в Django (для привязки генераций)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')


def issue_demo_token(request):
    """
    Выдаёт демо-токен «Попробовать», если с IP за сутки выдано меньше N

    Счётчик — AccessEvent с HMAC-хэшем IP. Записи старше суток удаляются
    здесь же, при каждом обращении.

    Returns:
        TemporaryAccessToken или None, если лимит выдачи на IP исчерпан
    """
    now = timezone.now()
    window_start = now - ACCESS_WINDOW
    ip_hash = hash_ip(get_client_ip(request))

    AccessEvent.objects.filter(created_at__lt=window_start).delete()

    issued = AccessEvent.objects.filter(
        event_type=AccessEvent.DEMO_TOKEN,
        ip_hash=ip_hash,
        created_at__gte=window_start,
    ).count()
    if issued >= settings.DEMO_TOKENS_PER_IP_PER_DAY:
        return None

    with transaction.atomic():
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO_FREE',
            gigachat_tokens_limit=settings.DEMO_GIGACHAT_TOKENS_LIMIT,
            openai_tokens_limit=0,
            expires_at=now + DEMO_TOKEN_LIFETIME,
        )
        AccessEvent.objects.create(
            event_type=AccessEvent.DEMO_TOKEN,
            ip_hash=ip_hash,
            created_at=now,
        )
    return token


def check_gigachat_access(request, topic=None, result_text=None):
    """
    Единая проверка перед каждым вызовом GigaChat

    Проверяет действующий токен в сессии, остаток его лимита GigaChat
    (лимит OpenAI не учитывается), общий потолок вызовов GigaChat за 24 часа
    и длину пользовательского ввода, который уходит в промпт.

    Returns:
        None, если вызов разрешён (токен кладётся в request.token),
        иначе ответ с отказом: view возвращает его, не вызывая GigaChat
    """
    token = get_session_token(request)
    if token is None:
        return deny(request, MSG_NO_TOKEN, 403, 'token_required_page')

    can_use, _ = token.can_use_gigachat()
    if not can_use:
        return deny(request, MSG_TOKEN_LIMIT, 429, 'limit_exceeded_page')

    calls = GigaChatTokenUsage.objects.filter(created_at__gte=timezone.now() - ACCESS_WINDOW).count()
    if calls >= settings.GIGACHAT_DAILY_CALL_LIMIT:
        return deny(request, MSG_DAILY_LIMIT, 429, 'limit_exceeded_page')

    for value, max_length, message in (
        (topic, settings.GENERATION_MAX_TOPIC_LENGTH, MSG_TOPIC_TOO_LONG),
        (result_text, settings.GENERATION_MAX_TEXT_LENGTH, MSG_TEXT_TOO_LONG),
    ):
        if value and len(value) > max_length:
            return deny(request, message.format(max_length=max_length), 400, 'limit_exceeded_page')

    request.token = token
    return None
