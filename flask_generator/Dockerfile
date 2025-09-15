# Flask AI Generator Microservice Dockerfile
# Оптимизированный для развертывания на зарубежных серверах

FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN addgroup --system flask && adduser --system --group flask

# Установка рабочей директории
WORKDIR /app

# Копирование requirements и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка gunicorn для продакшена
RUN pip install gunicorn

# Копирование Flask приложения
COPY . .

# Создание директории для логов
RUN mkdir -p /app/logs

# Установка прав доступа
RUN chown -R flask:flask /app
USER flask

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV FLASK_APP=app.py

# Открытие порта
EXPOSE 5000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Команда запуска с gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--max-requests", "1000", "app:app"]
