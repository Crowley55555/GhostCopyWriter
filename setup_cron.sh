#!/bin/bash

# Скрипт для настройки автоматической очистки токенов через cron
# Использование: bash setup_cron.sh

echo "============================================"
echo "Настройка автоматической очистки токенов"
echo "============================================"
echo ""

# Получаем текущую директорию проекта
PROJECT_DIR=$(pwd)
PYTHON_PATH=$(which python)

echo "Директория проекта: $PROJECT_DIR"
echo "Python путь: $PYTHON_PATH"
echo ""

# Проверяем наличие manage.py
if [ ! -f "$PROJECT_DIR/manage.py" ]; then
    echo "❌ Ошибка: manage.py не найден в текущей директории"
    echo "Запустите скрипт из корня проекта Ghostwriter"
    exit 1
fi

echo "✅ manage.py найден"
echo ""

# Создаем задачи cron
echo "Создание заданий cron..."
echo ""

# Временный файл для новых заданий
TEMP_CRON=$(mktemp)

# Получаем текущий crontab (если есть)
crontab -l 2>/dev/null > "$TEMP_CRON" || true

# Проверяем, есть ли уже задание для cleanup_tokens
if grep -q "cleanup_tokens" "$TEMP_CRON"; then
    echo "⚠️  Задания для cleanup_tokens уже существуют в crontab"
    echo "Показываем существующие задания:"
    echo ""
    grep "cleanup_tokens" "$TEMP_CRON"
    echo ""
    read -p "Хотите заменить их? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Отменено пользователем"
        rm "$TEMP_CRON"
        exit 0
    fi
    # Удаляем старые задания
    grep -v "cleanup_tokens" "$TEMP_CRON" > "${TEMP_CRON}.tmp"
    mv "${TEMP_CRON}.tmp" "$TEMP_CRON"
fi

# Добавляем новые задания
cat >> "$TEMP_CRON" << EOF

# Ghostwriter: Автоматическая очистка токенов
# Деактивация истекших токенов - каждый день в 2:00
0 2 * * * cd $PROJECT_DIR && $PYTHON_PATH manage.py cleanup_tokens >> $PROJECT_DIR/logs/cleanup_tokens.log 2>&1

# Удаление старых деактивированных токенов (> 90 дней) - каждое воскресенье в 3:00
0 3 * * 0 cd $PROJECT_DIR && $PYTHON_PATH manage.py cleanup_tokens --delete --days=90 >> $PROJECT_DIR/logs/cleanup_tokens.log 2>&1

EOF

# Устанавливаем новый crontab
crontab "$TEMP_CRON"

if [ $? -eq 0 ]; then
    echo "✅ Cron задания успешно установлены!"
    echo ""
    echo "Добавлены следующие задания:"
    echo ""
    echo "1. Деактивация истекших токенов:"
    echo "   Время: Каждый день в 2:00"
    echo "   Команда: python manage.py cleanup_tokens"
    echo ""
    echo "2. Удаление старых токенов (> 90 дней):"
    echo "   Время: Каждое воскресенье в 3:00"
    echo "   Команда: python manage.py cleanup_tokens --delete --days=90"
    echo ""
    echo "Логи: $PROJECT_DIR/logs/cleanup_tokens.log"
    echo ""
    
    # Создаем директорию для логов
    mkdir -p "$PROJECT_DIR/logs"
    echo "✅ Директория для логов создана: $PROJECT_DIR/logs"
    echo ""
    
    echo "Текущий crontab:"
    echo "----------------"
    crontab -l | grep -A 2 "Ghostwriter"
    echo ""
else
    echo "❌ Ошибка при установке cron заданий"
    rm "$TEMP_CRON"
    exit 1
fi

# Очистка
rm "$TEMP_CRON"

echo "============================================"
echo "✅ Настройка завершена успешно!"
echo "============================================"
echo ""
echo "Для проверки работы cron:"
echo "  crontab -l"
echo ""
echo "Для просмотра логов:"
echo "  tail -f $PROJECT_DIR/logs/cleanup_tokens.log"
echo ""
echo "Для ручного запуска очистки:"
echo "  python manage.py cleanup_tokens"
echo "  python manage.py cleanup_tokens --dry-run"
echo ""
