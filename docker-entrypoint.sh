#!/bin/bash
# ==============================================================================
# GHOSTWRITER - Docker Entrypoint Script
# ==============================================================================
# Выполняется перед запуском Django приложения
# ==============================================================================

set -e

echo "========================================================================"
echo "🚀 GHOSTWRITER - Starting Django Application"
echo "========================================================================"

# Ожидание готовности PostgreSQL
if [ -n "$DB_HOST" ]; then
    echo "⏳ Waiting for PostgreSQL..."
    while ! pg_isready -h $DB_HOST -U ${DB_USER:-ghostwriter} > /dev/null 2>&1; do
        sleep 1
    done
    echo "✅ PostgreSQL is ready!"
fi

# Ожидание готовности Redis
if [ -n "$REDIS_URL" ]; then
    echo "⏳ Waiting for Redis..."
    until python -c "import redis; r=redis.from_url('$REDIS_URL'); r.ping()" 2>/dev/null; do
        sleep 1
    done
    echo "✅ Redis is ready!"
fi

# Применение миграций
echo "📦 Applying database migrations..."
python manage.py migrate --noinput

# Сбор статических файлов
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Создание директории для логов
mkdir -p /app/logs

echo "========================================================================"
echo "✅ Initialization complete! Starting application..."
echo "========================================================================"

# Выполнение команды из CMD
exec "$@"
