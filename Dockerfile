# =============================================================================
# GHOSTWRITER - Django Application Dockerfile
# =============================================================================
# Production-ready контейнер для Django приложения
# Поддерживает PostgreSQL, Redis, систему токенов
# Включает мониторинг токенов GigaChat и кликов по кнопке подписки
# =============================================================================

FROM python:3.11-slim

# Метаданные
LABEL maintainer="Ghostwriter Team"
LABEL version="2.2"
LABEL description="Ghostwriter AI Content Generator - Django Application with Anti-Multiaccount Protection"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    gettext \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создание пользователя для безопасности
RUN groupadd --system django \
    && useradd --system --gid django --create-home django

# Установка рабочей директории
WORKDIR /app

# Копирование requirements и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY --chown=django:django . .

# Создание необходимых директорий
RUN mkdir -p /app/media /app/staticfiles /app/logs \
    && chown -R django:django /app

# Копирование и настройка entrypoint
COPY --chown=django:django docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Переключение на непривилегированного пользователя
USER django

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=ghostwriter.production_settings

# Открытие порта
EXPOSE 8000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Entrypoint и команда запуска
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "1000", "--max-requests", "1000", "--max-requests-jitter", "50", "ghostwriter.wsgi:application"]
