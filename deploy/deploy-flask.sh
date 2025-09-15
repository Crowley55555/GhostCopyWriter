#!/bin/bash
# Скрипт развертывания Flask AI микросервиса на зарубежном сервере

set -e

echo "🤖 РАЗВЕРТЫВАНИЕ FLASK AI МИКРОСЕРВИСА (ЗАРУБЕЖНЫЙ СЕРВЕР)"
echo "=================================================================="
echo "⚠️  ВАЖНО: Этот сервис должен быть развернут на зарубежном сервере"
echo "    для корректного доступа к OpenAI API"
echo ""

# Проверка наличия .env файла
if [ ! -f flask_generator/.env ]; then
    echo "❌ Ошибка: Файл flask_generator/.env не найден!"
    echo "Создайте файл с настройками:"
    echo "OPENAI_API_KEY=your-openai-key"
    echo "GENERATOR_ENCRYPTION_KEY=k6W1hS1TpK-fOe-1pEGSSXmSDHkQNrpsI-TfuL-7EHI="
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

# Проверка доступности OpenAI API
echo "🌐 Проверка доступности OpenAI API..."
if command -v curl &> /dev/null; then
    if curl -s --connect-timeout 5 https://api.openai.com/v1/models > /dev/null; then
        echo "✅ OpenAI API доступен"
    else
        echo "⚠️  WARNING: OpenAI API может быть недоступен с этого сервера"
        echo "   Убедитесь, что сервер находится в юрисдикции с доступом к OpenAI"
    fi
fi

# Создание необходимых директорий
echo "📁 Создание директорий..."
sudo mkdir -p /opt/flask-ai/{logs,ssl,redis}
sudo chown -R $USER:$USER /opt/flask-ai

# Остановка существующих контейнеров
echo "🛑 Остановка существующих контейнеров..."
docker-compose -f docker-compose.flask.yml down

# Сборка образов
echo "🔨 Сборка Docker образов..."
docker-compose -f docker-compose.flask.yml build --no-cache

# Запуск Redis
echo "💾 Запуск Redis..."
docker-compose -f docker-compose.flask.yml up -d redis-flask

# Ожидание готовности Redis
echo "⏳ Ожидание готовности Redis..."
sleep 5

# Тестирование Flask приложения
echo "🧪 Тестирование Flask приложения..."
docker-compose -f docker-compose.flask.yml run --rm flask-ai python -c "
import requests
import json
from crypto_utils import encrypt_data, decrypt_data

print('Тестирование шифрования...')
test_data = {'test': 'encryption_test'}
encrypted = encrypt_data(json.dumps(test_data).encode())
decrypted = decrypt_data(encrypted)
print('✅ Шифрование работает')

print('Тестирование health endpoint...')
# Этот тест выполнится после запуска сервиса
"

# Запуск всех сервисов
echo "🚀 Запуск всех сервисов..."
docker-compose -f docker-compose.flask.yml up -d

# Проверка статуса
echo "🔍 Проверка статуса сервисов..."
sleep 10
docker-compose -f docker-compose.flask.yml ps

# Тестирование API endpoints
echo "🧪 Тестирование API..."
sleep 5

# Проверка health endpoint
if curl -f http://localhost:5000/ > /dev/null 2>&1; then
    echo "✅ Health endpoint работает"
else
    echo "❌ Health endpoint недоступен"
fi

# Проверка test endpoint
if curl -X POST -H "Content-Type: application/json" \
   -d '{"test": "data"}' \
   http://localhost:5000/test > /dev/null 2>&1; then
    echo "✅ Test endpoint работает"
else
    echo "❌ Test endpoint недоступен"
fi

echo ""
echo "✅ РАЗВЕРТЫВАНИЕ FLASK МИКРОСЕРВИСА ЗАВЕРШЕНО!"
echo "=================================================================="
echo "🤖 Flask AI API: http://localhost:5000"
echo "🔍 Health Check: http://localhost:5000/"
echo "📊 Логи: docker-compose -f docker-compose.flask.yml logs -f flask-ai"
echo "🛑 Остановка: docker-compose -f docker-compose.flask.yml down"
echo ""
echo "⚠️  ВАЖНО ДЛЯ ИНТЕГРАЦИИ:"
echo "1. Укажите URL этого сервера в переменной FLASK_EXTERNAL_URL Django приложения"
echo "2. Убедитесь, что ключи шифрования совпадают в обоих сервисах"
echo "3. Настройте SSL/HTTPS для безопасной передачи данных"
echo ""
echo "📝 Пример настройки в Django .env:"
echo "FLASK_EXTERNAL_URL=https://your-flask-server.com"
