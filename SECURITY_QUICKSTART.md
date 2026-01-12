# 🚀 Быстрый старт: Безопасность

## Установка за 5 минут

### 1️⃣ Установите зависимости

```bash
pip install django-redis redis django-ipware
```

Или обновите из requirements.txt:
```bash
pip install -r requirements.txt
```

### 2️⃣ Настройте .env

Добавьте в `.env`:

```bash
# Безопасность
MAX_REQUESTS_PER_MINUTE=60
MAX_REQUESTS_PER_HOUR=1000
MAX_GENERATIONS_PER_HOUR=50
MAX_FAILED_ATTEMPTS=5
BLOCK_DURATION_MINUTES=30
SUSPICIOUS_ACTIVITY_THRESHOLD=10

# Redis (для продакшена)
REDIS_URL=redis://127.0.0.1:6379/1

# Production (включить в продакшене)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0
```

### 3️⃣ Middleware уже настроены!

В `ghostwriter/settings.py` уже добавлены все необходимые middleware:
- ✅ `SecurityMiddleware` - rate limiting, IP блокировка
- ✅ `TokenSecurityMiddleware` - проверка токенов
- ✅ `AuditLogMiddleware` - логирование

### 4️⃣ Создайте директорию для логов

```bash
mkdir logs
```

### 5️⃣ Готово! 🎉

Перезапустите Django:
```bash
python manage.py runserver
```

---

## ✅ Что уже работает

### Автоматическая защита:

1. **Rate Limiting**
   - 60 запросов/минуту (общие)
   - 30 запросов/минуту (API)
   - 20 запросов/минуту (генерация)
   - 100 запросов/минуту (webhook)

2. **IP Блокировка**
   - Автоматически после 5 неудачных попыток
   - Длительность: 30 минут

3. **Защита от атак**
   - SQL Injection detection
   - XSS detection
   - Подозрительные User-Agent

4. **Безопасные заголовки**
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - X-XSS-Protection: 1; mode=block
   - Content-Security-Policy

5. **Webhook защита**
   - Проверка секретного токена
   - Валидация структуры данных
   - Rate limiting

6. **Логирование**
   - Все события безопасности в `logs/security.log`
   - Общие логи в `logs/django.log`

---

## 🔧 Дополнительная настройка

### Для продакшена: Установите Redis

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
Скачайте с https://github.com/microsoftarchive/redis/releases

### Включите Redis в settings.py

Раскомментируйте в `ghostwriter/settings.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### Включите HTTPS (production)

В `.env`:
```bash
DEBUG=False
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

---

## 📊 Проверка работы

### Тест Rate Limiting

```bash
# Отправьте 100 запросов подряд
for i in {1..100}; do
  curl http://localhost:8000/
  echo "Request $i"
done
```

После 60 запросов получите ошибку 429 (Too Many Requests).

### Тест блокировки

```bash
# 6 неудачных попыток доступа
for i in {1..6}; do
  curl http://localhost:8000/auth/token/invalid-token/
done
```

После 5 попыток IP будет заблокирован на 30 минут.

### Просмотр логов

```bash
# Логи безопасности
tail -f logs/security.log

# Общие логи
tail -f logs/django.log

# Только ошибки
tail -f logs/security.log | grep ERROR
```

---

## 🆘 Разблокировка

### Через Django shell

```bash
python manage.py shell

>>> from generator.security import BlockList
>>> from django.core.cache import cache
>>> 
>>> # Разблокировать IP
>>> cache.delete('blocked_ip:192.168.1.100')
>>> 
>>> # Разблокировать токен
>>> cache.delete('blocked_token:uuid-токена')
>>> 
>>> # Посмотреть все блокировки
>>> for key in cache.keys('blocked_*'):
...     print(f"{key}: {cache.get(key)}")
```

---

## 📖 Полная документация

Читайте `SECURITY.md` для:
- Детального описания всех механизмов защиты
- Примеров использования декораторов
- Настройки для production
- Мониторинга и реагирования на инциденты

---

## 🎯 Рекомендации

### Для разработки (локально):
- ✅ LocMemCache (уже настроен)
- ✅ DEBUG=True
- ✅ HTTP (без SSL)

### Для production:
- ✅ Redis (обязательно!)
- ✅ DEBUG=False
- ✅ HTTPS (с сертификатом)
- ✅ Мониторинг логов
- ✅ Регулярные бэкапы

---

**Защита активна! Ваш проект защищен от большинства атак! 🛡️**
