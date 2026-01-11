# 🚀 Deployment Guide - Ghostwriter

Руководство по развертыванию Ghostwriter в production окружении.

---

## 📚 Документация по деплою

### Основные руководства:

1. **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** - **РЕКОМЕНДУЕТСЯ!**
   - Полное пошаговое руководство по Docker деплою
   - Для Django + Bot (российский сервер)
   - Для Flask AI Generator (зарубежный сервер)
   - Настройка SSL, Nginx, мониторинг, бэкапы
   - **Используйте это руководство для production!**

2. **Текущий файл (DEPLOYMENT.md)** - Общая информация
   - Обзор вариантов деплоя
   - Ручная установка без Docker
   - Дополнительные настройки

---

## 🎯 Выбор варианта деплоя

### ✅ Docker Deployment (Рекомендуется)

**Преимущества:**
- Простое развертывание в 1 команду
- Изоляция компонентов
- Легкое масштабирование
- Простое обновление
- Одинаковая работа в dev и production

**Подходит для:**
- Production окружения
- VPS/Dedicated серверы
- Облачные платформы (AWS, DigitalOcean, etc.)

👉 **[Перейти к Docker Deployment Guide](DOCKER_DEPLOYMENT.md)**

---

### ⚙️ Ручной Deployment

**Преимущества:**
- Больше контроля
- Меньше overhead
- Подходит для shared hosting

**Недостатки:**
- Сложнее настройка
- Труднее обновления
- Больше ручной работы

**Подходит для:**
- Специфичные требования
- Legacy серверы
- Образовательные цели

---

## 📋 Содержание (Ручной деплой)

- [Требования](#-требования)
- [Ручной Deployment](#-ручной-deployment)
- [Nginx Configuration](#-nginx-configuration)
- [Telegram Bot Production](#-telegram-bot-production)
- [Environment Variables](#-environment-variables)
- [SSL/HTTPS Setup](#-sslhttps-setup)
- [Мониторинг и логи](#-мониторинг-и-логи)
- [Backup и восстановление](#-backup-и-восстановление)
- [Troubleshooting](#-troubleshooting)

---

## 🔧 Требования

### Минимальные требования сервера

- **OS**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **Python**: 3.9+
- **RAM**: 2GB минимум, 4GB рекомендуется
- **CPU**: 2 cores минимум
- **Disk**: 10GB свободного места
- **Network**: Публичный IP адрес

### Рекомендуемые

- **RAM**: 8GB
- **CPU**: 4 cores
- **Disk**: 50GB SSD
- **Swap**: 2GB

### Необходимый софт

- PostgreSQL 13+
- Nginx (reverse proxy)
- Git
- Python 3.9+
- Supervisor или systemd (для автозапуска)

---

## 🔨 Ручной Deployment

### Шаг 1: Установка зависимостей системы

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.9 python3.9-venv python3-pip \
    postgresql postgresql-contrib nginx supervisor git

# CentOS/RHEL
sudo yum install -y python39 python39-pip postgresql-server \
    postgresql-contrib nginx supervisor git
```

### Шаг 2: Настройка PostgreSQL

```bash
# Инициализация (только CentOS/RHEL)
sudo postgresql-setup --initdb

# Запуск PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание базы данных и пользователя
sudo -u postgres psql << EOF
CREATE DATABASE ghostwriter;
CREATE USER ghostwriter WITH PASSWORD 'your-strong-password';
ALTER ROLE ghostwriter SET client_encoding TO 'utf8';
ALTER ROLE ghostwriter SET default_transaction_isolation TO 'read committed';
ALTER ROLE ghostwriter SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE ghostwriter TO ghostwriter;
\q
EOF
```

### Шаг 3: Клонирование и настройка проекта

```bash
# Создание директории
sudo mkdir -p /opt/ghostwriter
cd /opt/ghostwriter

# Клонирование
sudo git clone https://github.com/yourusername/Ghostwriter.git .

# Права доступа
sudo chown -R www-data:www-data /opt/ghostwriter

# Создание виртуального окружения
sudo -u www-data python3.9 -m venv venv

# Активация и установка зависимостей
sudo -u www-data bash << EOF
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
EOF
```

### Шаг 4: Настройка .env

```bash
sudo -u www-data nano /opt/ghostwriter/.env
```

Используйте те же переменные что и в Docker deployment.

### Шаг 5: Инициализация Django

```bash
cd /opt/ghostwriter
sudo -u www-data bash << EOF
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
EOF
```

### Шаг 6: Настройка Gunicorn

Создайте файл `/etc/systemd/system/ghostwriter.service`:

```ini
[Unit]
Description=Ghostwriter Django Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/ghostwriter
Environment="PATH=/opt/ghostwriter/venv/bin"

ExecStart=/opt/ghostwriter/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    --timeout 300 \
    --access-logfile /var/log/ghostwriter/access.log \
    --error-logfile /var/log/ghostwriter/error.log \
    --log-level info \
    ghostwriter.wsgi:application

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Создайте директорию для логов:

```bash
sudo mkdir -p /var/log/ghostwriter
sudo chown www-data:www-data /var/log/ghostwriter
```

Запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl start ghostwriter
sudo systemctl enable ghostwriter

# Проверка статуса
sudo systemctl status ghostwriter
```

---

## 🌐 Nginx Configuration

### Базовая конфигурация

Создайте файл `/etc/nginx/sites-available/ghostwriter`:

```nginx
# Upstream для Django
upstream django {
    server 127.0.0.1:8000 fail_timeout=0;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (будут созданы через Certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Client settings
    client_max_body_size 20M;
    client_body_timeout 60s;

    # Logging
    access_log /var/log/nginx/ghostwriter_access.log;
    error_log /var/log/nginx/ghostwriter_error.log;

    # Static files
    location /static/ {
        alias /opt/ghostwriter/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /opt/ghostwriter/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Django application
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Telegram webhook (если используется)
    location /telegram-webhook/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Активируйте конфигурацию:

```bash
# Создайте симлинк
sudo ln -s /etc/nginx/sites-available/ghostwriter /etc/nginx/sites-enabled/

# Удалите дефолтную конфигурацию
sudo rm /etc/nginx/sites-enabled/default

# Проверьте конфигурацию
sudo nginx -t

# Перезапустите nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 📱 Telegram Bot Production

### Вариант 1: Polling режим (простой)

Создайте systemd service `/etc/systemd/system/ghostwriter-bot.service`:

```ini
[Unit]
Description=Ghostwriter Telegram Bot
After=network.target ghostwriter.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/ghostwriter
Environment="PATH=/opt/ghostwriter/venv/bin"

ExecStart=/opt/ghostwriter/venv/bin/python bot.py

Restart=always
RestartSec=5

StandardOutput=append:/var/log/ghostwriter/bot.log
StandardError=append:/var/log/ghostwriter/bot.log

[Install]
WantedBy=multi-user.target
```

Запустите:

```bash
sudo systemctl daemon-reload
sudo systemctl start ghostwriter-bot
sudo systemctl enable ghostwriter-bot

# Проверка
sudo systemctl status ghostwriter-bot
```

### Вариант 2: Webhook режим (рекомендуется для production)

Установите webhook через бота:

```bash
cd /opt/ghostwriter
source venv/bin/activate
python bot.py --set-webhook
```

Или через API:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://yourdomain.com/telegram-webhook/",
    "secret_token": "your-webhook-secret"
  }'
```

Django будет обрабатывать webhook через `generator/views.py:telegram_webhook()`.

**Преимущества webhook:**
- Мгновенная доставка сообщений
- Меньше нагрузки на сервер
- Не требует отдельного процесса бота

---

## 🔐 Environment Variables

### Production .env файл

```bash
# =============================================================================
# DJANGO SETTINGS
# =============================================================================
DJANGO_SECRET_KEY=your-very-long-random-secret-key-minimum-50-characters
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your-server-ip

# =============================================================================
# DATABASE
# =============================================================================
DB_HOST=db                           # 'localhost' для ручного deployment
DB_PORT=5432
DB_NAME=ghostwriter
DB_USER=ghostwriter
DB_PASSWORD=your-very-strong-database-password-here

# =============================================================================
# AI API KEYS
# =============================================================================
# GigaChat (Сбер)
GIGACHAT_CLIENT_ID=your_gigachat_client_id
GIGACHAT_CLIENT_SECRET=your_gigachat_client_secret
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# OpenAI (для Flask микросервиса)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-3.5-turbo
DALLE_MODEL=dall-e-3

# =============================================================================
# TELEGRAM BOT
# =============================================================================
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram-webhook/
TELEGRAM_WEBHOOK_SECRET=your-random-webhook-secret-token
SITE_URL=https://yourdomain.com

# =============================================================================
# API INTEGRATION
# =============================================================================
DJANGO_API_URL=http://localhost:8000
DJANGO_API_KEY=your-api-key-for-bot-authentication

# =============================================================================
# FLASK GENERATOR (опционально)
# =============================================================================
FLASK_GEN_URL=https://your-flask-server.com
GENERATOR_ENCRYPTION_KEY=your-fernet-encryption-key-base64

# =============================================================================
# REDIS
# =============================================================================
REDIS_URL=redis://redis:6379/0      # 'redis://localhost:6379/0' для ручного

# =============================================================================
# EMAIL (опционально)
# =============================================================================
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password

# =============================================================================
# SECURITY
# =============================================================================
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS=DENY
```

### Безопасное хранение

```bash
# Установите правильные права доступа
sudo chmod 600 /opt/ghostwriter/.env
sudo chown www-data:www-data /opt/ghostwriter/.env

# Не коммитьте .env в git
echo ".env" >> .gitignore
```

---

## 🔒 SSL/HTTPS Setup

### Установка Certbot

```bash
# Ubuntu/Debian
sudo apt install certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install certbot python3-certbot-nginx
```

### Получение SSL сертификата

```bash
# Остановите nginx временно
sudo systemctl stop nginx

# Получите сертификат
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Запустите nginx
sudo systemctl start nginx
```

### Автоматическое обновление

```bash
# Тест обновления
sudo certbot renew --dry-run

# Добавьте в cron для автоматического обновления
sudo crontab -e

# Добавьте строку:
0 3 * * * certbot renew --quiet && systemctl reload nginx
```

---

## 📊 Мониторинг и логи

### Логи Django/Gunicorn

```bash
# Access logs
sudo tail -f /var/log/ghostwriter/access.log

# Error logs
sudo tail -f /var/log/ghostwriter/error.log

# Telegram Bot logs
sudo tail -f /var/log/ghostwriter/bot.log

# Все логи разом
sudo tail -f /var/log/ghostwriter/*.log
```

### Логи Nginx

```bash
# Access logs
sudo tail -f /var/log/nginx/ghostwriter_access.log

# Error logs
sudo tail -f /var/log/nginx/ghostwriter_error.log
```

### Системные логи

```bash
# Gunicorn service
sudo journalctl -u ghostwriter -f

# Bot service
sudo journalctl -u ghostwriter-bot -f

# Nginx service
sudo journalctl -u nginx -f
```

### Ротация логов

Создайте `/etc/logrotate.d/ghostwriter`:

```
/var/log/ghostwriter/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload ghostwriter > /dev/null 2>&1 || true
    endscript
}
```

### Мониторинг через Supervisor Dashboard (опционально)

```bash
sudo apt install supervisor

# Конфигурация в /etc/supervisor/conf.d/ghostwriter.conf
[program:ghostwriter]
command=/opt/ghostwriter/venv/bin/gunicorn ghostwriter.wsgi:application --bind 127.0.0.1:8000
directory=/opt/ghostwriter
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/ghostwriter/access.log

# Запуск
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start ghostwriter
```

---

## 💾 Backup и восстановление

### Автоматический backup скрипт

Создайте `/opt/ghostwriter/backup.sh`:

```bash
#!/bin/bash

# Настройки
BACKUP_DIR="/backups/ghostwriter"
PROJECT_DIR="/opt/ghostwriter"
DB_NAME="ghostwriter"
DB_USER="ghostwriter"
DATE=$(date +%Y%m%d_%H%M%S)

# Создание директории
mkdir -p $BACKUP_DIR

# Backup базы данных
echo "Backing up database..."
sudo -u postgres pg_dump $DB_NAME > $BACKUP_DIR/db_$DATE.sql

# Backup media файлов
echo "Backing up media files..."
tar -czf $BACKUP_DIR/media_$DATE.tar.gz -C $PROJECT_DIR media/

# Backup .env файла
echo "Backing up configuration..."
cp $PROJECT_DIR/.env $BACKUP_DIR/env_$DATE

# Удаление старых backup'ов (старше 30 дней)
echo "Cleaning old backups..."
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

Сделайте исполняемым:

```bash
sudo chmod +x /opt/ghostwriter/backup.sh
```

Добавьте в cron (ежедневно в 2:00):

```bash
sudo crontab -e
0 2 * * * /opt/ghostwriter/backup.sh >> /var/log/ghostwriter/backup.log 2>&1
```

### Восстановление из backup

```bash
# Восстановление базы данных
sudo -u postgres psql $DB_NAME < /backups/ghostwriter/db_20260111_020000.sql

# Восстановление media
cd /opt/ghostwriter
tar -xzf /backups/ghostwriter/media_20260111_020000.tar.gz

# Восстановление .env
cp /backups/ghostwriter/env_20260111_020000 .env

# Перезапуск сервисов
sudo systemctl restart ghostwriter
```

---

## 🔧 Troubleshooting

### Проблема: Django не запускается

**Проверка:**
```bash
# Смотрите логи
sudo journalctl -u ghostwriter -n 50

# Проверьте конфигурацию
cd /opt/ghostwriter
source venv/bin/activate
python manage.py check --deploy
```

**Решения:**
- Проверьте .env файл
- Убедитесь что база данных доступна
- Проверьте права доступа на файлы

### Проблема: 502 Bad Gateway

**Причины:**
- Gunicorn не запущен
- Неправильный upstream в nginx

**Решение:**
```bash
# Проверьте Gunicorn
sudo systemctl status ghostwriter

# Проверьте что порт 8000 слушается
sudo netstat -tlnp | grep 8000

# Перезапустите сервисы
sudo systemctl restart ghostwriter nginx
```

### Проблема: Static файлы не работают

**Решение:**
```bash
# Соберите статику заново
cd /opt/ghostwriter
source venv/bin/activate
python manage.py collectstatic --noinput

# Проверьте права
sudo chown -R www-data:www-data staticfiles/

# Проверьте nginx конфигурацию
sudo nginx -t
```

### Проблема: Telegram Bot не отвечает

**Polling режим:**
```bash
# Проверьте статус
sudo systemctl status ghostwriter-bot

# Смотрите логи
sudo tail -f /var/log/ghostwriter/bot.log
```

**Webhook режим:**
```bash
# Проверьте webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Проверьте Django логи
sudo tail -f /var/log/ghostwriter/error.log | grep telegram
```

### Проблема: База данных недоступна

**Решение:**
```bash
# Проверьте PostgreSQL
sudo systemctl status postgresql

# Проверьте подключение
sudo -u postgres psql -c "\l"

# Проверьте пользователя
sudo -u postgres psql -c "\du"

# Тест подключения
psql -h localhost -U ghostwriter -d ghostwriter
```

### Проблема: Высокая нагрузка

**Оптимизация:**

1. Увеличьте количество gunicorn workers:
```ini
# /etc/systemd/system/ghostwriter.service
ExecStart=... --workers 8 ...  # 2-4 x CPU cores
```

2. Настройте кеширование в Redis:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

3. Оптимизируйте PostgreSQL:
```bash
# /etc/postgresql/13/main/postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
max_connections = 100
```

---

## 📝 Checklist для Production

### Перед запуском

- [ ] Установлены все системные зависимости
- [ ] Настроен .env файл с production значениями
- [ ] DEBUG=False в настройках
- [ ] ALLOWED_HOSTS настроен правильно
- [ ] Секретные ключи сгенерированы и установлены
- [ ] База данных создана и мигрирована
- [ ] Статика собрана (collectstatic)
- [ ] Nginx настроен и запущен
- [ ] SSL сертификат установлен
- [ ] Gunicorn/Django запущен
- [ ] Telegram Bot настроен
- [ ] Backup скрипт настроен

### После запуска

- [ ] Сайт доступен по HTTPS
- [ ] Telegram Bot отвечает
- [ ] API endpoints работают
- [ ] Статика загружается
- [ ] Media файлы доступны
- [ ] Логи пишутся корректно
- [ ] Backup выполняется автоматически
- [ ] Мониторинг настроен

---

## 🆘 Поддержка

Если возникли проблемы при deployment:

1. Проверьте логи (см. раздел "Мониторинг и логи")
2. Посмотрите раздел "Troubleshooting"
3. Проверьте checklist
4. Создайте issue на GitHub

---

**Обновлено:** 11.01.2026  
**Версия:** 2.0 (Production Ready)
