# =============================================================================
# GHOSTWRITER - Flask AI Generator Microservice
# =============================================================================
# OpenAI GPT + DALL-E микросервис для зарубежного сервера
# =============================================================================

FROM python:3.11-slim

# Метаданные
LABEL maintainer="Ghostwriter Team"
LABEL version="2.2"
LABEL description="Ghostwriter Flask AI Generator - GPT-4o-mini + DALL-E"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создание пользователя для безопасности
RUN groupadd --system flask \
    && useradd --system --gid flask --create-home flask

# Установка рабочей директории
WORKDIR /app

# Копирование requirements и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt gunicorn

# Копирование Flask приложения
COPY --chown=flask:flask . .

# Создание директории для логов
RUN mkdir -p /app/logs \
    && chown -R flask:flask /app

# Переключение на непривилегированного пользователя
USER flask

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_APP=app.py

# Открытие порта
EXPOSE 5000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Команда запуска
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--max-requests", "1000", "--max-requests-jitter", "50", "app:app"]
