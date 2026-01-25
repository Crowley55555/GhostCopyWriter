# 🚀 Полное руководство по деплою Ghostwriter в Production

**Версия:** 2.2 (с защитой от мультиаккаунтов)  
**Дата:** 25 января 2026 г.  
**Статус:** Production Ready

---

## 📋 Содержание

1. [Архитектура системы](#архитектура-системы)
2. [Требования к серверу](#требования-к-серверу)
3. [Подготовка к деплою](#подготовка-к-деплою)
4. [Деплой Django на российском сервере](#деплой-django-на-российском-сервере)
5. [Деплой Flask на зарубежном сервере](#деплой-flask-на-зарубежном-сервере)
6. [Настройка домена и SSL](#настройка-домена-и-ssl)
7. [Настройка переменных окружения](#настройка-переменных-окружения)
8. [Применение миграций](#применение-миграций)
9. [Настройка платежных систем](#настройка-платежных-систем)
10. [Мониторинг и логирование](#мониторинг-и-логирование)
11. [Резервное копирование](#резервное-копирование)
12. [Troubleshooting](#troubleshooting)
13. [Checklist перед запуском](#checklist-перед-запуском)

---

## 🏗️ Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                    РОССИЙСКИЙ СЕРВЕР                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │  Nginx  │──│ Django  │──│ Postgres│  │  Redis  │           │
│  │  :80    │  │  :8000  │  │  :5432  │  │  :6379  │           │
│  │  :443   │  └────┬────┘  └─────────┘  └─────────┘           │
│  └─────────┘       │                                           │
│                    │       ┌─────────┐                         │
│                    └───────│   Bot   │                         │
│                            │ Telegram│                         │
│                            └─────────┘                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS API (шифрование)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ЗАРУБЕЖНЫЙ СЕРВЕР                              │
│  ┌─────────┐  ┌─────────┐                                      │
│  │  Nginx  │──│  Flask  │  OpenAI GPT + DALL-E                 │
│  │  :443   │  │  :5000  │                                      │
│  └─────────┘  └─────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Компоненты:**
- **Django** - основное приложение (генерация через GigaChat, токены, платежи)
- **Telegram Bot** - автоматическая выдача токенов, обработка платежей
- **PostgreSQL** - база данных
- **Redis** - кеширование и rate limiting
- **Nginx** - reverse proxy, SSL, статика
- **Flask** (отдельный сервер) - генерация через OpenAI

---

## 💻 Требования к серверу

### Российский сервер (Django + Bot)

**Минимальные:**
- OS: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- RAM: 2GB (4GB рекомендуется)
- CPU: 2 cores (4 cores рекомендуется)
- Disk: 20GB SSD
- Network: Публичный IP, порты 80, 443 открыты

**Рекомендуемые:**
- RAM: 8GB
- CPU: 4 cores
- Disk: 50GB SSD
- Swap: 2GB

### Зарубежный сервер (Flask)

**Минимальные:**
- OS: Ubuntu 20.04+ / Debian 11+
- RAM: 1GB (2GB рекомендуется)
- CPU: 1 core (2 cores рекомендуется)
- Disk: 10GB SSD
- Network: Публичный IP, порт 443 открыт

---

## 🔧 Подготовка к деплою

### 1. Установка Docker и Docker Compose

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version

# Перелогиньтесь для применения группы docker
exit
# (затем войдите снова)
```

### 2. Клонирование проекта

```bash
# Создайте директорию для проекта
sudo mkdir -p /opt/ghostwriter
cd /opt/ghostwriter

# Клонируйте репозиторий
sudo git clone https://github.com/your-repo/ghostwriter.git .

# Установите права
sudo chown -R $USER:$USER /opt/ghostwriter
```

### 3. Получение необходимых ключей и токенов

#### 3.1. Django Secret Key

```bash
# Генерация Django Secret Key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Скопируйте результат** - он понадобится для `DJANGO_SECRET_KEY` в `.env`

#### 3.2. Fernet Key для шифрования Django-Flask

```bash
# Генерация Fernet Key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**ВАЖНО:** Этот ключ должен быть **одинаковым** на Django и Flask серверах!

**Скопируйте результат** - он понадобится для `GENERATOR_ENCRYPTION_KEY` в `.env` на обоих серверах

#### 3.3. Telegram Bot Token

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Введите имя бота (например: `GhostCopywriter`)
4. Введите username (например: `ghostcopywriter_bot`)
5. **Скопируйте токен** - он понадобится для `TELEGRAM_BOT_TOKEN`

**Дополнительные настройки бота:**
```bash
# Установите описание
/setdescription - добавьте описание бота

# Установите команды
/setcommands - добавьте команды:
start - Начать работу
help - Справка
plans - Тарифы

# Установите аватар (опционально)
/setuserpic - загрузите изображение
```

#### 3.4. GigaChat Credentials

1. Зарегистрируйтесь на [https://developers.sber.ru/](https://developers.sber.ru/)
2. Создайте проект
3. Подключите продукт "GigaChat API"
4. Получите **Authorization Key** из личного кабинета
5. **Скопируйте ключ** - он понадобится для `GIGACHAT_CREDENTIALS`

**Альтернативно** (если используете OAuth2):
- `GIGACHAT_CLIENT_ID` - Client ID из личного кабинета
- `GIGACHAT_CLIENT_SECRET` - Client Secret из личного кабинета

#### 3.5. OpenAI API Key (для Flask сервера)

1. Зарегистрируйтесь на [https://platform.openai.com/](https://platform.openai.com/)
2. Перейдите в [API Keys](https://platform.openai.com/api-keys)
3. Создайте новый API ключ
4. **Скопируйте ключ** - он понадобится для `OPENAI_API_KEY` на Flask сервере

#### 3.6. Webhook Secret для Telegram

```bash
# Генерация Webhook Secret
openssl rand -hex 32
```

**Скопируйте результат** - он понадобится для `TELEGRAM_WEBHOOK_SECRET`

#### 3.7. ЮКасса (для приема платежей)

1. Зарегистрируйтесь на [https://yookassa.ru/](https://yookassa.ru/)
2. Перейдите в Личный кабинет → Интеграция → Ключи API
3. Получите:
   - `YOOKASSA_SHOP_ID` - ID магазина
   - `YOOKASSA_SECRET_KEY` - Секретный ключ

**Webhook URL для настройки в ЮКасса:**
```
https://yourdomain.com/api/payments/yookassa/webhook/
```

---

## 🇷🇺 Деплой Django на российском сервере

### Шаг 1: Настройка .env файла

```bash
cd /opt/ghostwriter

# Скопируйте пример конфигурации
cp env.production.example .env

# Откройте для редактирования
nano .env
```

**Заполните все переменные:**

```env
# =============================================================================
# DJANGO CORE (ОБЯЗАТЕЛЬНО)
# =============================================================================

# Вставьте сгенерированный Django Secret Key
DJANGO_SECRET_KEY=ваш-сгенерированный-секретный-ключ-50-символов

# Ваши домены (через запятую, БЕЗ пробелов)
# Пока домена нет - используйте IP сервера
# После получения домена - обновите здесь
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your-server-ip

# ОБЯЗАТЕЛЬНО False для production
DEBUG=False

# =============================================================================
# БАЗА ДАННЫХ PostgreSQL (ОБЯЗАТЕЛЬНО)
# =============================================================================

DB_HOST=db
DB_NAME=ghostwriter
DB_USER=ghostwriter
# Сгенерируйте надежный пароль (минимум 32 символа)
DB_PASSWORD=ваш-надежный-пароль-для-базы-данных
DB_PORT=5432

# =============================================================================
# REDIS (ОБЯЗАТЕЛЬНО)
# =============================================================================

REDIS_URL=redis://redis:6379/0

# =============================================================================
# GIGACHAT API (ОБЯЗАТЕЛЬНО)
# =============================================================================

# Вставьте Authorization Key из личного кабинета Sber
GIGACHAT_CREDENTIALS=ваш-authorization-key-из-sber
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# =============================================================================
# FLASK МИКРОСЕРВИС (ОБЯЗАТЕЛЬНО если используете OpenAI)
# =============================================================================

# URL вашего Flask сервера на зарубежном хостинге
# Пока Flask не развернут - оставьте пустым или используйте тестовый URL
FLASK_EXTERNAL_URL=https://flask.yourdomain.com

# Ключ шифрования (ОБЯЗАТЕЛЬНО одинаковый на Django и Flask!)
# Вставьте сгенерированный Fernet Key
GENERATOR_ENCRYPTION_KEY=ваш-fernet-key-для-шифрования

# =============================================================================
# TELEGRAM BOT (ОБЯЗАТЕЛЬНО)
# =============================================================================

# Вставьте токен от @BotFather
TELEGRAM_BOT_TOKEN=ваш-токен-от-botfather

# Username бота (без @)
BOT_USERNAME=ghostcopywriter_bot

# Telegram владельца
OWNER_TELEGRAM=@your_username

# Секрет для webhook (вставьте сгенерированный)
TELEGRAM_WEBHOOK_SECRET=ваш-сгенерированный-webhook-secret

# URL вашего сайта (БЕЗ trailing slash)
# Пока домена нет - используйте IP или временный домен
# После получения домена - обновите здесь
SITE_URL=https://yourdomain.com

# API ключ для связи Django-Bot (опционально, для дополнительной безопасности)
# Если не указан, бот будет работать без API ключа
DJANGO_API_KEY=

# Реквизиты исполнителя (для публичной оферты)
EXECUTOR_FULL_NAME=Ваше ФИО полностью
EXECUTOR_INN=123456789012
EXECUTOR_PHONE=+7 (999) 123-45-67
EXECUTOR_EMAIL=your-email@example.com
EXECUTOR_TELEGRAM=@username
EXECUTOR_CITY=Москва, Россия

# =============================================================================
# ПЛАТЁЖНЫЕ СИСТЕМЫ (ОБЯЗАТЕЛЬНО для приёма платежей)
# =============================================================================

# Вставьте данные из личного кабинета ЮКасса
YOOKASSA_SHOP_ID=ваш-shop-id
YOOKASSA_SECRET_KEY=ваш-secret-key

# =============================================================================
# HTTPS (ОБЯЗАТЕЛЬНО для production)
# =============================================================================

USE_HTTPS=true
```

**Сохраните файл:** `Ctrl+O`, `Enter`, `Ctrl+X`

**Установите правильные права:**
```bash
chmod 600 .env
```

### Шаг 2: Подготовка SSL сертификатов

**Вариант A: Let's Encrypt (рекомендуется)**

```bash
# Установка Certbot
sudo apt install certbot -y

# Остановите Nginx (если запущен)
sudo systemctl stop nginx

# Получение сертификата
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive

# Создайте директорию для сертификатов в проекте
mkdir -p ssl

# Копируем сертификаты
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem

# Установите права
sudo chown $USER:$USER ssl/*.pem
chmod 600 ssl/*.pem
```

**Вариант B: Самоподписанный сертификат (для тестов)**

```bash
mkdir -p ssl

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem \
  -out ssl/cert.pem \
  -subj "/CN=yourdomain.com"
```

### Шаг 3: Обновление конфигурации Nginx

```bash
# Откройте конфигурацию Nginx
nano nginx.prod.conf

# Найдите строку:
# server_name yourdomain.com www.yourdomain.com;

# Замените на ваш домен:
server_name yourdomain.com www.yourdomain.com;
```

### Шаг 4: Создание директории для бэкапов

```bash
mkdir -p backups
```

### Шаг 5: Запуск контейнеров

```bash
# Сборка и запуск всех сервисов
docker-compose -f docker-compose.production.yml up -d --build

# Проверка статуса
docker-compose -f docker-compose.production.yml ps

# Просмотр логов
docker-compose -f docker-compose.production.yml logs -f
```

**Ожидаемый результат:**
```
NAME                      STATUS
ghostwriter-django-prod   Up (healthy)
ghostwriter-bot-prod      Up
ghostwriter-db-prod       Up (healthy)
ghostwriter-redis-prod    Up (healthy)
ghostwriter-nginx-prod    Up (healthy)
```

### Шаг 6: Применение миграций

```bash
# Применение всех миграций (включая новую для защиты от мультиаккаунтов)
docker-compose -f docker-compose.production.yml exec django python manage.py migrate

# Проверка примененных миграций
docker-compose -f docker-compose.production.yml exec django python manage.py showmigrations
```

**Важно:** Убедитесь, что миграция `0017_add_telegram_user_id_to_tokens` применена!

### Шаг 7: Создание суперпользователя (опционально)

```bash
docker-compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

### Шаг 8: Создание токена разработчика (опционально)

```bash
docker-compose -f docker-compose.production.yml exec django python manage.py create_dev_token --name="Admin"
```

Токен будет сохранен в файл `.dev_token`

---

## 🌍 Деплой Flask на зарубежном сервере

### Шаг 1: Подготовка сервера

```bash
# Установка Docker (если еще не установлен)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Шаг 2: Клонирование проекта

```bash
# Создайте директорию
sudo mkdir -p /opt/ghostwriter-flask
cd /opt/ghostwriter-flask

# Клонируйте репозиторий (или только flask_generator папку)
sudo git clone https://github.com/your-repo/ghostwriter.git .
cd flask_generator

# Установите права
sudo chown -R $USER:$USER /opt/ghostwriter-flask
```

### Шаг 3: Настройка .env для Flask

```bash
cd /opt/ghostwriter-flask/flask_generator

# Создайте .env файл
nano .env
```

**Содержимое .env:**

```env
# OpenAI API Key
OPENAI_API_KEY=sk-your-openai-api-key-here

# Ключ шифрования (ОБЯЗАТЕЛЬНО тот же, что на Django сервере!)
GENERATOR_ENCRYPTION_KEY=тот-же-fernet-key-что-на-django

# Модели OpenAI
OPENAI_MODEL=gpt-4o-minio-mini  # Модель для генерации текста и промптов
DALLE_MODEL=dall-e-3      # Модель для генерации изображений

# Flask настройки
FLASK_ENV=production
FLASK_DEBUG=False
```

**ВАЖНО:** `GENERATOR_ENCRYPTION_KEY` должен быть **идентичным** ключу на Django сервере!

### Шаг 4: SSL сертификаты для Flask

```bash
# Установка Certbot
sudo apt install certbot -y

# Получение сертификата
sudo certbot certonly --standalone \
  -d flask.yourdomain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive

# Создайте директорию
mkdir -p ssl

# Копируем сертификаты
sudo cp /etc/letsencrypt/live/flask.yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/flask.yourdomain.com/privkey.pem ssl/key.pem

# Установите права
sudo chown $USER:$USER ssl/*.pem
chmod 600 ssl/*.pem
```

### Шаг 5: Обновление конфигурации Nginx для Flask

```bash
cd /opt/ghostwriter-flask/flask_generator

# Откройте конфигурацию
nano nginx.conf

# Найдите строку:
# server_name flask.yourdomain.com;

# Замените на ваш домен
server_name flask.yourdomain.com;
```

### Шаг 6: Запуск Flask

```bash
cd /opt/ghostwriter-flask

# Запуск через Docker Compose
docker-compose -f docker-compose.flask.yml up -d --build

# Проверка статуса
docker-compose -f docker-compose.flask.yml ps

# Просмотр логов
docker-compose -f docker-compose.flask.yml logs -f
```

### Шаг 7: Проверка работоспособности Flask

```bash
# Проверка health endpoint
curl https://flask.yourdomain.com/health

# Ожидаемый ответ:
# {"status": "ok", "message": "Flask Generator API is running"}
```

---

## 🌐 Настройка домена и SSL

### 1. Настройка DNS записей

**Для основного домена (Django):**

```
A     @              your-server-ip
A     www            your-server-ip
```

**Для Flask поддомена:**

```
A     flask          your-flask-server-ip
```

**Проверка DNS:**
```bash
# Проверка основного домена
dig yourdomain.com
dig www.yourdomain.com

# Проверка Flask поддомена
dig flask.yourdomain.com
```

### 2. Обновление ALLOWED_HOSTS после получения домена

```bash
cd /opt/ghostwriter

# Откройте .env
nano .env

# Обновите ALLOWED_HOSTS
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Обновите SITE_URL
SITE_URL=https://yourdomain.com

# Сохраните и перезапустите контейнеры
docker-compose -f docker-compose.production.yml restart django
```

### 3. Обновление SSL сертификатов

**Если домен изменился:**

```bash
# Остановите Nginx
docker-compose -f docker-compose.production.yml stop nginx

# Получите новый сертификат
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com

# Скопируйте сертификаты
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem

# Установите права
sudo chown $USER:$USER ssl/*.pem

# Запустите Nginx
docker-compose -f docker-compose.production.yml start nginx
```

### 4. Автоматическое обновление SSL (Let's Encrypt)

```bash
# Добавьте в crontab
crontab -e

# Добавьте строку (обновление каждый месяц)
0 0 1 * * certbot renew --quiet && docker-compose -f docker-compose.production.yml restart nginx
```

---

## ⚙️ Настройка переменных окружения

### Полный список переменных для Django сервера

См. раздел [Шаг 1: Настройка .env файла](#шаг-1-настройка-env-файла)

### Где брать ключи

| Переменная | Где получить | Команда генерации |
|------------|--------------|-------------------|
| `DJANGO_SECRET_KEY` | Генерировать | `python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'` |
| `GENERATOR_ENCRYPTION_KEY` | Генерировать | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `TELEGRAM_BOT_TOKEN` | @BotFather | `/newbot` в Telegram |
| `TELEGRAM_WEBHOOK_SECRET` | Генерировать | `openssl rand -hex 32` |
| `GIGACHAT_CREDENTIALS` | developers.sber.ru | Личный кабинет → GigaChat API |
| `OPENAI_API_KEY` | platform.openai.com | API Keys → Create new secret key |
| `YOOKASSA_SHOP_ID` | yookassa.ru | Личный кабинет → Интеграция |
| `YOOKASSA_SECRET_KEY` | yookassa.ru | Личный кабинет → Интеграция |

### Важные замечания

1. **GENERATOR_ENCRYPTION_KEY** должен быть **одинаковым** на Django и Flask серверах
2. **DJANGO_SECRET_KEY** должен быть уникальным и секретным
3. **DB_PASSWORD** должен быть надежным (минимум 32 символа)
4. **ALLOWED_HOSTS** обновляйте после получения домена
5. **SITE_URL** обновляйте после получения домена

---

## 📦 Применение миграций

### Первый деплой

```bash
# Применение всех миграций
docker-compose -f docker-compose.production.yml exec django python manage.py migrate

# Проверка статуса миграций
docker-compose -f docker-compose.production.yml exec django python manage.py showmigrations
```

### После обновления кода

```bash
# Получите последние изменения
cd /opt/ghostwriter
git pull

# Пересоберите контейнеры
docker-compose -f docker-compose.production.yml up -d --build

# Примените новые миграции
docker-compose -f docker-compose.production.yml exec django python manage.py migrate
```

### Важные миграции версии 2.2

- `0016_remove_legacy_token_fields` - удаление старых полей
- `0017_add_telegram_user_id_to_tokens` - добавление защиты от мультиаккаунтов

---

## 💳 Настройка платежных систем

### ЮКасса

1. **Получение ключей:**
   - Зайдите на [https://yookassa.ru/](https://yookassa.ru/)
   - Личный кабинет → Интеграция → Ключи API
   - Скопируйте `Shop ID` и `Secret Key`

2. **Настройка Webhook:**
   - Личный кабинет → Настройки → Webhook
   - URL: `https://yourdomain.com/api/payments/yookassa/webhook/`
   - События: `payment.succeeded`, `payment.canceled`

3. **Добавление в .env:**
   ```env
   YOOKASSA_SHOP_ID=ваш-shop-id
   YOOKASSA_SECRET_KEY=ваш-secret-key
   ```

4. **Перезапуск:**
   ```bash
   docker-compose -f docker-compose.production.yml restart django bot
   ```

### Тестирование платежей

```bash
# Проверка логов платежей
docker-compose -f docker-compose.production.yml logs -f django | grep -i payment

# Проверка webhook
curl -X POST https://yourdomain.com/api/payments/yookassa/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

---

## 📊 Мониторинг и логирование

### Просмотр логов

```bash
# Все логи
docker-compose -f docker-compose.production.yml logs -f

# Логи конкретного сервиса
docker-compose -f docker-compose.production.yml logs -f django
docker-compose -f docker-compose.production.yml logs -f bot
docker-compose -f docker-compose.production.yml logs -f nginx

# Последние 100 строк
docker-compose -f docker-compose.production.yml logs --tail=100 django
```

### Проверка здоровья сервисов

```bash
# Статус всех контейнеров
docker-compose -f docker-compose.production.yml ps

# Детальная информация о здоровье
docker inspect ghostwriter-django-prod | grep -A 20 "Health"

# Проверка доступности
curl -I https://yourdomain.com
curl https://yourdomain.com/health
```

### Мониторинг ресурсов

```bash
# Использование ресурсов
docker stats

# Размер volumes
docker system df -v
```

### Логи Django

```bash
# Вход в контейнер
docker-compose -f docker-compose.production.yml exec django bash

# Просмотр логов Django
tail -f /app/logs/django.log

# Просмотр логов безопасности
tail -f /app/logs/security.log
```

---

## 💾 Резервное копирование

### Автоматический бэкап базы данных

```bash
# Создайте скрипт бэкапа
nano /opt/ghostwriter/backup.sh
```

**Содержимое скрипта:**

```bash
#!/bin/bash

BACKUP_DIR="/opt/ghostwriter/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Создание директории
mkdir -p $BACKUP_DIR

# Бэкап базы данных
docker-compose -f docker-compose.production.yml exec -T db \
  pg_dump -U ghostwriter ghostwriter > $BACKUP_DIR/db_$DATE.sql

# Бэкап медиа файлов
docker cp ghostwriter-django-prod:/app/media $BACKUP_DIR/media_$DATE

# Бэкап .env файла
cp /opt/ghostwriter/.env $BACKUP_DIR/env_$DATE

# Удаление старых бэкапов (старше 30 дней)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

**Сделайте исполняемым:**

```bash
chmod +x /opt/ghostwriter/backup.sh
```

**Добавьте в cron (ежедневно в 2:00):**

```bash
crontab -e

# Добавьте строку:
0 2 * * * /opt/ghostwriter/backup.sh >> /opt/ghostwriter/logs/backup.log 2>&1
```

### Восстановление из бэкапа

```bash
# Восстановление базы данных
docker-compose -f docker-compose.production.yml exec -T db \
  psql -U ghostwriter ghostwriter < backups/db_YYYYMMDD_HHMMSS.sql

# Восстановление медиа
docker cp backups/media_YYYYMMDD ghostwriter-django-prod:/app/media

# Восстановление .env
cp backups/env_YYYYMMDD /opt/ghostwriter/.env
```

---

## 🔧 Troubleshooting

### Проблема: Контейнеры не запускаются

```bash
# Проверьте логи
docker-compose -f docker-compose.production.yml logs django

# Проверьте конфигурацию
docker-compose -f docker-compose.production.yml config

# Проверьте переменные окружения
docker-compose -f docker-compose.production.yml exec django env | grep -E "DB_|DJANGO_|GIGACHAT_"
```

### Проблема: 502 Bad Gateway

```bash
# Проверьте что Django запущен
docker-compose -f docker-compose.production.yml ps django

# Проверьте логи Nginx
docker-compose -f docker-compose.production.yml logs nginx

# Проверьте подключение Django
curl http://localhost:8000/health
```

### Проблема: База данных недоступна

```bash
# Проверьте статус PostgreSQL
docker-compose -f docker-compose.production.yml exec db pg_isready

# Проверьте подключение
docker-compose -f docker-compose.production.yml exec db \
  psql -U ghostwriter -d ghostwriter -c "SELECT 1;"

# Перезапустите БД
docker-compose -f docker-compose.production.yml restart db
```

### Проблема: Telegram Bot не отвечает

```bash
# Проверьте логи бота
docker-compose -f docker-compose.production.yml logs bot

# Проверьте переменные окружения
docker-compose -f docker-compose.production.yml exec bot env | grep TELEGRAM

# Проверьте webhook (если используется)
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

### Проблема: Статика не загружается

```bash
# Пересоберите статику
docker-compose -f docker-compose.production.yml exec django \
  python manage.py collectstatic --noinput

# Проверьте права
docker-compose -f docker-compose.production.yml exec django \
  ls -la /app/staticfiles
```

### Проблема: Ошибки миграций

```bash
# Проверьте статус миграций
docker-compose -f docker-compose.production.yml exec django \
  python manage.py showmigrations

# Откатите последнюю миграцию (если нужно)
docker-compose -f docker-compose.production.yml exec django \
  python manage.py migrate generator 0016

# Примените заново
docker-compose -f docker-compose.production.yml exec django \
  python manage.py migrate
```

---

## ✅ Checklist перед запуском

### Подготовка

- [ ] Docker и Docker Compose установлены
- [ ] Проект склонирован на сервер
- [ ] Все необходимые ключи получены и сохранены

### Настройка .env

- [ ] `DJANGO_SECRET_KEY` сгенерирован и установлен
- [ ] `GENERATOR_ENCRYPTION_KEY` сгенерирован (одинаковый для Django и Flask)
- [ ] `TELEGRAM_BOT_TOKEN` получен от @BotFather
- [ ] `TELEGRAM_WEBHOOK_SECRET` сгенерирован
- [ ] `GIGACHAT_CREDENTIALS` получены
- [ ] `OPENAI_API_KEY` получен (для Flask)
- [ ] `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` получены
- [ ] `DB_PASSWORD` установлен (надежный, 32+ символов)
- [ ] `ALLOWED_HOSTS` настроен
- [ ] `SITE_URL` настроен
- [ ] `DEBUG=False` установлен

### Деплой Django

- [ ] `.env` файл создан и заполнен
- [ ] SSL сертификаты установлены
- [ ] `nginx.prod.conf` обновлен с правильным доменом
- [ ] Контейнеры запущены и работают
- [ ] Миграции применены (включая `0017`)
- [ ] Статика собрана
- [ ] Суперпользователь создан (опционально)

### Деплой Flask

- [ ] `.env` файл создан в `flask_generator/`
- [ ] `GENERATOR_ENCRYPTION_KEY` совпадает с Django
- [ ] `OPENAI_API_KEY` установлен
- [ ] SSL сертификаты установлены
- [ ] Flask запущен и доступен

### Настройка домена

- [ ] DNS записи настроены
- [ ] `ALLOWED_HOSTS` обновлен с доменом
- [ ] `SITE_URL` обновлен с доменом
- [ ] SSL сертификаты обновлены для домена
- [ ] Nginx перезапущен

### Платежи

- [ ] ЮКасса настроена
- [ ] Webhook URL настроен в ЮКасса
- [ ] Тестовый платеж выполнен

### Финальная проверка

- [ ] Сайт доступен по HTTPS
- [ ] Telegram Bot отвечает на `/start`
- [ ] Генерация контента работает
- [ ] Платежи обрабатываются
- [ ] Логи пишутся корректно
- [ ] Бэкапы настроены

---

## 🎯 Быстрые команды

### Управление контейнерами

```bash
# Запуск
docker-compose -f docker-compose.production.yml up -d

# Остановка
docker-compose -f docker-compose.production.yml down

# Перезапуск
docker-compose -f docker-compose.production.yml restart

# Перезапуск конкретного сервиса
docker-compose -f docker-compose.production.yml restart django

# Просмотр логов
docker-compose -f docker-compose.production.yml logs -f

# Статус
docker-compose -f docker-compose.production.yml ps
```

### Django команды

```bash
# Миграции
docker-compose -f docker-compose.production.yml exec django python manage.py migrate

# Создание суперпользователя
docker-compose -f docker-compose.production.yml exec django python manage.py createsuperuser

# Создание токена разработчика
docker-compose -f docker-compose.production.yml exec django python manage.py create_dev_token --name="Admin"

# Очистка токенов
docker-compose -f docker-compose.production.yml exec django python manage.py cleanup_tokens

# Сбор статики
docker-compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput

# Django shell
docker-compose -f docker-compose.production.yml exec django python manage.py shell
```

### Бэкапы

```bash
# Ручной бэкап БД
docker-compose -f docker-compose.production.yml exec -T db \
  pg_dump -U ghostwriter ghostwriter > backups/manual_$(date +%Y%m%d_%H%M%S).sql

# Восстановление БД
docker-compose -f docker-compose.production.yml exec -T db \
  psql -U ghostwriter ghostwriter < backups/db_YYYYMMDD_HHMMSS.sql
```

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose -f docker-compose.production.yml logs -f`
2. Проверьте статус: `docker-compose -f docker-compose.production.yml ps`
3. Проверьте раздел [Troubleshooting](#troubleshooting)
4. Создайте Issue на GitHub

---

**Версия документа:** 2.2  
**Последнее обновление:** 25 января 2026 г.  
**Статус:** Production Ready ✅
