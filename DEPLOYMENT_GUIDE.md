# Руководство по развёртыванию Ghostwriter в Production

**Версия:** 2.4  
**Дата:** май 2026  
**Статус:** Production Ready

См. также: [README.md — Deployment](README.md#-deployment) · [DEPLOY_UPDATE.md](DEPLOY_UPDATE.md)

---

## Содержание

1. [Архитектура](#архитектура)
2. [Порты production](#порты-production)
3. [Требования к серверу](#требования-к-серверу)
4. [Подготовка: ключи и токены](#подготовка-ключи-и-токены)
5. [Пошаговый деплой на облачном сервере](#пошаговый-деплой-на-облачном-сервере)
6. [Настройка домена и SSL](#настройка-домена-и-ssl)
7. [Обновление проекта с Git](#обновление-проекта-с-git)
8. [Переменные окружения](#переменные-окружения)
9. [Миграции и команды Django](#миграции-и-команды-django)
10. [Деплой Flask (зарубежный сервер)](#деплой-flask-зарубежный-сервер)
11. [Резервное копирование](#резервное-копирование)
12. [Устранение неполадок](#устранение-неполадок)
13. [Чеклист перед запуском](#чеклист-перед-запуском)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    ОБЛАЧНЫЙ СЕРВЕР (РФ)                         │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐          │
│  │  Nginx  │──│ Django  │──│ Postgres │  │  Redis  │          │
│  │ :8010   │  │  :8000  │  │  :5432   │  │  :6379  │          │
│  │ (хост)  │  └────┬────┘  └──────────┘  └─────────┘          │
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
- **Nginx** — reverse proxy и статика. Снаружи: `http://<сервер>:8010` (порт 443 на хосте **не** используется).

---

## Порты production

| Где | Порт | Назначение |
|-----|------|------------|
| Хост (сервер) | **8010** | Основной доступ: `http://<IP или домен>:8010` |
| Хост (опционально) | **8443** | HTTPS, если раскомментировать `8443:8443` в compose и HTTPS в `nginx.prod.conf` |
| Docker (Nginx) | 80 | Проброс `8010:80` |
| Docker (Django) | 8000 | Только внутри compose (`http://django:8000` для бота) |

В `docker-compose.production.yml` по умолчанию только `"8010:80"`. Порт **443 на хосте не занимается** (нет конфликта с системным nginx).

---

## Требования к серверу

**Минимальные (основной сервер):**
- ОС: Ubuntu 20.04+ / Debian 11+ / иной Linux с Docker.
- RAM: 2 GB (рекомендуется 4 GB).
- CPU: 2 ядра.
- Диск: 20 GB SSD.
- Сеть: порт **8010** открыт в firewall; при опциональном HTTPS — **8443** (не 443).

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
- Webhook URL в кабинете ЮКасса: `http://ВАШ_ДОМЕН:8010/api/payments/yookassa/webhook/` (или `https://...:8443`, если включили опциональный HTTPS).

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
| `SITE_URL` | `http://yourdomain.com:8010` (или `https://yourdomain.com:8443` при опциональном HTTPS) |
| `EXECUTOR_*` | Реквизиты для оферты |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | Для приёма платежей |

Опционально: `TELEGRAM_SUPPORT_GROUP_URL` (ссылка на группу поддержки), `TELEGRAM_ADMIN_IDS`, `DJANGO_API_KEY`.

Сохраните файл.

### Шаг 4. SSL (опционально, порт 8443)

Для **HTTP на 8010** сертификаты **не нужны**. HTTPS только если раскомментируете `8443:8443` в `docker-compose.production.yml` и блок `server` на 8443 в `nginx.prod.conf`.

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem -subj "/CN=yourdomain.com"
chmod 600 ssl/*.pem
```

### Шаг 5. Директория бэкапов и запуск контейнеров

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

### Шаг 6. Проверка статуса

```bash
docker compose -f docker-compose.production.yml ps
```

Ожидаемый вид: все сервисы `Up`, у `django`, `db`, `redis`, `nginx` может быть `(healthy)`.

Просмотр логов:

```bash
docker compose -f docker-compose.production.yml logs -f
```

### Шаг 7. Суперпользователь и проверка сайта

```bash
docker compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

Откройте в браузере:

- `http://yourdomain.com:8010` и `http://yourdomain.com:8010/admin/`
- Опционально HTTPS: `https://yourdomain.com:8443` (если включили 8443 в compose)

### Шаг 8. Бот

Бот запущен в контейнере в режиме **polling**. Проверьте в Telegram: отправьте боту `/start` — должно открыться главное меню (Тарифы, Мои токены, Техподдержка, Оставить отзыв).

---

## Настройка домена

1. **DNS:** A-записи для домена и www на IP сервера.
2. В `.env`: `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`, `SITE_URL=http://yourdomain.com:8010`.
3. Откройте в firewall порт **8010** (`ufw allow 8010/tcp`).
4. После смены `.env`:

```bash
docker compose -f docker-compose.production.yml up -d
```

### Переход с IP на домен

```bash
cd /opt/ghostwriter
sed -i 's|SITE_URL=.*|SITE_URL=http://ghostcopywriter.ru:8010|' .env
docker compose -f docker-compose.production.yml up -d
```

Сайт: `http://ghostcopywriter.ru:8010` (порт **8010** обязателен в URL, если нет внешнего прокси на 80/443).

---

## Обновление проекта с Git

Чтобы подтянуть новые коммиты и перезапустить приложение **без повторного полного деплоя**:

```bash
cd /opt/ghostwriter
git pull
docker compose -f docker-compose.production.yml up -d --build
```

- **`git pull`** — забирает изменения из удалённого репозитория (ветка по умолчанию, обычно `main` или `dev`). Если вы работаете в другой ветке, сначала переключитесь: `git checkout имя-ветки`, затем `git pull`.
- **`up -d --build`** — пересобирает образы при изменении Dockerfile/зависимостей и перезапускает контейнеры. Миграции применятся автоматически при старте Django (entrypoint).

Если в проекте появились **новые миграции**, они применятся при старте контейнера `django`. Проверить статус миграций:

```bash
docker compose -f docker-compose.production.yml exec django python manage.py showmigrations
```

Файл `.env` при `git pull` не перезаписывается (он в `.gitignore`), настройки окружения сохраняются.

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
- Проверка с хоста через Nginx: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8010/` (ожидается `200` или `302`).

**Сайт не открывается по адресу без порта**

- Production слушает **8010**, а не 80. Используйте `http://<домен>:8010`, не `http://<домен>/`.
- Убедитесь, что в firewall/security group открыт порт **8010** (`ufw allow 8010/tcp` и т.п.).

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
- [ ] Порт **8010** открыт; `curl http://127.0.0.1:8010/` отвечает.
- [ ] Выполнено: `docker compose -f docker-compose.production.yml up -d --build`.
- [ ] Все контейнеры в статусе Up (при необходимости healthy).
- [ ] Миграции применены (при старте Django или вручную).
- [ ] Создан суперпользователь.
- [ ] В `.env` указан `SITE_URL` с `:8010`.
- [ ] Бот в Telegram отвечает на `/start`.

---

**Версия документа:** 2.4  
**Последнее обновление:** май 2026 — production HTTP на порту **8010**
