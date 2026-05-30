#!/bin/bash
# ==============================================================================
# GHOSTWRITER - Скрипт обновления после git pull
# ==============================================================================
# Использование: ./deploy/update.sh
# Или через SSH: bash deploy/update.sh
# ==============================================================================

set -e

echo "========================================================================"
echo "🔄 GHOSTWRITER - Обновление проекта после git pull"
echo "========================================================================"

# Переход в директорию проекта (если скрипт запущен из корня)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_DIR"

echo "📂 Директория проекта: $PROJECT_DIR"

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "⚠️  Предупреждение: Файл .env не найден!"
    echo "   Убедитесь, что переменные окружения настроены"
fi

# 1. Git pull
echo ""
echo "📥 Шаг 1: Получение изменений из Git..."
git pull origin main || git pull origin dev || {
    echo "❌ Ошибка при git pull. Проверьте подключение к репозиторию."
    exit 1
}
echo "✅ Изменения получены"

# 2. Остановка контейнеров (опционально, можно пропустить для zero-downtime)
echo ""
echo "🛑 Шаг 2: Остановка контейнеров..."
docker compose -f docker-compose.production.yml stop django bot nginx || {
    echo "⚠️  Некоторые контейнеры уже остановлены или не запущены"
}

# 3. Пересборка образов
echo ""
echo "🔨 Шаг 3: Пересборка Docker образов..."
docker compose -f docker-compose.production.yml build --no-cache django bot || {
    echo "❌ Ошибка при сборке образов"
    exit 1
}
echo "✅ Образы пересобраны"

# 4. Запуск базы данных и Redis (если не запущены)
echo ""
echo "🗄️  Шаг 4: Проверка базы данных и Redis..."
docker compose -f docker-compose.production.yml up -d db redis || {
    echo "❌ Ошибка при запуске базы данных"
    exit 1
}

# Ожидание готовности БД
echo "⏳ Ожидание готовности базы данных..."
sleep 5
until docker compose -f docker-compose.production.yml exec -T db pg_isready -U ghostwriter > /dev/null 2>&1; do
    echo "   Ожидание PostgreSQL..."
    sleep 2
done
echo "✅ База данных готова"

# 5. Применение миграций (вручную, на случай если entrypoint не сработал)
echo ""
echo "📊 Шаг 5: Применение миграций Django..."
docker compose -f docker-compose.production.yml run --rm django python manage.py migrate --noinput || {
    echo "❌ Ошибка при применении миграций"
    exit 1
}
echo "✅ Миграции применены"

# 6. Сбор статических файлов
echo ""
echo "📁 Шаг 6: Сбор статических файлов..."
docker compose -f docker-compose.production.yml run --rm django python manage.py collectstatic --noinput --clear || {
    echo "❌ Ошибка при сборе статических файлов"
    exit 1
}
echo "✅ Статические файлы собраны"

# 7. Перезапуск всех сервисов
echo ""
echo "🚀 Шаг 7: Запуск всех сервисов..."
docker compose -f docker-compose.production.yml up -d || {
    echo "❌ Ошибка при запуске сервисов"
    exit 1
}
echo "✅ Сервисы запущены"

# 8. Проверка статуса
echo ""
echo "🔍 Шаг 8: Проверка статуса контейнеров..."
sleep 5
docker compose -f docker-compose.production.yml ps

# 9. Показ логов (последние 20 строк)
echo ""
echo "📋 Последние логи Django (для проверки):"
docker compose -f docker-compose.production.yml logs --tail=20 django

echo ""
echo "========================================================================"
echo "✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!"
echo "========================================================================"
echo ""
echo "📊 Полезные команды:"
echo "   Сайт (HTTPS):   https://<server>  (порт 443, см. SITE_URL в .env)"
echo "   Логи Django:    docker compose -f docker-compose.production.yml logs -f django"
echo "   Логи Bot:       docker compose -f docker-compose.production.yml logs -f bot"
echo "   Логи Nginx:     docker compose -f docker-compose.production.yml logs -f nginx"
echo "   Статус:         docker compose -f docker-compose.production.yml ps"
echo "   Остановка:      docker compose -f docker-compose.production.yml down"
echo "   Перезапуск:     docker compose -f docker-compose.production.yml restart django nginx"
echo ""
