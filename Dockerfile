# ==============================================================================
# GHOSTWRITER - Django Application (Main Service)
# ==============================================================================
# Включает: Django, Security, Токены, APScheduler, Redis
# Версия: 3.0 (Secure & Anonymous Edition)
# ==============================================================================

FROM python:3.11-slim

LABEL maintainer="Ghostwriter Team"
LABEL version="3.0"
LABEL description="Django application with security, token system, and APScheduler"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    gettext \
    postgresql-client \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN addgroup --system django && adduser --system --group django

# Установка рабочей директории
WORKDIR /app

# Копирование requirements и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Копирование проекта
COPY --chown=django:django . .

# Создание необходимых директорий
RUN mkdir -p /app/media /app/staticfiles /app/logs && \
    chown -R django:django /app

# Переключение на пользователя django
USER django

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=ghostwriter.settings

# Открытие порта
EXPOSE 8000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Entrypoint скрипт
COPY --chown=django:django docker-entrypoint.sh /app/
USER root
RUN chmod +x /app/docker-entrypoint.sh
USER django

# Команда запуска
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "ghostwriter.wsgi:application"]
