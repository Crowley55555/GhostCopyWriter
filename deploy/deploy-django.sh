#!/bin/bash
# Скрипт развертывания Django приложения на российском сервере

set -e

echo "🚀 РАЗВЕРТЫВАНИЕ DJANGO ПРИЛОЖЕНИЯ (РОССИЙСКИЙ СЕРВЕР)"
echo "=================================================================="

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "❌ Ошибка: Файл .env не найден!"
    echo "Скопируйте env.example в .env и заполните переменные"
    exit 1
fi

echo "✅ Файл .env найден"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Ошибка: Docker не установлен!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Ошибка: Docker Compose не установлен!"
    exit 1
fi

echo "✅ Docker и Docker Compose доступны"

# Создание необходимых директорий
echo "📁 Создание директорий..."
sudo mkdir -p /opt/ghostwriter/{media,logs,postgres,redis,backups,ssl,static}
sudo chown -R $USER:$USER /opt/ghostwriter

# Остановка существующих контейнеров
echo "🛑 Остановка существующих контейнеров..."
docker-compose -f docker-compose.production.yml down

# Сборка образов
echo "🔨 Сборка Docker образов..."
docker-compose -f docker-compose.production.yml build --no-cache

# Запуск базы данных
echo "🗄️ Запуск базы данных..."
docker-compose -f docker-compose.production.yml up -d db redis

# Ожидание готовности БД
echo "⏳ Ожидание готовности базы данных..."
sleep 10

# Выполнение миграций
echo "📊 Выполнение миграций..."
docker-compose -f docker-compose.production.yml exec db psql -U ghostwriter -d ghostwriter -c "SELECT 1;" || {
    echo "Создание базы данных..."
    docker-compose -f docker-compose.production.yml exec db createdb -U postgres ghostwriter
}

# Применение миграций Django
docker-compose -f docker-compose.production.yml run --rm django python manage.py migrate --settings=ghostwriter.production_settings

# Сбор статических файлов
echo "🎨 Сбор статических файлов..."
docker-compose -f docker-compose.production.yml run --rm django python manage.py collectstatic --noinput --settings=ghostwriter.production_settings

# Создание суперпользователя (интерактивно)
echo "👤 Создание суперпользователя..."
docker-compose -f docker-compose.production.yml run --rm django python manage.py createsuperuser --settings=ghostwriter.production_settings

# Запуск всех сервисов
echo "🚀 Запуск всех сервисов..."
docker-compose -f docker-compose.production.yml up -d

# Проверка статуса
echo "🔍 Проверка статуса сервисов..."
sleep 5
docker-compose -f docker-compose.production.yml ps

echo ""
echo "✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО!"
echo "=================================================================="
echo "🌐 Django приложение: http://localhost:8000"
echo "🔧 Админ панель: http://localhost:8000/admin/"
echo "📊 Логи: docker-compose -f docker-compose.production.yml logs -f django"
echo "🛑 Остановка: docker-compose -f docker-compose.production.yml down"
echo ""
echo "⚠️  ВАЖНО: Не забудьте развернуть Flask микросервис на зарубежном сервере!"
echo "📝 Инструкции: deploy/deploy-flask.sh"
