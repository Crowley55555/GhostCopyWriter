# 🚀 Инструкция по обновлению проекта после git pull

**Production:** используйте только `docker-compose.production.yml`. Сайт: `http://<сервер>:8010` (не `docker compose up` без `-f` — это dev на порту 8000).

См. также: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) · [README.md — Deployment](README.md#-deployment)

---

## Быстрое обновление (рекомендуется)

### Через SSH:

```bash
ssh user@your-server.com
cd /path/to/Ghostwriter

bash deploy/update.sh
```

Скрипт автоматически выполнит:
- ✅ `git pull` — получение изменений
- ✅ Остановку контейнеров Django, Bot и Nginx
- ✅ Пересборку Docker образов
- ✅ Применение миграций Django
- ✅ Сбор статических файлов
- ✅ Перезапуск всех сервисов production
- ✅ Проверку статуса

---

## Ручное обновление (пошагово)

```bash
cd /path/to/Ghostwriter

git pull origin main

docker compose -f docker-compose.production.yml stop django bot nginx

docker compose -f docker-compose.production.yml build --no-cache django bot

docker compose -f docker-compose.production.yml up -d db redis

docker compose -f docker-compose.production.yml run --rm django python manage.py migrate --noinput

docker compose -f docker-compose.production.yml run --rm django python manage.py collectstatic --noinput --clear

docker compose -f docker-compose.production.yml up -d --remove-orphans

docker compose -f docker-compose.production.yml ps
curl -I http://127.0.0.1:8010/
```

---

## Важные замечания

### ⚠️ Миграции применяются автоматически

При старте контейнера Django (`docker-entrypoint.sh`) миграции применяются сами. Для надёжности их можно выполнить вручную до `up -d` (см. выше).

### 🔄 Zero-downtime обновление

```bash
git pull origin main
docker compose -f docker-compose.production.yml build django
docker compose -f docker-compose.production.yml run --rm django python manage.py migrate --noinput
docker compose -f docker-compose.production.yml run --rm django python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml up -d --no-deps django
docker compose -f docker-compose.production.yml restart nginx
```

### 📊 Проверка после обновления

| Проверка | Команда |
|----------|---------|
| HTTP на 8010 | `curl -I http://127.0.0.1:8010/` |
| Контейнеры | `docker compose -f docker-compose.production.yml ps` |
| Nginx Up + порт | `docker ps \| grep nginx-prod` → `0.0.0.0:8010->80/tcp` |
| Логи Django | `docker compose -f docker-compose.production.yml logs --tail=50 django` |
| Логи Bot | `docker compose -f docker-compose.production.yml logs --tail=50 bot` |
| Логи Nginx | `docker compose -f docker-compose.production.yml logs --tail=50 nginx` |

Ожидаемые контейнеры: `ghostwriter-*-prod` (db, redis, django, nginx, bot).

### 🐛 Типичные проблемы

**Connection refused на 8010** — Nginx не запущен (`Restarting` / `Created`):

```bash
docker logs ghostwriter-nginx-prod --tail 30
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d --build
```

**Bind for 443 failed** — на сервере старый `docker-compose.production.yml` с `"443:443"`. Нужна версия только с `"8010:80"` (см. `git pull`).

**TELEGRAM_BOT_TOKEN не установлен** — заполните `.env`, затем:

```bash
docker compose -f docker-compose.production.yml up -d --force-recreate bot
```

**Полный перезапуск:**

```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d --build --remove-orphans
```

---

## Полезные команды

```bash
docker compose -f docker-compose.production.yml logs -f
docker compose -f docker-compose.production.yml restart django nginx
docker compose -f docker-compose.production.yml exec django python manage.py shell
docker compose -f docker-compose.production.yml run --rm django python manage.py createsuperuser
docker system prune -a
```

---

## Автоматизация через cron (опционально)

```bash
0 3 * * * cd /path/to/Ghostwriter && bash deploy/update.sh >> /var/log/ghostwriter-update.log 2>&1
```

---

## Контакты и поддержка

1. Логи: `docker compose -f docker-compose.production.yml logs`
2. Статус: `docker compose -f docker-compose.production.yml ps`
3. БД: `docker compose -f docker-compose.production.yml exec db pg_isready -U ghostwriter`
