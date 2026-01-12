# 🐳 Docker Deployment Guide

## Обзор

Ghostwriter 3.0 использует **микросервисную Docker архитектуру** со следующими компонентами:

- 🐍 **Django** - основное приложение (генератор, безопасность, токены)
- 🤖 **Bot** - основной Telegram бот (автоматическая выдача токенов)
- 🤖 **Bot Public** - публичный Telegram бот (маркетинг)
- 🐘 **PostgreSQL** - база данных
- 🔴 **Redis** - кеш и rate limiting
- 🌐 **Nginx** - reverse proxy (опционально для production)

---

## 📦 Файловая структура

```
Ghostwriter/
├── Dockerfile                  # Django application
├── Dockerfile.bot              # Основной Telegram бот
├── Dockerfile.bot-public       # Публичный Telegram бот
├── docker-compose.yml          # Основная конфигурация
├── docker-entrypoint.sh        # Entrypoint для Django
├── .dockerignore               # Игнорируемые файлы
└── .env                        # Переменные окружения
```

---

## 🚀 Быстрый старт

### 1. Подготовка

```bash
# Скопируйте пример .env
cp env.example .env

# Отредактируйте .env с вашими настройками
nano .env
```

**Обязательные переменные:**

```bash
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DB_PASSWORD=your-secure-password

# GigaChat
GIGACHAT_CLIENT_ID=your-client-id
GIGACHAT_CLIENT_SECRET=your-client-secret

# Telegram Bots
TELEGRAM_BOT_TOKEN=your-main-bot-token
TELEGRAM_BOT_TOKEN_PUBLIC=your-public-bot-token
OWNER_TELEGRAM=@your_username
SITE_URL=https://yourdomain.com
```

### 2. Запуск всех сервисов

```bash
# Сборка и запуск всех контейнеров
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Проверка статуса
docker-compose ps
```

### 3. Первоначальная настройка

```bash
# Применение миграций (автоматически при старте)
docker-compose exec django python manage.py migrate

# Создание superuser (опционально)
docker-compose exec django python manage.py createsuperuser

# Создание developer токена
docker-compose exec django python manage.py create_dev_token --name="Admin"
```

---

## 🔧 Управление контейнерами

### Запуск отдельных сервисов

```bash
# Только Django + PostgreSQL + Redis
docker-compose up -d django db redis

# Django + основной бот
docker-compose up -d django db redis bot

# Django + публичный бот
docker-compose up -d django db redis bot-public

# Все сервисы без nginx
docker-compose up -d django db redis bot bot-public

# Все сервисы с nginx (production)
docker-compose --profile production up -d
```

### Остановка и удаление

```bash
# Остановка всех сервисов
docker-compose stop

# Остановка конкретного сервиса
docker-compose stop bot

# Удаление контейнеров (данные сохраняются)
docker-compose down

# Удаление контейнеров и volumes (ВНИМАНИЕ: удалит БД!)
docker-compose down -v

# Полная очистка (контейнеры, volumes, images)
docker-compose down -v --rmi all
```

### Перезапуск после изменений

```bash
# Пересборка после изменений в коде
docker-compose up -d --build

# Пересборка конкретного сервиса
docker-compose up -d --build django

# Пересборка без кеша
docker-compose build --no-cache
docker-compose up -d
```

---

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f django
docker-compose logs -f bot
docker-compose logs -f bot-public

# Последние 100 строк
docker-compose logs --tail=100 django

# Логи с временными метками
docker-compose logs -f -t django
```

### Проверка состояния

```bash
# Статус всех сервисов
docker-compose ps

# Использование ресурсов
docker stats

# Здоровье контейнеров
docker-compose ps --format "table {{.Name}}\t{{.Status}}"
```

### Вход в контейнер

```bash
# Django shell
docker-compose exec django python manage.py shell

# Bash в контейнере Django
docker-compose exec django bash

# Bash в контейнере бота
docker-compose exec bot sh

# PostgreSQL CLI
docker-compose exec db psql -U ghostwriter -d ghostwriter

# Redis CLI
docker-compose exec redis redis-cli
```

---

## 🔐 Команды безопасности

```bash
# Проверка безопасности
docker-compose exec django python manage.py security_check

# Детальная проверка
docker-compose exec django python manage.py security_check --detailed

# Разблокировка IP
docker-compose exec django python manage.py unblock --ip 192.168.1.1

# Просмотр логов безопасности
docker-compose exec django tail -f /app/logs/security.log
```

---

## 🗄️ Управление базой данных

### Бэкапы

```bash
# Создание бэкапа
docker-compose exec db pg_dump -U ghostwriter ghostwriter > backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Автоматический бэкап (добавьте в cron)
0 2 * * * cd /path/to/Ghostwriter && docker-compose exec -T db pg_dump -U ghostwriter ghostwriter > backups/backup_$(date +\%Y\%m\%d).sql
```

### Восстановление

```bash
# Восстановление из бэкапа
docker-compose exec -T db psql -U ghostwriter -d ghostwriter < backups/backup_20260112.sql
```

### Миграции

```bash
# Применение миграций
docker-compose exec django python manage.py migrate

# Создание новых миграций
docker-compose exec django python manage.py makemigrations

# Откат миграции
docker-compose exec django python manage.py migrate generator 0010
```

---

## 📈 Production настройка

### 1. Подготовка .env для production

```bash
# Django
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_SECRET_KEY=generate-new-strong-key-here

# Database
DB_PASSWORD=very-secure-password-here

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000

# Redis
REDIS_URL=redis://redis:6379/1

# Site
SITE_URL=https://yourdomain.com
```

### 2. SSL сертификаты

```bash
# Создайте директорию для SSL
mkdir -p ssl

# Используйте Let's Encrypt
docker run -it --rm \
  -v $(pwd)/ssl:/etc/letsencrypt \
  certbot/certbot certonly \
  --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com
```

### 3. Запуск с Nginx

```bash
# Запуск с production профилем
docker-compose --profile production up -d

# Проверка конфигурации nginx
docker-compose exec nginx nginx -t

# Перезагрузка nginx после изменений
docker-compose exec nginx nginx -s reload
```

### 4. Мониторинг production

```bash
# Установите cron для проверки здоровья
*/5 * * * * docker-compose ps | grep -q "Up" || docker-compose up -d

# Мониторинг логов ошибок
docker-compose logs -f django 2>&1 | grep -i error

# Алерты при ошибках (настройте Sentry)
```

---

## 🔄 Обновление версии

### 1. Подготовка

```bash
# Создайте бэкап
docker-compose exec db pg_dump -U ghostwriter ghostwriter > backups/pre_update_$(date +%Y%m%d).sql

# Сохраните текущие переменные
cp .env .env.backup
```

### 2. Обновление

```bash
# Получите новый код
git pull origin main

# Остановите контейнеры
docker-compose down

# Пересоберите с новым кодом
docker-compose build --no-cache

# Запустите с миграциями
docker-compose up -d

# Проверьте логи
docker-compose logs -f django
```

### 3. Откат при проблемах

```bash
# Откатитесь к предыдущей версии
git checkout previous-tag

# Пересоберите
docker-compose build --no-cache

# Восстановите БД если нужно
docker-compose exec -T db psql -U ghostwriter -d ghostwriter < backups/pre_update_20260112.sql
```

---

## 🧹 Очистка

### Очистка неиспользуемых ресурсов

```bash
# Удалить остановленные контейнеры
docker container prune -f

# Удалить неиспользуемые образы
docker image prune -a -f

# Удалить неиспользуемые volumes
docker volume prune -f

# Полная очистка Docker
docker system prune -a --volumes -f
```

### Очистка логов контейнеров

```bash
# Очистить логи конкретного контейнера
truncate -s 0 $(docker inspect --format='{{.LogPath}}' ghostwriter-django)

# Очистить все логи
docker-compose ps -q | xargs -I {} sh -c 'truncate -s 0 $(docker inspect --format="{{.LogPath}}" {})'
```

---

## 🐛 Troubleshooting

### Django не запускается

```bash
# Проверьте логи
docker-compose logs django

# Проверьте подключение к БД
docker-compose exec django python manage.py dbshell

# Проверьте переменные окружения
docker-compose exec django env | grep DJANGO
```

### Боты не отвечают

```bash
# Проверьте что боты запущены
docker-compose ps bot bot-public

# Проверьте логи
docker-compose logs bot
docker-compose logs bot-public

# Проверьте токены
docker-compose exec bot env | grep TELEGRAM
```

### База данных недоступна

```bash
# Проверьте здоровье БД
docker-compose exec db pg_isready -U ghostwriter

# Перезапустите БД
docker-compose restart db

# Проверьте пароль
docker-compose exec db psql -U ghostwriter -d ghostwriter
```

### Redis недоступен

```bash
# Проверьте Redis
docker-compose exec redis redis-cli ping

# Очистите кеш
docker-compose exec redis redis-cli FLUSHALL

# Перезапустите Redis
docker-compose restart redis
```

### Проблемы с правами доступа

```bash
# Исправьте права на директории
sudo chown -R 1000:1000 media logs staticfiles

# В контейнере
docker-compose exec django chown -R django:django /app
```

---

## 📚 Полезные команды

### Информация о контейнерах

```bash
# Детальная информация
docker-compose config

# IP адреса контейнеров
docker network inspect ghostwriter_ghostwriter-network

# Размер контейнеров
docker-compose images

# Использование дискового пространства
docker system df
```

### Работа с volumes

```bash
# Список volumes
docker volume ls

# Информация о volume
docker volume inspect ghostwriter_postgres_data

# Бэкап volume
docker run --rm -v ghostwriter_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

---

## 🎯 Best Practices

1. **Всегда делайте бэкапы** перед обновлением
2. **Используйте .env.example** как шаблон
3. **Не коммитьте .env** в Git
4. **Мониторьте логи** регулярно
5. **Обновляйте образы** регулярно (`docker-compose pull`)
6. **Очищайте неиспользуемые ресурсы** периодически
7. **Используйте health checks** для всех сервисов
8. **Настройте автоматические бэкапы** через cron
9. **Тестируйте обновления** на staging перед production
10. **Документируйте изменения** в конфигурации

---

## 📞 Поддержка

При проблемах:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `docker-compose ps`
3. Проверьте health checks: `docker inspect ghostwriter-django`
4. Читайте документацию: [README.md](README.md), [SECURITY.md](SECURITY.md)
5. Создайте Issue на GitHub

---

**Docker deployment готов! Удачного деплоя! 🚀**
