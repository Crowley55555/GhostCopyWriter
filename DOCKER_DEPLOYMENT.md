# 🐳 Ghostwriter - Полное руководство по Docker деплою

Подробная инструкция по развертыванию всех компонентов проекта через Docker.

---

## 📋 Содержание

1. [Архитектура системы](#архитектура-системы)
2. [Предварительные требования](#предварительные-требования)
3. [Подготовка к деплою](#подготовка-к-деплою)
4. [Локальная разработка](#локальная-разработка)
5. [Production деплой - Django + Bot (Российский сервер)](#production-деплой---django--bot-российский-сервер)
6. [Production деплой - Flask (Зарубежный сервер)](#production-деплой---flask-зарубежный-сервер)
7. [Настройка SSL сертификатов](#настройка-ssl-сертификатов)
8. [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
9. [Резервное копирование](#резервное-копирование)
10. [Устранение проблем](#устранение-проблем)

---

## 🏗️ Архитектура системы

Ghostwriter состоит из **трех основных компонентов**:

### 1. Django Application (Российский сервер)
- **Назначение**: Основной веб-интерфейс, система токенов, база данных
- **Порты**: 8000 (внутренний), 80/443 (Nginx)
- **Зависимости**: PostgreSQL, Redis, GigaChat API
- **Контейнеры**: `django`, `db`, `redis`, `nginx`

### 2. Telegram Bot (Российский сервер)
- **Назначение**: Генерация и выдача токенов пользователям
- **API**: Webhook от Telegram, REST API к Django
- **Контейнер**: `bot`

### 3. Flask AI Generator (Зарубежный сервер)
- **Назначение**: Генерация контента через OpenAI API
- **Порты**: 5000 (внутренний), 80/443 (Nginx)
- **Зависимости**: OpenAI API
- **Контейнеры**: `flask-ai`, `nginx-flask`, `redis-flask`

```
┌─────────────────────────────────────────┐
│      РОССИЙСКИЙ СЕРВЕР                  │
│  ┌────────────┐      ┌──────────────┐  │
│  │   Nginx    │◄────►│   Django     │  │
│  │  (80/443)  │      │   (8000)     │  │
│  └────────────┘      └──────┬───────┘  │
│                             │           │
│  ┌────────────┐      ┌──────▼───────┐  │
│  │  Telegram  │◄────►│  PostgreSQL  │  │
│  │    Bot     │      │    Redis     │  │
│  └────────────┘      └──────────────┘  │
└────────────┬────────────────────────────┘
             │ HTTPS (encrypted)
             ▼
┌─────────────────────────────────────────┐
│      ЗАРУБЕЖНЫЙ СЕРВЕР                  │
│  ┌────────────┐      ┌──────────────┐  │
│  │   Nginx    │◄────►│    Flask     │  │
│  │  (80/443)  │      │   AI Gen     │  │
│  └────────────┘      └──────┬───────┘  │
│                             │           │
│                      ┌──────▼───────┐  │
│                      │    Redis     │  │
│                      └──────────────┘  │
└─────────────────────────────────────────┘
```

---

## 📦 Предварительные требования

### Минимальные требования к серверу

#### Российский сервер (Django + Bot)
- **CPU**: 2 ядра
- **RAM**: 2 GB
- **Disk**: 20 GB SSD
- **OS**: Ubuntu 20.04/22.04 LTS или Debian 11/12
- **Сеть**: Статический IP, открытые порты 80, 443

#### Зарубежный сервер (Flask)
- **CPU**: 1 ядро
- **RAM**: 1 GB
- **Disk**: 10 GB SSD
- **OS**: Ubuntu 20.04/22.04 LTS или Debian 11/12
- **Сеть**: Статический IP, открытые порты 80, 443

### Установка Docker

#### На Ubuntu/Debian:

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем зависимости
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Добавляем GPG ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавляем репозиторий Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Проверяем установку
docker --version
docker compose version

# Добавляем текущего пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Включаем автозапуск Docker
sudo systemctl enable docker
sudo systemctl start docker
```

### Получение API ключей

#### 1. GigaChat API (для Django)
```bash
# Перейдите на https://developers.sber.ru/portal/products/gigachat
# Зарегистрируйтесь и создайте приложение
# Получите CLIENT_ID и CLIENT_SECRET
```

#### 2. OpenAI API (для Flask)
```bash
# Перейдите на https://platform.openai.com/api-keys
# Войдите в аккаунт или зарегистрируйтесь
# Создайте новый API ключ
# Сохраните ключ (он показывается только один раз!)
```

#### 3. Telegram Bot Token
```bash
# Откройте Telegram и найдите @BotFather
# Отправьте команду /newbot
# Следуйте инструкциям для создания бота
# Сохраните полученный токен
```

---

## 🔧 Подготовка к деплою

### 1. Клонирование репозитория

```bash
# На каждом сервере
git clone https://github.com/yourusername/ghostwriter.git
cd ghostwriter
```

### 2. Настройка переменных окружения

#### Для Django + Bot (Российский сервер):

```bash
# Копируем шаблон
cp env.example .env

# Редактируем .env
nano .env
```

**Обязательные переменные для production:**

```env
# Django
DJANGO_SECRET_KEY=ваш-супер-секретный-ключ-смените-это
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DEBUG=False

# База данных
DB_PASSWORD=очень-надежный-пароль-базы-данных

# GigaChat API
GIGACHAT_CLIENT_ID=ваш-gigachat-client-id
GIGACHAT_CLIENT_SECRET=ваш-gigachat-client-secret

# Flask микросервис (URL зарубежного сервера)
FLASK_EXTERNAL_URL=https://flask.yourdomain.com

# Telegram Bot
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook/
TELEGRAM_WEBHOOK_SECRET=ваш-секретный-токен-минимум-32-символа
SITE_URL=https://yourdomain.com
DJANGO_API_URL=http://django:8000

# Redis
REDIS_URL=redis://redis:6379/0
```

#### Для Flask (Зарубежный сервер):

```bash
cp env.example .env
nano .env
```

**Обязательные переменные:**

```env
# OpenAI API
OPENAI_API_KEY=sk-ваш-openai-api-ключ

# Шифрование (ДОЛЖНО СОВПАДАТЬ с Django сервером!)
GENERATOR_ENCRYPTION_KEY=тот-же-ключ-что-и-на-django-сервере

# Модели
OPENAI_MODEL=gpt-3.5-turbo
DALLE_MODEL=dall-e-3
```

### 3. Генерация секретных ключей

```bash
# Django Secret Key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Telegram Webhook Secret
openssl rand -hex 32

# Encryption Key (если нужен новый)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 💻 Локальная разработка

Для локального тестирования все сервисы запускаются на одной машине.

### 1. Запуск всех сервисов

```bash
# Убедитесь что .env настроен
cp env.example .env
# Отредактируйте .env для локальной разработки

# Запускаем все контейнеры
docker compose up -d

# Проверяем статус
docker compose ps

# Смотрим логи
docker compose logs -f
```

### 2. Инициализация базы данных

```bash
# Применяем миграции
docker compose exec django python manage.py migrate

# Создаем суперпользователя
docker compose exec django python manage.py createsuperuser

# Создаем developer токен
docker compose exec django python manage.py create_dev_token --name="Your Name"
```

### 3. Проверка работы

```bash
# Django
curl http://localhost:8000/

# Flask
curl http://localhost:5000/

# Nginx
curl http://localhost/
```

### 4. Остановка и очистка

```bash
# Остановить контейнеры
docker compose down

# Остановить и удалить volumes (БД будет очищена!)
docker compose down -v

# Пересобрать контейнеры
docker compose up -d --build
```

---

## 🚀 Production деплой - Django + Bot (Российский сервер)

### Шаг 1: Подготовка сервера

```bash
# Подключаемся к серверу
ssh user@your-server-ip

# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker (см. раздел "Установка Docker")

# Создаем директории для данных
sudo mkdir -p /opt/ghostwriter/{postgres,redis,media,staticfiles,logs,ssl,backups}
sudo chown -R $USER:$USER /opt/ghostwriter
```

### Шаг 2: Клонирование и настройка

```bash
# Клонируем репозиторий
cd /opt
git clone https://github.com/yourusername/ghostwriter.git
cd ghostwriter

# Настраиваем .env
cp env.example .env
nano .env
# Заполните все production переменные!
```

### Шаг 3: Настройка Nginx конфигурации

```bash
# Редактируем nginx.prod.conf
nano nginx.prod.conf

# Замените yourdomain.com на ваш реальный домен
sed -i 's/yourdomain.com/your-actual-domain.com/g' nginx.prod.conf
```

### Шаг 4: Получение SSL сертификатов

#### Вариант А: Let's Encrypt (рекомендуется)

```bash
# Устанавливаем Certbot
sudo apt install -y certbot

# Получаем сертификат (для начала остановите Nginx контейнер)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Копируем сертификаты
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/ghostwriter/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/ghostwriter/ssl/key.pem
sudo chown $USER:$USER /opt/ghostwriter/ssl/*.pem

# Настраиваем автообновление
sudo crontab -e
# Добавьте строку:
# 0 3 * * 0 certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/*.pem /opt/ghostwriter/ssl/ && docker compose -f /opt/ghostwriter/docker-compose.production.yml restart nginx
```

#### Вариант Б: Самоподписанный сертификат (только для тестирования!)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /opt/ghostwriter/ssl/key.pem \
  -out /opt/ghostwriter/ssl/cert.pem \
  -subj "/CN=yourdomain.com"
```

### Шаг 5: Запуск production контейнеров

```bash
# Собираем и запускаем контейнеры
docker compose -f docker-compose.production.yml up -d --build

# Проверяем статус
docker compose -f docker-compose.production.yml ps

# Смотрим логи
docker compose -f docker-compose.production.yml logs -f django
```

### Шаг 6: Инициализация Django

```bash
# Применяем миграции
docker compose -f docker-compose.production.yml exec django python manage.py migrate

# Собираем статику
docker compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput

# Создаем суперпользователя
docker compose -f docker-compose.production.yml exec django python manage.py createsuperuser

# Создаем developer токен
docker compose -f docker-compose.production.yml exec django python manage.py create_dev_token --name="Admin"
```

### Шаг 7: Настройка Telegram Webhook

```bash
# Устанавливаем webhook для бота
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://yourdomain.com/telegram/webhook/",
    "secret_token": "ваш-webhook-secret"
  }'

# Проверяем webhook
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"

# Должны увидеть:
# {
#   "ok": true,
#   "result": {
#     "url": "https://yourdomain.com/telegram/webhook/",
#     "has_custom_certificate": false,
#     "pending_update_count": 0
#   }
# }
```

### Шаг 8: Проверка работы

```bash
# Проверяем Django
curl https://yourdomain.com/

# Проверяем API
curl https://yourdomain.com/api/tokens/create/ \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: ваш-webhook-secret" \
  -d '{"token_type": "DEMO", "chat_id": 123456}'

# Проверяем Admin панель
# Откройте в браузере: https://yourdomain.com/admin/

# Тестируем Telegram бота
# Найдите бота в Telegram и отправьте /start
```

### Шаг 9: Настройка автозапуска

```bash
# Создаем systemd service
sudo nano /etc/systemd/system/ghostwriter.service
```

Содержимое файла:

```ini
[Unit]
Description=Ghostwriter Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ghostwriter
ExecStart=/usr/bin/docker compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# Включаем и запускаем service
sudo systemctl enable ghostwriter.service
sudo systemctl start ghostwriter.service

# Проверяем статус
sudo systemctl status ghostwriter.service
```

---

## 🌐 Production деплой - Flask (Зарубежный сервер)

Flask микросервис размещается на зарубежном сервере для доступа к OpenAI API.

### Шаг 1: Подготовка сервера

```bash
# Подключаемся к зарубежному серверу
ssh user@flask-server-ip

# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Docker (см. раздел "Установка Docker")

# Создаем директории
sudo mkdir -p /opt/flask-ai/{logs,ssl,redis}
sudo chown -R $USER:$USER /opt/flask-ai
```

### Шаг 2: Клонирование и настройка

```bash
# Клонируем репозиторий
cd /opt
git clone https://github.com/yourusername/ghostwriter.git
cd ghostwriter

# Настраиваем .env для Flask
cp env.example .env
nano .env
```

**Минимальные переменные для Flask:**

```env
OPENAI_API_KEY=sk-ваш-openai-api-ключ
GENERATOR_ENCRYPTION_KEY=тот-же-ключ-что-на-django-сервере
OPENAI_MODEL=gpt-3.5-turbo
DALLE_MODEL=dall-e-3
REQUEST_TIMEOUT=300
MAX_REQUESTS=1000
```

### Шаг 3: SSL сертификаты для Flask

```bash
# Получаем сертификат для поддомена
sudo certbot certonly --standalone -d flask.yourdomain.com

# Копируем сертификаты
sudo cp /etc/letsencrypt/live/flask.yourdomain.com/fullchain.pem /opt/flask-ai/ssl/cert.pem
sudo cp /etc/letsencrypt/live/flask.yourdomain.com/privkey.pem /opt/flask-ai/ssl/key.pem
sudo chown $USER:$USER /opt/flask-ai/ssl/*.pem
```

### Шаг 4: Обновление Nginx конфигурации Flask

```bash
cd /opt/ghostwriter
nano flask_generator/nginx.conf

# Замените yourdomain.com на flask.yourdomain.com
```

### Шаг 5: Запуск Flask контейнеров

```bash
# Запускаем Flask микросервис
docker compose -f docker-compose.flask.yml up -d --build

# Проверяем статус
docker compose -f docker-compose.flask.yml ps

# Смотрим логи
docker compose -f docker-compose.flask.yml logs -f flask-ai
```

### Шаг 6: Проверка работы

```bash
# Локальная проверка
curl http://localhost:5000/

# Проверка через Nginx
curl https://flask.yourdomain.com/

# Тест генерации (с Django сервера)
# Должно работать автоматически через FLASK_EXTERNAL_URL
```

### Шаг 7: Настройка автозапуска Flask

```bash
sudo nano /etc/systemd/system/ghostwriter-flask.service
```

```ini
[Unit]
Description=Ghostwriter Flask AI Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ghostwriter
ExecStart=/usr/bin/docker compose -f docker-compose.flask.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.flask.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ghostwriter-flask.service
sudo systemctl start ghostwriter-flask.service
```

---

## 🔐 Настройка SSL сертификатов

### Автоматическое обновление Let's Encrypt

#### На Django сервере:

```bash
# Создаем скрипт обновления
sudo nano /opt/ghostwriter/renew-ssl.sh
```

```bash
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/ghostwriter/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/ghostwriter/ssl/key.pem
docker compose -f /opt/ghostwriter/docker-compose.production.yml restart nginx
echo "SSL certificates renewed: $(date)" >> /opt/ghostwriter/logs/ssl-renewal.log
```

```bash
sudo chmod +x /opt/ghostwriter/renew-ssl.sh

# Добавляем в crontab
sudo crontab -e
# Добавьте:
0 3 * * 0 /opt/ghostwriter/renew-ssl.sh
```

#### На Flask сервере:

```bash
sudo nano /opt/flask-ai/renew-ssl.sh
```

```bash
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/flask.yourdomain.com/fullchain.pem /opt/flask-ai/ssl/cert.pem
cp /etc/letsencrypt/live/flask.yourdomain.com/privkey.pem /opt/flask-ai/ssl/key.pem
docker compose -f /opt/ghostwriter/docker-compose.flask.yml restart nginx-flask
echo "Flask SSL certificates renewed: $(date)" >> /opt/flask-ai/logs/ssl-renewal.log
```

```bash
sudo chmod +x /opt/flask-ai/renew-ssl.sh
sudo crontab -e
# Добавьте:
0 3 * * 0 /opt/flask-ai/renew-ssl.sh
```

---

## 📊 Мониторинг и обслуживание

### Проверка статуса контейнеров

```bash
# Django сервер
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f --tail=100

# Flask сервер
docker compose -f docker-compose.flask.yml ps
docker compose -f docker-compose.flask.yml logs -f --tail=100
```

### Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Место на диске
df -h
du -sh /opt/ghostwriter/*
```

### Логи

```bash
# Django логи
tail -f /opt/ghostwriter/logs/django.log

# Nginx логи
tail -f /opt/ghostwriter/logs/nginx/access.log
tail -f /opt/ghostwriter/logs/nginx/error.log

# Flask логи
tail -f /opt/flask-ai/logs/flask.log

# Bot логи
docker compose -f docker-compose.production.yml logs -f bot
```

### Обновление проекта

```bash
# Django сервер
cd /opt/ghostwriter
git pull origin main
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml exec django python manage.py migrate
docker compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml restart

# Flask сервер
cd /opt/ghostwriter
git pull origin main
docker compose -f docker-compose.flask.yml up -d --build
docker compose -f docker-compose.flask.yml restart
```

### Очистка токенов

```bash
# Ручная очистка (APScheduler делает автоматически)
docker compose -f docker-compose.production.yml exec django python manage.py cleanup_tokens

# Dry-run (показать что будет удалено)
docker compose -f docker-compose.production.yml exec django python manage.py cleanup_tokens --dry-run

# Удалить старые деактивированные токены
docker compose -f docker-compose.production.yml exec django python manage.py cleanup_tokens --delete --days=90
```

---

## 💾 Резервное копирование

### Автоматический бэкап PostgreSQL

```bash
# Создаем скрипт бэкапа
sudo nano /opt/ghostwriter/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/ghostwriter/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="ghostwriter_backup_$TIMESTAMP.sql.gz"

# Создаем бэкап
docker compose -f /opt/ghostwriter/docker-compose.production.yml exec -T db \
  pg_dump -U ghostwriter ghostwriter | gzip > "$BACKUP_DIR/$BACKUP_FILE"

# Удаляем старые бэкапы (старше 30 дней)
find "$BACKUP_DIR" -name "ghostwriter_backup_*.sql.gz" -mtime +30 -delete

echo "Backup created: $BACKUP_FILE" >> /opt/ghostwriter/logs/backup.log

# Опционально: загрузка на удаленный сервер
# scp "$BACKUP_DIR/$BACKUP_FILE" user@backup-server:/backups/
```

```bash
sudo chmod +x /opt/ghostwriter/backup.sh

# Добавляем в crontab (ежедневно в 2:00 AM)
sudo crontab -e
# Добавьте:
0 2 * * * /opt/ghostwriter/backup.sh
```

### Восстановление из бэкапа

```bash
# Список бэкапов
ls -lh /opt/ghostwriter/backups/

# Восстановление
gunzip < /opt/ghostwriter/backups/ghostwriter_backup_TIMESTAMP.sql.gz | \
  docker compose -f docker-compose.production.yml exec -T db \
  psql -U ghostwriter ghostwriter
```

### Бэкап медиафайлов

```bash
# Создаем архив медиафайлов
tar -czf /opt/ghostwriter/backups/media_$(date +%Y%m%d).tar.gz \
  -C /opt/ghostwriter media/

# Автоматизация (добавьте в backup.sh)
```

---

## 🔧 Устранение проблем

### Проблема: Контейнер не запускается

```bash
# Проверяем логи
docker compose -f docker-compose.production.yml logs <service-name>

# Проверяем конфигурацию
docker compose -f docker-compose.production.yml config

# Пересобираем без кеша
docker compose -f docker-compose.production.yml build --no-cache <service-name>
docker compose -f docker-compose.production.yml up -d <service-name>
```

### Проблема: База данных не подключается

```bash
# Проверяем что БД запущена
docker compose -f docker-compose.production.yml ps db

# Проверяем логи БД
docker compose -f docker-compose.production.yml logs db

# Подключаемся к БД вручную
docker compose -f docker-compose.production.yml exec db psql -U ghostwriter

# Проверяем переменные окружения
docker compose -f docker-compose.production.yml exec django env | grep DB_
```

### Проблема: Telegram webhook не работает

```bash
# Проверяем webhook info
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"

# Удаляем и устанавливаем заново
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourdomain.com/telegram/webhook/", "secret_token": "your-secret"}'

# Проверяем логи бота
docker compose -f docker-compose.production.yml logs -f bot

# Тестовый запрос
curl -X POST https://yourdomain.com/telegram/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: your-secret" \
  -d '{"update_id": 1}'
```

### Проблема: Flask недоступен с Django сервера

```bash
# С Django сервера проверяем доступность Flask
curl https://flask.yourdomain.com/

# Проверяем FLASK_EXTERNAL_URL в .env
cat .env | grep FLASK_EXTERNAL_URL

# Проверяем encryption key (должен совпадать!)
# На Django сервере:
cat .env | grep GENERATOR_ENCRYPTION_KEY
# На Flask сервере:
cat .env | grep GENERATOR_ENCRYPTION_KEY

# Проверяем логи Flask
docker compose -f docker-compose.flask.yml logs -f flask-ai
```

### Проблема: 502 Bad Gateway от Nginx

```bash
# Проверяем что Django запущен
docker compose -f docker-compose.production.yml ps django

# Проверяем логи Nginx
docker compose -f docker-compose.production.yml logs nginx

# Проверяем конфигурацию Nginx
docker compose -f docker-compose.production.yml exec nginx nginx -t

# Перезапускаем Nginx
docker compose -f docker-compose.production.yml restart nginx
```

### Проблема: Недостаточно памяти

```bash
# Проверяем использование памяти
free -h
docker stats

# Настраиваем swap (если нет)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Уменьшаем workers в gunicorn (docker-compose.production.yml)
# --workers 3 -> --workers 2
```

### Проблема: Медленная работа

```bash
# Проверяем использование ресурсов
docker stats

# Проверяем логи на ошибки
docker compose -f docker-compose.production.yml logs --tail=100

# Проверяем Redis
docker compose -f docker-compose.production.yml exec redis redis-cli ping
docker compose -f docker-compose.production.yml exec redis redis-cli info stats

# Очищаем старые данные
docker system prune -a --volumes
```

---

## 📞 Дополнительная помощь

### Полезные команды

```bash
# Показать все запущенные контейнеры
docker ps

# Показать использование диска Docker
docker system df

# Очистка неиспользуемых ресурсов
docker system prune -a

# Перезапуск всех контейнеров
docker compose -f docker-compose.production.yml restart

# Остановка всех контейнеров
docker compose -f docker-compose.production.yml stop

# Полное удаление (включая volumes)
docker compose -f docker-compose.production.yml down -v
```

### Проверка безопасности

```bash
# Обновление всех пакетов
sudo apt update && sudo apt upgrade -y

# Проверка открытых портов
sudo netstat -tulpn | grep LISTEN

# Настройка firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Fail2ban для защиты от брутфорса
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

---

## ✅ Checklist перед запуском в production

### Django сервер:
- [ ] Установлен Docker и Docker Compose
- [ ] Создан и настроен `.env` файл
- [ ] `DEBUG=False` в `.env`
- [ ] Установлены SSL сертификаты
- [ ] Настроен `nginx.prod.conf` с правильным доменом
- [ ] Настроен firewall (порты 80, 443)
- [ ] Созданы директории `/opt/ghostwriter/*`
- [ ] Получены API ключи (GigaChat, Telegram Bot)
- [ ] Установлен webhook для Telegram бота
- [ ] Создан superuser для Django admin
- [ ] Настроен автоматический бэкап
- [ ] Настроено автообновление SSL
- [ ] Добавлен systemd service для автозапуска

### Flask сервер:
- [ ] Установлен Docker и Docker Compose
- [ ] Создан и настроен `.env` файл
- [ ] Получен OpenAI API ключ
- [ ] `GENERATOR_ENCRYPTION_KEY` совпадает с Django
- [ ] Установлены SSL сертификаты
- [ ] Настроен `flask_generator/nginx.conf`
- [ ] Настроен firewall (порты 80, 443)
- [ ] Созданы директории `/opt/flask-ai/*`
- [ ] Flask доступен с Django сервера
- [ ] Добавлен systemd service для автозапуска

---

## 🎉 Готово!

После выполнения всех шагов ваш Ghostwriter должен быть полностью развернут и работать в production!

**Тестирование:**
1. Откройте `https://yourdomain.com/`
2. Найдите вашего бота в Telegram
3. Отправьте `/start` боту
4. Получите DEMO токен
5. Пройдите по ссылке и проверьте генерацию контента

**Поддержка:**
- GitHub Issues: https://github.com/yourusername/ghostwriter/issues
- Email: support@yourdomain.com

---

*Последнее обновление: 2026-01-11*
