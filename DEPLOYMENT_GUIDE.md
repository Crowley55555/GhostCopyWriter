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
6. [SSL-сертификат](#ssl-сертификат-самоподписанный-для-ip)
7. [Настройка домена](#настройка-домена-опционально-вместо-ip)
8. [Обновление проекта с Git](#обновление-проекта-с-git)
9. [Переменные окружения](#переменные-окружения)
10. [Миграции и команды Django](#миграции-и-команды-django)
11. [Деплой Flask (зарубежный сервер)](#деплой-flask-зарубежный-сервер)
12. [Резервное копирование](#резервное-копирование)
13. [Устранение неполадок](#устранение-неполадок)
14. [Чеклист перед запуском](#чеклист-перед-запуском)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    ОБЛАЧНЫЙ СЕРВЕР (РФ)                         │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐          │
│  │  Nginx  │──│ Django  │──│ Postgres │  │  Redis  │          │
│  │ :443    │  │  :8000  │  │  :5432   │  │  :6379  │          │
│  │ (HTTPS) │  └────┬────┘  └──────────┘  └─────────┘          │
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
- **Nginx** — reverse proxy, SSL (самоподписанный сертификат по IP). Снаружи: `https://<IP>` на порту **443**.

---

## Порты production

| Где | Порт | Назначение |
|-----|------|------------|
| Хост (сервер) | **443** | HTTPS: `https://<IP>/` (самоподписанный SSL в `ssl/`) |
| Docker (Nginx) | 443 | Проброс `443:443` |
| Docker (Django) | 8000 | Только внутри compose (`http://django:8000` для бота) |

В `docker-compose.production.yml`: `"443:443"`. Перед первым запуском: `bash deploy/generate-ssl-ip.sh`.

---

## Требования к серверу

**Минимальные (основной сервер):**
- ОС: Ubuntu 20.04+ / Debian 11+ / иной Linux с Docker.
- RAM: 2 GB (рекомендуется 4 GB).
- CPU: 2 ядра.
- Диск: 20 GB SSD.
- Сеть: порт **443** открыт в firewall (TCP, источник `0.0.0.0/0`).

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
- Webhook URL в кабинете ЮКасса: `https://85.208.86.148/api/payments/yookassa/webhook/` (или `https://ваш-домен/...` при привязке домена).

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
| `SITE_URL` | `https://85.208.86.148` (или `https://ваш-домен.ru` с Let's Encrypt) |
| `SECURE_HSTS_SECONDS` | `0` для IP с самоподписанным сертификатом; `31536000` после домена |
| `EXECUTOR_*` | Реквизиты для оферты |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | Для приёма платежей |

Опционально: `TELEGRAM_SUPPORT_GROUP_URL` (ссылка на группу поддержки), `TELEGRAM_ADMIN_IDS`, `DJANGO_API_KEY`.

Сохраните файл.

### Шаг 4. SSL-сертификат (самоподписанный для IP)

См. также [ssl/README.md](ssl/README.md).

```bash
cd /opt/ghostwriter   # или /opt/GhostCopyWriter — ваш путь к репозиторию
bash deploy/generate-ssl-ip.sh 85.208.86.148
# bash deploy/generate-ssl-ip.sh          # тот же IP по умолчанию
```

| Параметр | Описание |
|----------|----------|
| Скрипт | `deploy/generate-ssl-ip.sh` |
| Аргумент `$1` | IP сервера (по умолчанию `85.208.86.148`) |
| Результат | `ssl/cert.pem`, `ssl/key.pem` (в Git не попадают) |
| OpenSSL | SAN `IP:ваш_ip`, срок 365 дней |

Браузер покажет предупреждение о недоверенном сертификате — для IP без домена это нормально. Примите риск и продолжите.

Перед запуском:

- Порт **443** на хосте свободен: `sudo ss -tlnp | grep ':443'` (при необходимости `docker stop mtg-proxy`).
- В `.env`: `SITE_URL=https://85.208.86.148`, `USE_HTTPS=true`, `SECURE_HSTS_SECONDS=0`.

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

- `https://85.208.86.148` и `https://85.208.86.148/admin/` (примите предупреждение о сертификате)

### Шаг 8. Бот

Бот запущен в контейнере в режиме **polling**. Проверьте в Telegram: отправьте боту `/start` — должно открыться главное меню (Тарифы, Мои токены, Техподдержка, Оставить отзыв).

---

## SSL-сертификат (самоподписанный для IP)

Краткая справка (дублирует шаг 4 для быстрого поиска):

```bash
bash deploy/generate-ssl-ip.sh [IP]
docker compose -f docker-compose.production.yml restart nginx   # после смены IP/сертификата
curl -Ik https://85.208.86.148/
```

**Ограничения:** нет доверенного HTTPS без домена; webhook ЮKassa может требовать валидный сертификат — при проблемах привяжите домен и Let's Encrypt.

---

## Настройка домена (опционально, вместо IP)

1. **DNS:** A-запись домена на IP сервера.
2. Let's Encrypt (системный certbot или обновление `ssl/`).
3. В `.env`: `ALLOWED_HOSTS=yourdomain.com`, `SITE_URL=https://yourdomain.com`, `SECURE_HSTS_SECONDS=31536000`.
4. `docker compose -f docker-compose.production.yml up -d --force-recreate django nginx`

---

## Обновление проекта с Git

Чтобы подтянуть новые коммиты и перезапустить приложение **без повторного полного деплоя**:

```bash
cd /opt/ghostwriter
git pull

# Если после pull нет ssl/*.pem (новый сервер или чистый клон):
# bash deploy/generate-ssl-ip.sh 85.208.86.148

docker compose -f docker-compose.production.yml up -d --build
```

Или используйте скрипт: `bash deploy/update.sh` (см. [DEPLOY_UPDATE.md](DEPLOY_UPDATE.md)).

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
- Проверка HTTPS: `curl -Ik https://85.208.86.148/` (ожидается `200` или `302`, `-k` для самоподписанного).
- `docker ps | grep nginx-prod` → `0.0.0.0:443->443/tcp`.

**Сайт не открывается**

- URL: `https://85.208.86.148` (не `http://`, не без порта на другом сервисе).
- Firewall: входящий **TCP 443**, `0.0.0.0/0`.
- Порт 443 не занят другим контейнером: `sudo ss -tlnp | grep ':443'`.
- Есть `ssl/cert.pem` и `ssl/key.pem`: `bash deploy/generate-ssl-ip.sh`.

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
- [ ] Выполнено `bash deploy/generate-ssl-ip.sh`; порт **443** открыт в firewall.
- [ ] `curl -Ik https://85.208.86.148/` отвечает (с сервера).
- [ ] Выполнено: `docker compose -f docker-compose.production.yml up -d --build`.
- [ ] Все контейнеры в статусе Up (при необходимости healthy).
- [ ] Миграции применены (при старте Django или вручную).
- [ ] Создан суперпользователь.
- [ ] В `.env`: `SITE_URL=https://85.208.86.148`, `USE_HTTPS=true`, `SECURE_HSTS_SECONDS=0`.
- [ ] Бот в Telegram отвечает на `/start`.

---

**Версия документа:** 2.4  
**Последнее обновление:** май 2026 — production HTTPS на порту **443** (IP, самоподписанный SSL)
