# 🚀 Инструкция по обновлению проекта после git pull

## Быстрое обновление (рекомендуется)

### Через SSH:

```bash
# 1. Подключитесь к серверу по SSH
ssh user@your-server.com

# 2. Перейдите в директорию проекта
cd /path/to/Ghostwriter

# 3. Запустите скрипт обновления
bash deploy/update.sh
```

Скрипт автоматически выполнит:
- ✅ `git pull` - получение изменений
- ✅ Остановку контейнеров Django и Bot
- ✅ Пересборку Docker образов
- ✅ Применение миграций Django
- ✅ Сбор статических файлов
- ✅ Перезапуск всех сервисов
- ✅ Проверку статуса

---

## Ручное обновление (пошагово)

Если нужно выполнить обновление вручную:

```bash
# 1. Подключитесь к серверу
ssh user@your-server.com

# 2. Перейдите в директорию проекта
cd /path/to/Ghostwriter

# 3. Получите изменения из Git
git pull origin main
# или
git pull origin dev

# 4. Остановите контейнеры (опционально, для zero-downtime можно пропустить)
docker compose -f docker-compose.production.yml stop django bot

# 5. Пересоберите образы
docker compose -f docker-compose.production.yml build --no-cache django bot

# 6. Убедитесь что база данных и Redis запущены
docker compose -f docker-compose.production.yml up -d db redis

# 7. Примените миграции
docker compose -f docker-compose.production.yml run --rm django python manage.py migrate --noinput

# 8. Соберите статические файлы
docker compose -f docker-compose.production.yml run --rm django python manage.py collectstatic --noinput --clear

# 9. Запустите все сервисы
docker compose -f docker-compose.production.yml up -d

# 10. Проверьте статус
docker compose -f docker-compose.production.yml ps

# 11. Проверьте логи (если нужно)
docker compose -f docker-compose.production.yml logs -f django
```

---

## Важные замечания

### ⚠️ Миграции применяются автоматически

При запуске контейнера Django через `docker-entrypoint.sh` миграции применяются автоматически. 
Но для надежности рекомендуется применять их вручную перед перезапуском (как в скрипте выше).

### 🔄 Zero-downtime обновление

Для обновления без простоя:

```bash
# 1. Git pull
git pull origin main

# 2. Пересборка образа (без остановки)
docker compose -f docker-compose.production.yml build django

# 3. Применение миграций (если есть новые)
docker compose -f docker-compose.production.yml run --rm django python manage.py migrate --noinput

# 4. Сбор статики
docker compose -f docker-compose.production.yml run --rm django python manage.py collectstatic --noinput

# 5. Перезапуск только Django (rolling restart)
docker compose -f docker-compose.production.yml up -d --no-deps django
```

### 📊 Проверка после обновления

```bash
# Статус всех контейнеров
docker compose -f docker-compose.production.yml ps

# Логи Django
docker compose -f docker-compose.production.yml logs --tail=50 django

# Логи Bot
docker compose -f docker-compose.production.yml logs --tail=50 bot

# Проверка здоровья
docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

### 🐛 Если что-то пошло не так

```bash
# Откат к предыдущей версии (если нужно)
git checkout HEAD~1
docker compose -f docker-compose.production.yml build --no-cache django
docker compose -f docker-compose.production.yml up -d django

# Или полный перезапуск
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d --build
```

---

## Полезные команды

```bash
# Просмотр логов в реальном времени
docker compose -f docker-compose.production.yml logs -f

# Перезапуск конкретного сервиса
docker compose -f docker-compose.production.yml restart django

# Выполнение команды в контейнере Django
docker compose -f docker-compose.production.yml exec django python manage.py shell

# Создание суперпользователя
docker compose -f docker-compose.production.yml run --rm django python manage.py createsuperuser

# Очистка неиспользуемых образов
docker system prune -a

# Просмотр использования дискового пространства
docker system df
```

---

## Автоматизация через cron (опционально)

Если хотите автоматическое обновление:

```bash
# Добавьте в crontab (осторожно!)
# Обновление каждый день в 3:00 ночи
0 3 * * * cd /path/to/Ghostwriter && bash deploy/update.sh >> /var/log/ghostwriter-update.log 2>&1
```

---

## Контакты и поддержка

При возникновении проблем проверьте:
1. Логи контейнеров: `docker compose -f docker-compose.production.yml logs`
2. Статус контейнеров: `docker compose -f docker-compose.production.yml ps`
3. Доступность базы данных: `docker compose -f docker-compose.production.yml exec db pg_isready -U ghostwriter`
