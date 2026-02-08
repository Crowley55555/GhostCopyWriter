# Руководство по развёртыванию Ghostwriter в Production

**Версия:** 2.3  
**Дата:** февраль 2026  
**Статус:** Production Ready

---

## Содержание

1. [Архитектура](#архитектура)
2. [Требования к серверу](#требования-к-серверу)
3. [Подготовка: ключи и токены](#подготовка-ключи-и-токены)
4. [Пошаговый деплой на облачном сервере](#пошаговый-деплой-на-облачном-сервере)
5. [Настройка домена и SSL](#настройка-домена-и-ssl)
6. [Переменные окружения](#переменные-окружения)
7. [Миграции и команды Django](#миграции-и-команды-django)
8. [Деплой Flask (зарубежный сервер)](#деплой-flask-зарубежный-сервер)
9. [Резервное копирование](#резервное-копирование)
10. [Устранение неполадок](#устранение-неполадок)
11. [Чеклист перед запуском](#чеклист-перед-запуском)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    ОБЛАЧНЫЙ СЕРВЕР (РФ)                         │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐          │
│  │  Nginx  │──│ Django  │──│ Postgres │  │  Redis  │          │
│  │  :80    │  │  :8000  │  │  :5432   │  │  :6379  │          │
│  │  :443   │  └────┬────┘  └──────────┘  └─────────┘          │
│  └─────────┘       │                                            │
│                    │  ┌─────────────┐                           │
│                    └──│ Telegram Bot│  (polling)                 │
│                       └─────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTPS (шифрование)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ЗАРУБЕЖНЫЙ СЕРВЕР (опционально)                  │
│  Nginx → Flask :5000  (OpenAI GPT + DALL-E)                     │
└─────────────────────────────────────────────────────────────────┘
```

**Компоненты на основном сервере:**
- **Django** — веб-приложение, API токенов/платежей/поддержки/отзывов, GigaChat.
- **Telegram Bot** — меню (тарифы, токены, техподдержка, отзыв), оплата, выдача ссылок (режим polling).
- **PostgreSQL** — база данных.
- **Redis** — кеш.
- **Nginx** — reverse proxy, SSL, статика.

---

## Требования к серверу

**Минимальные (основной сервер):**
- ОС: Ubuntu 20.04+ / Debian 11+ / иной Linux с Docker.
- RAM: 2 GB (рекомендуется 4 GB).
- CPU: 2 ядра.
- Диск: 20 GB SSD.
- Сеть: порты 80 и 443 открыты.

**Рекомендуемые:** 4 GB RAM, 4 ядра, 50 GB SSD.

---

## Подготовка: ключи и токены

Перед деплоем подготовьте значения для `.env`.

### 1. Django Secret Key

```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Сохраните вывод в `DJANGO_SECRET_KEY`.

### 2. Ключ шифрования Django–Flask (Fernet)

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Один и тот же ключ должен быть на Django и на Flask сервере → `GENERATOR_ENCRYPTION_KEY`.

### 3. Telegram Bot

- В [@BotFather](https://t.me/BotFather): `/newbot` → имя и username.
- Сохраните токен → `TELEGRAM_BOT_TOKEN`.
- Username без `@` → `BOT_USERNAME`.

### 4. Секрет для webhook (если позже будете использовать webhook)

```bash
openssl rand -hex 32
```

→ `TELEGRAM_WEBHOOK_SECRET`. Сейчас бот в production работает в **polling**, webhook опционален.

### 5. GigaChat

- [developers.sber.ru](https://developers.sber.ru/) → проект → GigaChat API → Authorization Key.
- → `GIGACHAT_CREDENTIALS`. Scope: `GIGACHAT_API_PERS` → `GIGACHAT_SCOPE`.

### 6. ЮКасса (платежи)

- [yookassa.ru](https://yookassa.ru/) → Интеграция → Ключи API.
- → `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`.
- Webhook URL в кабинете: `https://ВАШ_ДОМЕН/api/payments/yookassa/webhook/`.

### 7. OpenAI (только для Flask-сервера)

- [platform.openai.com](https://platform.openai.com/api-keys) → API Keys.
- → `OPENAI_API_KEY` (на Flask-сервере).

---

## Пошаговый деплой на облачном сервере

### Шаг 1. Установка Docker и Docker Compose

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"

# Docker Compose (плагин v2)
sudo apt install -y docker-compose-plugin

# Проверка (после перелогина или newgrp docker)
docker --version
docker compose version
```

Если используете классический `docker-compose` (v1):

```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

В дальнейшем замените `docker compose` на `docker-compose`, если у вас v1.

### Шаг 2. Клонирование проекта

```bash
sudo mkdir -p /opt/ghostwriter
cd /opt/ghostwriter
sudo git clone https://github.com/YOUR_REPO/ghostwriter.git .
sudo chown -R "$USER:$USER" /opt/ghostwriter
cd /opt/ghostwriter
```

### Шаг 3. Файл окружения .env

```bash
cp env.production.example .env
chmod 600 .env
nano .env
```

Заполните **обязательные** переменные:

| Переменная | Описание |
|------------|----------|
| `DJANGO_SECRET_KEY` | Сгенерированный секретный ключ |
| `ALLOWED_HOSTS` | Домен и/или IP, через запятую без пробелов |
| `DEBUG` | `False` |
| `DB_PASSWORD` | Надёжный пароль БД (например 32+ символа) |
| `GIGACHAT_CREDENTIALS` | Ключ GigaChat |
| `GENERATOR_ENCRYPTION_KEY` | Fernet-ключ (тот же, что на Flask) |
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather |
| `BOT_USERNAME` | Username бота без @ |
| `TELEGRAM_WEBHOOK_SECRET` | Секрет (openssl rand -hex 32) |
| `SITE_URL` | URL сайта без слэша в конце, например `https://yourdomain.com` |
| `EXECUTOR_*` | Реквизиты для оферты |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | Для приёма платежей |

Опционально: `TELEGRAM_SUPPORT_GROUP_URL` (ссылка на группу поддержки), `TELEGRAM_ADMIN_IDS`, `DJANGO_API_KEY`.

Сохраните файл.

### Шаг 4. SSL-сертификаты

Создайте каталог и положите в него сертификаты:

```bash
mkdir -p /opt/ghostwriter/ssl
```

**Вариант A: Let's Encrypt**

```bash
sudo apt install -y certbot
# Временно остановите любой сервис на 80 порту
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com --email your@email.com --agree-tos --non-interactive
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/ghostwriter/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/ghostwriter/ssl/key.pem
sudo chown "$USER:$USER" /opt/ghostwriter/ssl/*.pem
chmod 600 /opt/ghostwriter/ssl/*.pem
```

**Вариант B: самоподписанный (только для теста)**

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /opt/ghostwriter/ssl/key.pem \
  -out /opt/ghostwriter/ssl/cert.pem \
  -subj "/CN=yourdomain.com"
chmod 600 /opt/ghostwriter/ssl/*.pem
```

### Шаг 5. Конфигурация Nginx

Подставьте свой домен в `nginx.prod.conf`:

```bash
nano nginx.prod.conf
```

Найдите `server_name` и укажите ваш домен, например:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

Сохраните.

### Шаг 6. Директория бэкапов и запуск контейнеров

```bash
mkdir -p /opt/ghostwriter/backups
cd /opt/ghostwriter

# Сборка и запуск (все миграции и collectstatic выполняются в entrypoint Django)
docker compose -f docker-compose.production.yml up -d --build
```

Если используете Docker Compose v1:

```bash
docker-compose -f docker-compose.production.yml up -d --build
```

### Шаг 7. Проверка статуса

```bash
docker compose -f docker-compose.production.yml ps
```

Ожидаемый вид: все сервисы `Up`, у `django`, `db`, `redis`, `nginx` может быть `(healthy)`.

Просмотр логов:

```bash
docker compose -f docker-compose.production.yml logs -f
```

### Шаг 8. Суперпользователь и проверка сайта

```bash
docker compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

Откройте в браузере: `https://yourdomain.com` и `https://yourdomain.com/admin/`.

### Шаг 9. Бот

Бот запущен в контейнере в режиме **polling**. Проверьте в Telegram: отправьте боту `/start` — должно открыться главное меню (Тарифы, Мои токены, Техподдержка, Оставить отзыв).

---

## Настройка домена и SSL

1. **DNS:** A-записи для домена и www на IP сервера.
2. В `.env`: `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`, `SITE_URL=https://yourdomain.com`.
3. После смены домена или сертификата перезапустите Nginx и при необходимости Django:

```bash
docker compose -f docker-compose.production.yml restart nginx
docker compose -f docker-compose.production.yml restart django
```

Обновление сертификатов Let's Encrypt (cron, раз в месяц):

```bash
0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/*.pem /opt/ghostwriter/ssl/ && docker compose -f /opt/ghostwriter/docker-compose.production.yml restart nginx
```

---

## Переменные окружения

Полный образец — в `env.production.example`. Кратко по группам:

- **Django:** `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG`, `DB_*`, `REDIS_URL`, `GIGACHAT_*`, `FLASK_EXTERNAL_URL`, `GENERATOR_ENCRYPTION_KEY`, `SITE_URL`, `USE_HTTPS`, `TELEGRAM_*`, `YOOKASSA_*`, `EXECUTOR_*`.
- **Бот:** те же `TELEGRAM_*`, `DJANGO_API_URL` (внутри Docker задаётся как `http://django:8000`), `TELEGRAM_SUPPORT_GROUP_URL`, `TELEGRAM_ADMIN_IDS` (опционально).

После изменения `.env` перезапустите контейнеры:

```bash
docker compose -f docker-compose.production.yml up -d
```

---

## Миграции и команды Django

Миграции применяются автоматически при старте контейнера Django (скрипт `docker-entrypoint.sh`). Текущие миграции включают:

- `0017_add_telegram_user_id_to_tokens` — защита от мультиаккаунтов.
- `0018_support_reviews` — тикеты поддержки, отзывы, чаты (SupportTicket, Review, SupportChat).

Ручной запуск миграций (если нужно):

```bash
docker compose -f docker-compose.production.yml exec django python manage.py migrate --noinput
```

Проверка списка миграций:

```bash
docker compose -f docker-compose.production.yml exec django python manage.py showmigrations
```

Другие полезные команды:

```bash
# Сбор статики (уже в entrypoint)
docker compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput

# Создание суперпользователя
docker compose -f docker-compose.production.yml exec django python manage.py createsuperuser

# Токен разработчика (если есть management-команда)
docker compose -f docker-compose.production.yml exec django python manage.py create_dev_token --name="Admin"

# Очистка токенов (если есть)
docker compose -f docker-compose.production.yml exec django python manage.py cleanup_tokens
```

---

## Деплой Flask (зарубежный сервер)

Для генерации через OpenAI разверните Flask на отдельном сервере.

1. Установите Docker (аналогично основному серверу).
2. Клонируйте проект или скопируйте каталог `flask_generator`.
3. В каталоге Flask создайте `.env` с:
   - `OPENAI_API_KEY`
   - `GENERATOR_ENCRYPTION_KEY` — **такой же**, как на Django.
   - При необходимости: `OPENAI_MODEL`, `DALLE_MODEL`.
4. Получите SSL для домена Flask (например, `flask.yourdomain.com`).
5. Запустите контейнеры Flask (по инструкции в `flask_generator/` или вашего `docker-compose.flask.yml`).
6. В `.env` на **Django** сервере укажите: `FLASK_EXTERNAL_URL=https://flask.yourdomain.com`.

---

## Резервное копирование

**Ручной бэкап БД:**

```bash
docker compose -f docker-compose.production.yml exec -T db \
  pg_dump -U ghostwriter ghostwriter > /opt/ghostwriter/backups/db_$(date +%Y%m%d_%H%M%S).sql
```

**Восстановление БД:**

```bash
docker compose -f docker-compose.production.yml exec -T db \
  psql -U ghostwriter ghostwriter < /opt/ghostwriter/backups/db_YYYYMMDD_HHMMSS.sql
```

Рекомендуется настроить регулярные бэкапы (cron) и копирование медиа и `.env`.

---

## Устранение неполадок

**Контейнеры не поднимаются**

```bash
docker compose -f docker-compose.production.yml logs django
docker compose -f docker-compose.production.yml config
```

**502 Bad Gateway**

- Проверьте, что контейнер `django` в состоянии healthy.
- Логи Nginx: `docker compose -f docker-compose.production.yml logs nginx`.
- Проверка Django изнутри сети: `docker compose -f docker-compose.production.yml exec django curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/`.

**База недоступна**

```bash
docker compose -f docker-compose.production.yml exec db pg_isready -U ghostwriter -d ghostwriter
docker compose -f docker-compose.production.yml restart db
```

**Бот не отвечает**

- Логи: `docker compose -f docker-compose.production.yml logs bot`.
- Проверьте в `.env`: `TELEGRAM_BOT_TOKEN`, `BOT_USERNAME`, `DJANGO_API_URL` (в compose задаётся как `http://django:8000`).
- Убедитесь, что контейнер `django` уже запущен (bot от него зависит).

**Статика не отдаётся**

- Повторно соберите статику:  
  `docker compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput`
- Проверьте, что в `nginx.prod.conf` указаны правильные пути к static/media (volumes `static_data`, `media_data`).

**Ошибки миграций**

```bash
docker compose -f docker-compose.production.yml exec django python manage.py showmigrations
# При необходимости откат и повтор:
# docker compose -f docker-compose.production.yml exec django python manage.py migrate generator 0016
# docker compose -f docker-compose.production.yml exec django python manage.py migrate
```

---

## Чеклист перед запуском

- [ ] Docker и Docker Compose установлены.
- [ ] Проект склонирован, `.env` создан из `env.production.example`.
- [ ] В `.env`: `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG=False`, `DB_PASSWORD`, `GIGACHAT_CREDENTIALS`, `GENERATOR_ENCRYPTION_KEY`, `TELEGRAM_BOT_TOKEN`, `BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET`, `SITE_URL`, реквизиты `EXECUTOR_*`.
- [ ] При приёме платежей: `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`; webhook в кабинете ЮКасса настроен.
- [ ] В `nginx.prod.conf` указан ваш `server_name`.
- [ ] Сертификаты лежат в `ssl/cert.pem` и `ssl/key.pem`, права 600.
- [ ] Выполнено: `docker compose -f docker-compose.production.yml up -d --build`.
- [ ] Все контейнеры в статусе Up (при необходимости healthy).
- [ ] Миграции применены (при старте Django или вручную).
- [ ] Создан суперпользователь.
- [ ] Сайт открывается по HTTPS, бот в Telegram отвечает на `/start`.

---

**Версия документа:** 2.3  
**Последнее обновление:** февраль 2026
