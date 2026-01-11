# Django Application Dockerfile
# Обновлен под систему токенов и Telegram бота

FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    gettext \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN addgroup --system django && adduser --system --group django

# Установка рабочей директории
WORKDIR /app

# Копирование requirements и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Копирование проекта
COPY . .

# Создание необходимых директорий
RUN mkdir -p /app/media /app/staticfiles /app/logs

# Установка прав доступа
RUN chown -R django:django /app
USER django

# Сбор статических файлов
RUN python manage.py collectstatic --noinput --settings=ghostwriter.settings

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=ghostwriter.settings

# Открытие порта
EXPOSE 8000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# Команда запуска
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "ghostwriter.wsgi:application"]
