# 🐳 Ghostwriter AI - Docker Deployment Guide

## 📋 Архитектура

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
                              │ HTTPS API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ЗАРУБЕЖНЫЙ СЕРВЕР                             │
│  ┌─────────┐  ┌─────────┐                                      │
│  │  Nginx  │──│  Flask  │  OpenAI GPT + DALL-E                 │
│  │  :443   │  │  :5000  │                                      │
│  └─────────┘  └─────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Быстрый старт

### 1. Подготовка сервера (Ubuntu 22.04)

```bash
# Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Перелогиньтесь для применения группы docker
exit
```

### 2. Клонирование проекта

```bash
git clone https://github.com/your-repo/ghostwriter.git
cd ghostwriter
```

### 3. Настройка окружения

```bash
# Копируем пример конфигурации
cp env.example .env

# Редактируем конфигурацию
nano .env
```

---

## ⚙️ Настройка .env

### Обязательные переменные для PRODUCTION:

```env
# Django
DJANGO_SECRET_KEY=your-super-secret-key-min-50-chars
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DEBUG=False

# База данных
DB_PASSWORD=super-secure-password-32-chars

# GigaChat (российский AI)
GIGACHAT_CREDENTIALS=your-authorization-key
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# Flask микросервис (зарубежный URL)
FLASK_EXTERNAL_URL=https://flask.yourdomain.com

# Шифрование Django-Flask
GENERATOR_ENCRYPTION_KEY=your-fernet-key

# Telegram Bot
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_SECRET=your-webhook-secret-32-chars
SITE_URL=https://yourdomain.com
```

### Генерация ключей:

```bash
# Django Secret Key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Fernet Key (для шифрования)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Webhook Secret
openssl rand -hex 32
```

---

## 🇷🇺 Деплой на российском сервере

### 1. Настройка SSL сертификатов

```bash
# Создаём директорию для сертификатов
mkdir -p ssl

# Вариант A: Let's Encrypt (рекомендуется)
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Копируем сертификаты
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem

# Вариант B: Самоподписанный (для тестов)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem \
  -subj "/CN=yourdomain.com"
```

### 2. Обновление nginx.prod.conf

```bash
# Замените yourdomain.com на ваш домен
sed -i 's/yourdomain.com/your-actual-domain.com/g' nginx.prod.conf
```

### 3. Создание директории для бэкапов

```bash
mkdir -p backups
```

### 4. Запуск контейнеров

```bash
# Сборка и запуск
docker-compose -f docker-compose.production.yml up -d --build

# Проверка статуса
docker-compose -f docker-compose.production.yml ps

# Просмотр логов
docker-compose -f docker-compose.production.yml logs -f
```

### 5. Создание суперпользователя Django

```bash
docker-compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

### 6. Создание токена разработчика

```bash
docker-compose -f docker-compose.production.yml exec django python manage.py create_dev_token
```

---

## 🌍 Деплой Flask на зарубежном сервере

### 1. Подготовка сервера

```bash
# Клонируем только Flask часть
git clone https://github.com/your-repo/ghostwriter.git
cd ghostwriter
```

### 2. Настройка .env для Flask

```env
OPENAI_API_KEY=sk-your-openai-api-key
GENERATOR_ENCRYPTION_KEY=same-key-as-django-server
OPENAI_MODEL=gpt-4
DALLE_MODEL=dall-e-3
```

### 3. SSL сертификаты

```bash
mkdir -p ssl
# Используйте Let's Encrypt или самоподписанный
```

### 4. Обновление nginx.conf для Flask

```bash
# Отредактируйте flask_generator/nginx.conf
# Замените server_name на ваш домен
```

### 5. Запуск Flask

```bash
docker-compose -f docker-compose.flask.yml up -d --build

# Проверка
docker-compose -f docker-compose.flask.yml ps
docker-compose -f docker-compose.flask.yml logs -f
```

---

## 🔧 Управление контейнерами

### Основные команды

```bash
# Статус
docker-compose -f docker-compose.production.yml ps

# Логи всех сервисов
docker-compose -f docker-compose.production.yml logs -f

# Логи конкретного сервиса
docker-compose -f docker-compose.production.yml logs -f django
docker-compose -f docker-compose.production.yml logs -f bot
docker-compose -f docker-compose.production.yml logs -f nginx

# Перезапуск
docker-compose -f docker-compose.production.yml restart

# Остановка
docker-compose -f docker-compose.production.yml down

# Остановка с удалением volumes (ОСТОРОЖНО!)
docker-compose -f docker-compose.production.yml down -v
```

### Обновление

```bash
# Получить последние изменения
git pull

# Пересобрать и перезапустить
docker-compose -f docker-compose.production.yml up -d --build

# Применить миграции (выполняется автоматически, но можно вручную)
docker-compose -f docker-compose.production.yml exec django python manage.py migrate
```

---

## 💾 Резервное копирование

### База данных PostgreSQL

```bash
# Создание бэкапа
docker-compose -f docker-compose.production.yml exec db \
  pg_dump -U ghostwriter ghostwriter > backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление
docker-compose -f docker-compose.production.yml exec -T db \
  psql -U ghostwriter ghostwriter < backups/backup_YYYYMMDD_HHMMSS.sql
```

### Медиа файлы

```bash
# Бэкап медиа
docker cp ghostwriter-django-prod:/app/media ./backups/media_$(date +%Y%m%d)

# Восстановление
docker cp ./backups/media_YYYYMMDD ghostwriter-django-prod:/app/media
```

### Автоматический бэкап (cron)

```bash
# Добавить в crontab
crontab -e

# Ежедневный бэкап в 3:00
0 3 * * * cd /path/to/ghostwriter && docker-compose -f docker-compose.production.yml exec -T db pg_dump -U ghostwriter ghostwriter > backups/daily_$(date +\%Y\%m\%d).sql
```

---

## 🔍 Мониторинг

### Проверка здоровья сервисов

```bash
# Все сервисы
docker-compose -f docker-compose.production.yml ps

# Детальная информация
docker inspect ghostwriter-django-prod | grep -A 20 "Health"

# Проверка доступности
curl -I https://yourdomain.com
curl https://yourdomain.com/health  # Django
curl https://flask.yourdomain.com/health  # Flask
```

### Просмотр ресурсов

```bash
# Использование ресурсов
docker stats

# Размер volumes
docker system df -v
```

---

## 🔒 Безопасность

### Firewall (UFW)

```bash
# Разрешить только необходимые порты
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### Автообновление SSL (Let's Encrypt)

```bash
# Добавить в crontab
0 0 1 * * certbot renew --quiet && docker-compose -f docker-compose.production.yml restart nginx
```

---

## ❗ Troubleshooting

### Контейнер не запускается

```bash
# Проверить логи
docker-compose -f docker-compose.production.yml logs django

# Проверить конфигурацию
docker-compose -f docker-compose.production.yml config
```

### Ошибка подключения к БД

```bash
# Проверить статус PostgreSQL
docker-compose -f docker-compose.production.yml exec db pg_isready

# Проверить переменные окружения
docker-compose -f docker-compose.production.yml exec django env | grep DB_
```

### 502 Bad Gateway

```bash
# Проверить что Django запущен
docker-compose -f docker-compose.production.yml ps django

# Проверить логи nginx
docker-compose -f docker-compose.production.yml logs nginx
```

### Очистка места

```bash
# Удалить неиспользуемые образы
docker image prune -a

# Удалить все неиспользуемое
docker system prune -a
```

---

## 📊 Полезные команды Django

```bash
# Войти в контейнер Django
docker-compose -f docker-compose.production.yml exec django bash

# Django shell
docker-compose -f docker-compose.production.yml exec django python manage.py shell

# Создать токен
docker-compose -f docker-compose.production.yml exec django python manage.py create_dev_token

# Очистить старые токены
docker-compose -f docker-compose.production.yml exec django python manage.py cleanup_tokens

# Собрать статику
docker-compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput
```

---

## 🎯 Checklist перед деплоем

- [ ] `.env` файл настроен со всеми переменными
- [ ] SSL сертификаты установлены в `ssl/`
- [ ] `nginx.prod.conf` обновлён с правильным доменом
- [ ] Директория `backups/` создана
- [ ] Firewall настроен
- [ ] GigaChat credentials получены
- [ ] Telegram Bot Token получен от @BotFather
- [ ] Flask сервер настроен (если используется OpenAI)
- [ ] DNS записи настроены

---

## 📞 Поддержка

- Telegram бот: [@Ghostcopywriterregistration_bot](https://t.me/Ghostcopywriterregistration_bot)
- Документация: см. `README.md`
