# 🔒 Безопасность Ghostwriter

## Обзор системы безопасности

Ghostwriter включает многоуровневую систему защиты от различных типов атак и злоупотреблений.

---

## 🛡️ Уровни защиты

### 1. Rate Limiting (Ограничение частоты запросов)

**Что защищает:**
- DDoS атаки
- Чрезмерное использование ресурсов
- Автоматизированные скрипты

**Лимиты:**
- **Общие запросы:** 60 запросов/минуту, 1000 запросов/час
- **API эндпоинты:** 30 запросов/минуту
- **Генерация контента:** 50 генераций/час
- **Webhook:** 100 запросов/минуту

**Реализация:**
```python
from generator.security import rate_limit

@rate_limit(max_per_minute=30)
def my_view(request):
    # Ваш код
```

---

### 2. IP Блокировка

**Что защищает:**
- Повторяющиеся атаки
- Подозрительная активность
- Брутфорс попытки

**Триггеры блокировки:**
- 5+ неудачных попыток доступа
- Подозрительные паттерны в запросах
- SQL injection попытки
- XSS попытки

**Длительность блокировки:**
- Автоматическая: 30 минут
- Ручная: настраивается

**Код:**
```python
from generator.security import BlockList

# Заблокировать IP
BlockList.block_ip('192.168.1.1', 'Brute force attempt', duration_minutes=60)

# Проверить блокировку
if BlockList.is_ip_blocked(ip):
    return HttpResponseForbidden()
```

---

### 3. Блокировка токенов

**Что защищает:**
- Утечка токенов
- Злоупотребление доступом
- Компрометированные токены

**Типы блокировки:**
- **Временная:** автоматически при подозрительной активности
- **Постоянная:** ручная блокировка админом

**Код:**
```python
from generator.security import BlockList

# Заблокировать токен навсегда
BlockList.block_token('uuid-токена', 'Compromised')

# Проверить блокировку
if BlockList.is_token_blocked(token):
    return JsonResponse({'error': 'Token blocked'}, status=403)
```

---

### 4. Обнаружение подозрительной активности

**Что отслеживается:**
- Необычные паттерны использования
- Подозрительный User-Agent
- SQL injection попытки
- XSS попытки
- Чрезмерное количество запросов
- Необычные HTTP методы

**Автоматические действия:**
- Логирование события
- Увеличение счетчика подозрительной активности
- Блокировка при превышении порога (10 событий)

**Код:**
```python
from generator.security import SecurityMonitor

# Залогировать подозрительную активность
SecurityMonitor.log_suspicious_activity(
    identifier='ip:192.168.1.1',
    activity_type='sql_injection_attempt',
    details='Found UNION SELECT in input'
)
```

---

### 5. Защита от SQL Injection

**Методы защиты:**
- Django ORM (параметризованные запросы)
- Валидация всех входных данных
- Обнаружение SQL паттернов в тексте
- Автоматическая блокировка при обнаружении

**Проверяемые паттерны:**
- `UNION SELECT`
- `DROP TABLE`
- `INSERT INTO`
- `DELETE FROM`
- `OR 1=1`
- SQL комментарии (`--`, `#`, `/*`)

**Код:**
```python
from generator.security import InputSanitizer

text = request.POST.get('content')
is_suspicious, reason = InputSanitizer.is_suspicious_input(text)

if is_suspicious:
    # Логируем и блокируем
    SecurityMonitor.log_suspicious_activity(...)
```

---

### 6. Защита от XSS (Cross-Site Scripting)

**Методы защиты:**
- Django auto-escaping в шаблонах
- CSP (Content Security Policy) заголовки
- Валидация HTML тегов в пользовательском вводе
- Фильтрация JavaScript кода

**Проверяемые паттерны:**
- `<script>` теги
- `javascript:` протокол
- Event handlers (`onerror`, `onclick`)
- `<iframe>` теги

**CSP заголовок:**
```
Content-Security-Policy: default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
```

---

### 7. Защита Webhook

**Что защищает:**
- Поддельные запросы от "имени" Telegram
- Флуд webhook эндпоинта
- Man-in-the-middle атаки

**Методы:**
- Проверка секретного токена в заголовке
- Rate limiting (100 req/min)
- Валидация структуры update
- Проверка метода запроса (только POST)

**Код:**
```python
from generator.security import WebhookSecurity

is_valid, error = WebhookSecurity.verify_telegram_request(
    request, 
    settings.TELEGRAM_WEBHOOK_SECRET
)

if not is_valid:
    return HttpResponseForbidden(error)
```

---

### 8. Безопасные HTTP заголовки

**Автоматически добавляемые заголовки:**

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; ...
```

**Для HTTPS (production, Docker Nginx на :443):**

Сертификат: `bash deploy/generate-ssl-ip.sh` → `ssl/cert.pem`, `ssl/key.pem` (см. [ssl/README.md](ssl/README.md)).

HSTS через `SECURE_HSTS_SECONDS` в `.env` (`0` для IP с самоподписанным сертификатом, `31536000` после домена с Let's Encrypt):

```http
Strict-Transport-Security: max-age=...
```

---

### 9. Логирование и аудит

**Что логируется:**

1. **Безопасность:**
   - Все блокировки IP/токенов
   - Подозрительная активность
   - Неудачные попытки доступа
   - SQL/XSS попытки

2. **Аудит:**
   - Создание токенов
   - Генерация контента
   - Webhook запросы
   - Ошибки 4xx/5xx

**Формат логов:**
```json
{
  "timestamp": "2026-01-12T10:30:00Z",
  "event_type": "blocked_access",
  "identifier": "ip:192.168.1.1",
  "details": {
    "path": "/api/generate/",
    "reason": "Too many failed attempts"
  },
  "severity": "WARNING"
}
```

**Хранение:**
- Логи: stdout/файлы (настраивается)
- Критичные события: Redis/Cache (24 часа)

---

## 🔧 Настройка в Django

### 1. Добавьте middleware в `settings.py`

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    
    # Безопасность (добавить после стандартных)
    'generator.security_middleware.SecurityMiddleware',
    'generator.middleware.TokenAccessMiddleware',
    'generator.security_middleware.TokenSecurityMiddleware',
    'generator.security_middleware.AuditLogMiddleware',
    
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### 2. Настройте безопасность в `.env`

```bash
# Production settings
DEBUG=False
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Rate limiting
MAX_REQUESTS_PER_MINUTE=60
MAX_GENERATIONS_PER_HOUR=50

# Блокировка
MAX_FAILED_ATTEMPTS=5
BLOCK_DURATION_MINUTES=30
```

### 3. Настройте Redis/Cache

Для rate limiting и блокировок нужен кеш:

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

---

## 🎯 Использование декораторов

### Rate Limiting

```python
from generator.security import rate_limit

@rate_limit(max_per_minute=20)
def expensive_view(request):
    # Код view
    pass
```

### Проверка блокировки IP

```python
from generator.security import check_ip_block

@check_ip_block
def protected_view(request):
    # Код view
    pass
```

### Очистка ввода

```python
from generator.security import sanitize_input

@sanitize_input
def user_input_view(request):
    # Все POST данные автоматически проверяются
    pass
```

### Комбинированная защита

```python
from generator.security import rate_limit, check_ip_block, sanitize_input

@check_ip_block
@rate_limit(max_per_minute=10)
@sanitize_input
def super_protected_view(request):
    # Максимальная защита
    pass
```

---

## 🚨 Реагирование на инциденты

### Ручная блокировка IP

```bash
# Через Django shell
python manage.py shell

>>> from generator.security import BlockList
>>> BlockList.block_ip('192.168.1.100', 'Manual block - attack detected', duration_minutes=1440)
```

### Ручная блокировка токена

```bash
>>> from generator.security import BlockList
>>> BlockList.block_token('uuid-токена', 'Compromised - leaked online')
```

### Просмотр блокировок

```bash
>>> from django.core.cache import cache
>>> 
>>> # Все заблокированные IP
>>> blocked_ips = cache.keys('blocked_ip:*')
>>> for key in blocked_ips:
>>>     print(f"{key}: {cache.get(key)}")
>>> 
>>> # Все заблокированные токены
>>> blocked_tokens = cache.keys('blocked_token:*')
>>> for key in blocked_tokens:
>>>     print(f"{key}: {cache.get(key)}")
```

### Разблокировка

```bash
>>> from django.core.cache import cache
>>> 
>>> # Разблокировать IP
>>> cache.delete('blocked_ip:192.168.1.100')
>>> 
>>> # Разблокировать токен
>>> cache.delete('blocked_token:uuid-токена')
```

---

## 📊 Мониторинг

### Просмотр логов безопасности

```bash
# Все логи
tail -f logs/security.log

# Только критичные
tail -f logs/security.log | grep CRITICAL

# Только блокировки
tail -f logs/security.log | grep blocked
```

### Статистика из Redis

```python
from django.core.cache import cache

# Последние события безопасности
security_keys = cache.keys('security_log:*')
for key in security_keys[-10:]:  # Последние 10
    event = cache.get(key)
    print(event)
```

### Метрики для отслеживания

1. **Rate limit превышения** - частота блокировок
2. **IP блокировки** - количество и причины
3. **Токен блокировки** - скомпрометированные токены
4. **Подозрительная активность** - типы и частота
5. **Ошибки 4xx/5xx** - общая стабильность

---

## 🔍 Типичные атаки и защита

### 1. Брутфорс токенов

**Атака:** Перебор UUID токенов
**Защита:**
- Rate limiting (макс. 60 попыток/мин)
- Блокировка после 5 неудачных попыток
- UUID v4 (128 бит энтропии = 2^128 вариантов)

### 2. DDoS

**Атака:** Множество запросов с разных IP
**Защита:**
- Rate limiting на уровне middleware
- Блокировка подозрительных IP
- Cloudflare/CDN (опционально)

### 3. SQL Injection

**Атака:** `'; DROP TABLE users; --`
**Защита:**
- Django ORM (автоматическая экранировка)
- Валидация входных данных
- Обнаружение SQL паттернов

### 4. XSS

**Атака:** `<script>alert('XSS')</script>`
**Защита:**
- Django auto-escaping
- CSP заголовки
- Валидация HTML тегов

### 5. Утечка токенов

**Атака:** Украденный токен используется злоумышленником
**Защита:**
- Мониторинг необычной активности
- Автоматическая блокировка при подозрении
- Короткий срок жизни токенов

### 6. Webhook spoofing

**Атака:** Поддельные запросы к webhook
**Защита:**
- Секретный токен в заголовке
- Валидация структуры данных
- HTTPS only

---

## ✅ Чек-лист безопасности

### Перед запуском в продакшн:

- [ ] `DEBUG=False` в `.env`
- [ ] Установлен `DJANGO_SECRET_KEY` (уникальный)
- [ ] Настроен `ALLOWED_HOSTS`
- [ ] Включен HTTPS (`SECURE_SSL_REDIRECT=True`)
- [ ] Настроены secure cookies
- [ ] Включен HSTS
- [ ] Redis/Cache настроен для rate limiting
- [ ] Все middleware активированы
- [ ] Логирование настроено
- [ ] Webhook secret установлен
- [ ] CSP заголовки настроены
- [ ] Регулярные бэкапы базы данных
- [ ] Мониторинг логов настроен
- [ ] План реагирования на инциденты готов

### Регулярное обслуживание:

- [ ] Проверка логов безопасности (ежедневно)
- [ ] Анализ заблокированных IP (еженедельно)
- [ ] Обновление зависимостей (ежемесячно)
- [ ] Аудит безопасности (ежеквартально)
- [ ] Тестирование на проникновение (ежегодно)

---

## 📚 Дополнительные рекомендации

### 1. Используйте HTTPS везде

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Остальная конфигурация
}
```

### 2. Настройте fail2ban

```ini
# /etc/fail2ban/jail.local
[ghostwriter]
enabled = true
port = http,https
filter = ghostwriter
logpath = /path/to/logs/security.log
maxretry = 3
bantime = 3600
```

### 3. Регулярно обновляйте зависимости

```bash
# Проверка уязвимостей
pip install safety
safety check

# Обновление пакетов
pip list --outdated
pip install -U package_name
```

### 4. Используйте Sentry для мониторинга

```python
# settings.py
import sentry_sdk

sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=1.0,
)
```

---

## 🆘 Контакты

При обнаружении уязвимости:
- Email: security@ghostwriter.com (замените на реальный)
- Telegram: @lavrovartem
- Не публикуйте уязвимости публично до фикса!

---

**Безопасность - это процесс, а не одноразовое действие. Регулярно проверяйте и обновляйте защиту!** 🔒
