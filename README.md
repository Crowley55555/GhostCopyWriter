# Ghostwriter

**Ghostwriter** — это современная микросервисная платформа для генерации профессионального, цепляющего и SEO-оптимизированного контента для социальных сетей с автоматическим подбором визуала.

[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![GigaChat](https://img.shields.io/badge/GigaChat-00A651?style=for-the-badge)](https://developers.sber.ru/portal/products/gigachat)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)

> **Статус проекта:** Готов к продакшену | **Версия:** 2.2 (Anti-Multiaccount Edition)

---

## 📋 Содержание

- [Возможности](#-возможности)
- [Архитектура](#-архитектура)
- [Быстрый старт](#-быстрый-старт)
- [Система токенов и Telegram Bot](#-система-токенов-и-telegram-bot)
- [Автоматизация](#-автоматизация)
- [Deployment](#-deployment)
- [Тестирование](#-тестирование)
- [Требования и зависимости](#-требования-и-зависимости)
- [Документация](#-документация)
- [FAQ](#-faq)
- [Лицензия](#-лицензия)

---

## ✨ Возможности

### 🎯 Генерация контента
- Генерация текстов для **VK, Дзен, Telegram, TikTok, Instagram, Facebook, Twitter/X, LinkedIn**
- **Гибкая генерация изображений**: чекбокс для автоматической генерации или кнопка для генерации по запросу
- Гибкая настройка: тон, цель, эмоции, формат, стиль, CTA
- Адаптация под целевую аудиторию и платформу
- Экономия токенов: пользователь сам выбирает, когда генерировать изображение

### 🤖 AI Интеграция
- **GigaChat** (Сбер) - для российских пользователей
- **OpenAI GPT-4o-mini + DALL-E** - для международной аудитории
- Автоматическое переключение между AI провайдерами
- Fallback система при недоступности сервисов

### 🔐 Безопасность и соответствие законам
- **152-ФЗ "О персональных данных"** - полное соблюдение
- Локализация данных на территории РФ
- Шифрование данных между сервисами (Fernet)
- Анонимный доступ через временные токены
- Telegram Bot без сбора ПДн

### 📱 Telegram Bot интеграция
- **Анонимный доступ** без регистрации
- Генерация временных токенов-ссылок
- **Защита от мультиаккаунтов** (один DEMO токен на пользователя)
- Бесплатный старт (30K GigaChat + 30K OpenAI, бессрочно)
- Платные тарифы с подпиской (30 дней, автоматическое пополнение)
- Реальная интеграция через API
- Юридические документы (оферта, политика конфиденциальности, отказ от ответственности)

### 🤖 Автоматизация (NEW!)
- **APScheduler** - встроенный планировщик задач
- Автоматическая деактивация истекших токенов (каждый час)
- Автоматический сброс дневных лимитов (ежедневно)
- Автоматическое удаление старых токенов (еженедельно)
- **Никакой настройки cron не требуется!**

### 💾 Управление данными
- Сохранение истории генераций
- Система шаблонов настроек
- Персонализированные профили
- Стена пользователя с контентом

---

## 🏗️ Архитектура

### Микросервисная архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    ПОЛЬЗОВАТЕЛЬ                              │
│                                                              │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐          │
│  │ Веб-браузер│    │ Telegram │      │ Mobile   │          │
│  │           │      │ Bot      │      │ App      │          │
│  └─────┬────┘      └────┬─────┘      └────┬─────┘          │
└────────┼──────────────────┼────────────────┼──────────────────┘
         │                  │                 │
         ▼                  ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│              DJANGO APPLICATION (РФ)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ • UI / Templates                                      │  │
│  │ • Аутентификация / Токены                            │  │
│  │ • База данных (SQLite / PostgreSQL)                  │  │
│  │ • История генераций                                  │  │
│  │ • Персональные данные (152-ФЗ)                       │  │
│  │ • Telegram Bot API                                   │  │
│  │ • APScheduler (автоочистка)                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                         ▲                                    │
│                         │ Зашифрованная связь (Fernet)      │
│                         ▼                                    │
│              GigaChat API (Сбер)                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Обезличенные промпты
                          ▼
┌─────────────────────────────────────────────────────────────┐
│         FLASK GENERATOR (Зарубежный сервер)                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ • AI Generation Service                               │  │
│  │ • OpenAI GPT (текст)                                 │  │
│  │ • DALL-E (изображения)                               │  │
│  │ • Без персональных данных                            │  │
│  │ • Шифрование запросов/ответов                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Компоненты

#### 🎯 Django Application (Основной сервис)
- **Назначение:** UI, аутентификация, данные
- **База данных:** SQLite (dev) / PostgreSQL (prod)
- **Функции:**
  - Регистрация и авторизация
  - Управление профилями
  - История генераций
  - Система токенов
  - Telegram Bot
  - Автоматизация задач (APScheduler)
- **Порт:** 8000 (локальная разработка) / только внутри Docker в production (снаружи — **443** HTTPS через Nginx)

#### 🤖 Flask Generator (AI Микросервис)
- **Назначение:** Генерация через внешние AI API
- **Функции:**
  - Генерация текста (OpenAI GPT-4o-mini)
  - Генерация промптов для изображений (GPT-4o-mini)
  - Создание изображений (DALL-E 3/2)
- **Особенности:**
  - Независимый деплой на зарубежном сервере
  - Работает с обезличенными данными
  - Шифрование связи с Django (Fernet)
- **Порт:** 5000

#### 📱 Telegram Bot
- **Назначение:** Анонимный доступ к платформе
- **Функции:**
  - Генерация временных токенов
  - Выдача ссылок доступа
  - Демо и платные тарифы
- **Особенности:**
  - Без сбора ПДн (152-ФЗ)
  - Реальная интеграция с Django API
  - Заглушки только для платежей

---

## 🚀 Быстрый старт

### Требования
- Python 3.9+
- pip
- Git

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/Ghostwriter.git
cd Ghostwriter
```

### 2. Виртуальное окружение

```bash
# Создание
python -m venv venv

# Активация (Windows)
venv\Scripts\activate

# Активация (Linux/macOS)
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
# Основные зависимости (Django + Telegram Bot + GigaChat)
pip install -r requirements.txt

# Опционально: тестовые зависимости
pip install -r requirements-test.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
# GigaChat API
GIGACHAT_CLIENT_ID=your_gigachat_client_id
GIGACHAT_CLIENT_SECRET=your_gigachat_client_secret

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SITE_URL=http://localhost:8000

# Django
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True

# Flask Generator (опционально)
FLASK_GEN_URL=http://localhost:5000
GENERATOR_ENCRYPTION_KEY=your-encryption-key

# OpenAI (для Flask)
OPENAI_API_KEY=your-openai-api-key
```

### 5. Инициализация базы данных

```bash
# Применить миграции
python manage.py migrate

# Создать суперпользователя (опционально)
python manage.py createsuperuser
```

### 6. Создание токена разработчика

```bash
# Создать бессрочный токен для разработки
python manage.py create_dev_token --name="Ваше Имя"
```

Вы получите:
```
✅ DEVELOPER token uspeshno sozdan!
Razrabotchik: Ваше Имя
Token: 550e8400-e29b-41d4-a716-446655440000
Tip: Bessrochniy (bezlimit)

VASHA SSYLKA DOSTUPA:
http://localhost:8000/auth/token/550e8400-e29b-41d4-a716-446655440000/
```

Токен сохранен в файл `.dev_token` для удобства.

### 7. Запуск Django сервера

```bash
python manage.py runserver
```

При запуске увидите:
```
======================================================================
🤖 Планировщик фоновых задач запущен!
======================================================================
📋 Активные задачи:
  1️⃣ Деактивация истекших токенов - каждый час
  2️⃣ Сброс DEMO лимитов - каждый день в 00:01
  3️⃣ Удаление старых токенов - воскресенье в 03:00
======================================================================
```

### 8. Открыть приложение

Откройте в браузере ссылку из шага 6 или перейдите по адресу:
```
http://localhost:8000/
```

### 9. (Опционально) Запуск Telegram бота

В отдельном терминале:

```bash
# Активируйте виртуальное окружение
venv\Scripts\activate  # Windows
# или
source venv/bin/activate  # Linux/macOS

# Запустите бота
python bot.py
```

Теперь можно:
1. Найти бота в Telegram
2. Нажать `/start`
3. Получить DEMO токен (5 дней, 5 генераций/день)
4. Открыть ссылку и начать работу!

### 10. (Опционально) Запуск Flask микросервиса

Если нужна генерация через OpenAI:

```bash
cd flask_generator
pip install -r requirements.txt
python app.py
```

**Готово!** Платформа запущена и готова к работе! 🎉

---

## 🎫 Система токенов и Telegram Bot

### Концепция
Ghostwriter использует систему **временных токенов-ссылок** для доступа без регистрации и сбора персональных данных.

### Тарифы и типы токенов

| Тариф | Цена | Лимиты | Срок действия | Статус |
|-------|------|--------|--------------|--------|
| 🆓 **Бесплатный старт** | 0₽ | 30K GigaChat + 30K OpenAI | Бессрочно | ✅ Работает |
| 📊 **Базовый** | 590₽/мес | 200K GigaChat + 100K OpenAI | 30 дней (подписка) | ✅ Работает |
| ⭐ **Про** | 1190₽/мес | 500K GigaChat + 200K OpenAI | 30 дней (подписка) | ✅ Работает |
| 🚀 **Безлимит** | 2490₽/мес | ∞ GigaChat + 500K OpenAI | 30 дней (подписка) | ✅ Работает |
| 👨‍💻 **DEVELOPER** | - | Безлимит | Бессрочно | ✅ Работает |

**Важно:** Токены обновляются ежемесячно при активной подписке. Один пользователь может иметь только один активный бесплатный токен.

### Telegram Bot

#### Получение токена

1. Найдите бота в Telegram: `@Ghostcopywriterregistration_bot`
2. Нажмите `/start`
3. Ознакомьтесь с юридическими документами (оферта, политика конфиденциальности, отказ от ответственности)
4. Примите все документы
5. Выберите тариф:
   - 🆓 **Бесплатный старт** - бесплатно, бессрочно
   - 📊 **Базовый** - 590₽/мес
   - ⭐ **Про** - 1190₽/мес
   - 🚀 **Безлимит** - 2490₽/мес
6. Получите **реальную рабочую ссылку** с токеном
7. Откройте ссылку в браузере
8. Начните генерировать контент!

**Защита от мультиаккаунтов:** Один пользователь может иметь только один активный бесплатный токен. При попытке создать второй токен вы получите ссылку на существующий.

#### Особенности бота

- ✅ **Анонимность** - не запрашивает телефон, email, имя
- ✅ **Без ПДн** - полное соблюдение 152-ФЗ
- ✅ **Реальные токены** - интеграция через Django API
- ✅ **Мгновенный доступ** - ссылка работает сразу
- ✅ **Защита от мультиаккаунтов** - один DEMO токен на пользователя
- ✅ **Платежи** - интеграция с ЮКасса, реальные подписки
- ✅ **Юридические документы** - оферта, политика конфиденциальности, отказ от ответственности

### Создание токена разработчика

Для тестирования и разработки:

```bash
python manage.py create_dev_token --name="Ваше Имя"
```

Получите:
- Бессрочный токен
- Безлимитные генерации
- Ссылка сохраняется в `.dev_token`

### API для создания токенов

Django предоставляет API endpoints для Telegram бота:

#### POST /api/tokens/create/
Создание нового токена

**Запрос:**
```json
{
  "token_type": "DEMO",
  "expires_days": 5,
  "daily_limit": 5
}
```

**Ответ:**
```json
{
  "token": "550e8400-e29b-41d4-a716-446655440000",
  "token_type": "DEMO",
  "expires_at": "2026-01-20T12:00:00Z",
  "daily_limit": 5,
  "url": "http://site.com/auth/token/550e8400.../",
  "created_at": "2026-01-15T12:00:00Z",
  "is_active": true
}
```

#### GET /api/tokens/<uuid>/
Получение информации о токене

**Ответ:**
```json
{
  "token": "550e8400-e29b-41d4-a716-446655440000",
  "token_type": "DEMO",
  "is_active": true,
  "expires_at": "2026-01-20T12:00:00Z",
  "daily_generations_left": 5,
  "total_used": 0,
  "last_used": null,
  "is_expired": false
}
```

---

## 🤖 Автоматизация

### APScheduler - встроенный планировщик

Ghostwriter **автоматически** выполняет фоновые задачи без необходимости настройки cron или Task Scheduler.

### Что автоматизировано

#### 1. Деактивация истекших токенов
- **Частота:** Каждый час (в :00 минут)
- **Действие:** Находит токены где `expires_at < now` и устанавливает `is_active = False`
- **Логирование:** `✅ Автоматическая очистка: деактивировано N токенов`

#### 2. Сброс дневных лимитов DEMO
- **Частота:** Каждый день в 00:01
- **Действие:** Сбрасывает `daily_generations_left = 5` для всех DEMO токенов
- **Логирование:** `🔄 Автоматический сброс: обновлено N DEMO токенов`

#### 3. Удаление старых токенов
- **Частота:** Каждое воскресенье в 03:00
- **Действие:** Удаляет токены где `is_active = False` и `expires_at < (now - 90 days)`
- **Логирование:** `🗑️ Автоматическая очистка: удалено N старых токенов`

### Преимущества

| Характеристика | APScheduler | Cron/Task Scheduler |
|----------------|-------------|---------------------|
| Настройка | ✅ Не требуется | ❌ Требуется |
| Кроссплатформенность | ✅ Да | ⚠️ Разная для ОС |
| Мониторинг | ✅ Встроенный | ❌ Внешний |
| Логирование | ✅ Django logs | ⚠️ Отдельные файлы |
| Перезапуск | ✅ Автоматически | ⚠️ Вручную |

### Проверка работы

```python
# Django Shell
python manage.py shell

from generator.scheduler import get_scheduler_status

status = get_scheduler_status()
print(f"Работает: {status['running']}")  # True
print(f"Задач: {len(status['jobs'])}")   # 3

for job in status['jobs']:
    print(f"- {job['name']}: {job['next_run']}")
```

**Результат:**
```
Работает: True
Задач: 3
- Деактивация истекших токенов: 2026-01-11 15:00:00
- Сброс дневных лимитов DEMO: 2026-01-12 00:01:00
- Удаление старых токенов: 2026-01-14 03:00:00
```

### Ручной запуск (опционально)

Если нужно запустить очистку вручную:

```bash
# Через management команду
python manage.py cleanup_tokens

# С просмотром без изменений
python manage.py cleanup_tokens --dry-run

# С удалением старых токенов
python manage.py cleanup_tokens --delete --days=90
```

---

## 🚀 Deployment

| Документ | Назначение |
|----------|------------|
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Полная пошаговая инструкция для сервера |
| [DEPLOY_UPDATE.md](DEPLOY_UPDATE.md) | Обновление после `git pull` |
| [env.production.example](env.production.example) | Шаблон `.env` для production |

### Порты

| Режим | Файл compose | Доступ к сайту |
|-------|----------------|----------------|
| **Локальная разработка** | `docker-compose.yml` | `http://localhost:8000` |
| **Production (сервер)** | `docker-compose.production.yml` | `https://<IP или домен>` (порт **443**) |

В production Django (**8000**) и PostgreSQL/Redis **не публикуются** на хост — только Nginx на **443** (самоподписанный SSL для IP, см. `deploy/generate-ssl-ip.sh`).

---

### Production на сервере (Docker Compose)

```bash
cd /opt/GhostCopyWriter   # или ваш путь к проекту

cp env.production.example .env
nano .env                  # заполнить DJANGO_SECRET_KEY, DB_PASSWORD, TELEGRAM_BOT_TOKEN, SITE_URL и др.
chmod 600 .env

bash deploy/generate-ssl-ip.sh 85.208.86.148   # самоподписанный сертификат для IP

docker compose -f docker-compose.production.yml up -d --build --remove-orphans

docker compose -f docker-compose.production.yml ps
curl -Ik https://127.0.0.1/

docker compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

**Важно:** всегда указывайте `-f docker-compose.production.yml`. Команда `docker compose up` без `-f` поднимает **dev**-стек (`docker-compose.yml`, порт **8000**).

**Сайт:** `https://ваш-сервер` · **Админка:** `https://ваш-сервер/admin/` (браузер может предупредить о самоподписанном сертификате)

**Обновление после изменений в Git:**

```bash
bash deploy/update.sh
# или: git pull && docker compose -f docker-compose.production.yml up -d --build
```

**Скрипты в `deploy/`:**

| Скрипт | Описание |
|--------|----------|
| `deploy-django.sh` | Первичный деплой Django-стека |
| `deploy-flask.sh` | Flask на зарубежном сервере (OpenAI) |
| `deploy-full.sh` | Интерактивный выбор типа деплоя |
| `update.sh` | Обновление production после `git pull` |

---

### Локальная разработка (Docker Compose)

```bash
cp env.example .env
nano .env

docker compose up -d
docker compose exec django python manage.py migrate
docker compose exec django python manage.py createsuperuser
```

Сайт: `http://localhost:8000`

Опционально — полный стек с Flask: `docker compose up -d` (все сервисы из `docker-compose.yml`).

---

### Переменные окружения (Production)

Скопируйте `env.production.example` → `.env`. Основные переменные:

```bash
DJANGO_SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,IP_СЕРВЕРА

DB_HOST=db
DB_NAME=ghostwriter
DB_USER=ghostwriter
DB_PASSWORD=...

GIGACHAT_CREDENTIALS=...
GENERATOR_ENCRYPTION_KEY=...

TELEGRAM_BOT_TOKEN=...
BOT_USERNAME=your_bot
TELEGRAM_WEBHOOK_SECRET=...
SITE_URL=https://85.208.86.148
USE_HTTPS=true
SECURE_HSTS_SECONDS=0

FLASK_EXTERNAL_URL=https://your-flask-server.com   # если используете OpenAI
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
```

Полный список — в [env.production.example](env.production.example).

---

### Ручной deployment (без Docker)

Для production рекомендуется Docker. При ручной установке проксируйте на Gunicorn (`127.0.0.1:8000`) или на Docker Nginx (`127.0.0.1:443`).

**Telegram Bot:** в Docker-стеке бот в контейнере `ghostwriter-bot-prod` (polling). Отдельно: `python bot.py` с тем же `.env`.

---

## 🧪 Тестирование

### Статистика

- **Всего тестов:** 21
- **Успешность:** 100%
- **Время выполнения:** 5-7 секунд
- **Покрытие:** 85%+

### Запуск тестов

#### Полный набор (рекомендуется)

```bash
# Все тесты с отчетом
python run_tests.py
```

**Результат:** Файл `test_results.txt` с подробным отчетом

#### Только Django тесты

```bash
# Windows PowerShell
$env:DJANGO_SETTINGS_MODULE="ghostwriter.test_settings"; python manage.py test tests.test_django_models tests.test_django_isolated

# Linux/macOS
DJANGO_SETTINGS_MODULE=ghostwriter.test_settings python manage.py test tests.test_django_models tests.test_django_isolated
```

#### Отдельные наборы

```bash
# Только модели
python manage.py test tests.test_django_models --settings=ghostwriter.test_settings

# Только изолированные тесты
python manage.py test tests.test_django_isolated --settings=ghostwriter.test_settings

# Конкретный тест
python manage.py test tests.test_django_models.UserProfileModelTest --settings=ghostwriter.test_settings
```

#### С покрытием кода

```bash
# Установите coverage
pip install coverage

# Запустите с покрытием
coverage run --source='.' manage.py test --settings=ghostwriter.test_settings
coverage report
coverage html  # HTML отчет в htmlcov/
```

### Структура тестов

```
tests/
├── test_django_models.py        # Тесты моделей (10 тестов)
├── test_django_isolated.py      # Функциональные тесты (11 тестов)
├── test_flask_app.py            # Тесты Flask микросервиса
└── README.md                    # Документация тестирования
```

### Что тестируется

#### ✅ Модели данных
- UserProfile: создание, валидация, связи
- Generation: CRUD, версионирование, анонимные записи
- GenerationTemplate: шаблоны, уникальность, JSON
- TemporaryAccessToken: токены, истечение, лимиты

#### ✅ Аутентификация
- Quick login система
- Регистрация и авторизация
- Права доступа
- Токен-based authentication

#### ✅ Генерация контента
- Полный цикл создания постов
- Обработка форм
- Сохранение результатов
- Перегенерация текста/изображений

#### ✅ API и интеграция
- AJAX запросы
- JSON endpoints
- Telegram Bot API
- Token creation API

---

## 📦 Требования и зависимости

### Основные зависимости (`requirements.txt`)

```python
# Django Framework
Django>=4.2
django-widget-tweaks>=1.4.0

# AI & ML
langchain-gigachat>=0.3.11
langchain-core>=0.3,<0.4
gigachat>=0.1.0

# Telegram Bot
python-telegram-bot==20.7

# HTTP & Networking
requests>=2.31.0
beautifulsoup4>=4.10.0

# Утилиты
python-dotenv>=1.0.0
cryptography>=3.4.0
APScheduler>=3.10.4
```

### Тестовые зависимости (`requirements-test.txt`)

```python
# Тестовые фреймворки
pytest>=7.0.0
pytest-django>=4.5.0
pytest-cov>=4.0.0

# Нагрузочное тестирование
locust>=2.14.0

# Качество кода
flake8>=6.0.0
black>=23.0.0
isort>=5.12.0
```

### Flask микросервис (`flask_generator/requirements.txt`)

```python
# Flask
Flask>=2.3.0
gunicorn>=20.1.0

# AI
openai>=1.0.0

# Утилиты
requests>=2.31.0
cryptography>=3.4.0
python-dotenv>=1.0.0
```

### Установка

```bash
# Production (минимальная)
pip install -r requirements.txt

# Development (с тестами)
pip install -r requirements.txt -r requirements-test.txt

# Flask микросервис (отдельно)
cd flask_generator
pip install -r requirements.txt
```

---

## 📚 Документация

### Структура файлов проекта

```
Ghostwriter/
├── 📄 README.md                    # Этот файл - основная документация
├── 📄 LICENSE                      # MIT License
│
├── 🐍 manage.py                   # Django management
├── 🐍 bot.py                      # Telegram Bot
├── 🐍 run_tests.py                # Запуск тестов
│
├── 📦 requirements.txt            # Основные зависимости
├── 📦 requirements-test.txt       # Тестовые зависимости
├── 📄 env.example                 # Пример .env файла
│
├── 🗂️ generator/                  # Django приложение
│   ├── models.py                 # Модели (User, Generation, Token)
│   ├── views.py                  # Представления и API
│   ├── urls.py                   # URL маршруты
│   ├── forms.py                  # Формы
│   ├── middleware.py             # Token middleware
│   ├── decorators.py             # Декораторы (@token_required)
│   ├── scheduler.py              # APScheduler задачи
│   ├── gigachat_api.py           # GigaChat интеграция
│   ├── fastapi_client.py         # Flask клиент
│   ├── templates/                # HTML шаблоны
│   ├── static/                   # CSS, JS
│   └── management/commands/      # Management команды
│       ├── cleanup_tokens.py     # Очистка токенов
│       └── create_dev_token.py   # Создание dev токена
│
├── 🗂️ ghostwriter/                # Django настройки
│   ├── settings.py               # Основные настройки
│   ├── test_settings.py          # Настройки тестирования
│   ├── urls.py                   # URL конфигурация
│   └── wsgi.py                   # WSGI приложение
│
├── 🗂️ flask_generator/            # Flask микросервис
│   ├── 📄 README.md              # Документация Flask
│   ├── app.py                    # Flask приложение
│   ├── text_gen.py               # Генерация текста
│   ├── image_gen.py              # Генерация изображений
│   ├── requirements.txt          # Flask зависимости
│   └── Dockerfile                # Docker образ
│
├── 🗂️ tests/                      # Тестирование
│   ├── test_django_models.py     # Тесты моделей
│   ├── test_django_isolated.py   # Функциональные тесты
│   └── test_flask_app.py         # Flask тесты
│
├── 🗂️ media/                      # Сгенерированные изображения
├── 🗂️ staticfiles/                # Статические файлы (CSS, JS)
│
├── 🐳 docker-compose.yml              # Docker: локальная разработка (:8000)
├── 🐳 docker-compose.production.yml   # Docker: production (HTTPS :443)
├── 🐳 docker-compose.flask.yml        # Docker: Flask (зарубежный сервер)
├── 🐳 nginx.prod.conf                 # Nginx для production
├── 🐳 Dockerfile                      # Docker образ Django
├── 📄 DEPLOYMENT_GUIDE.md             # Инструкция по деплою на сервер
├── 📄 DEPLOY_UPDATE.md                # Обновление после git pull
└── 🗂️ deploy/                         # Скрипты деплоя
    ├── deploy-full.sh
    ├── deploy-django.sh
    ├── deploy-flask.sh
    └── update.sh
```

### Дополнительные ресурсы

- **Django Documentation**: https://docs.djangoproject.com/
- **Flask Documentation**: https://flask.palletsprojects.com/
- **GigaChat API**: https://developers.sber.ru/portal/products/gigachat
- **OpenAI API**: https://platform.openai.com/docs
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **APScheduler**: https://apscheduler.readthedocs.io/

---

## ❓ FAQ

### Общие вопросы

**Q: Нужно ли регистрироваться для использования?**  
A: Нет! Получите токен через Telegram Bot или используйте developer token для тестирования.

**Q: Сколько стоит использование?**  
A: Бесплатный старт - 0₽ (30K GigaChat + 30K OpenAI, бессрочно). Платные тарифы: Базовый 590₽/мес, Про 1190₽/мес, Безлимит 2490₽/мес.

**Q: Какие AI модели используются?**  
A: GigaChat (Сбер) для российских пользователей, OpenAI GPT-4o-mini + DALL-E 3 для международных.

**Q: Безопасны ли мои данные?**  
A: Да! Полное соблюдение 152-ФЗ, данные хранятся на территории РФ, шифрование передачи.

### Технические вопросы

**Q: Нужно ли настраивать cron для автоматизации?**  
A: Нет! APScheduler работает автоматически при запуске Django.

**Q: Можно ли использовать только Django без Flask?**  
A: Да! Flask опционален. Django может работать только с GigaChat.

**Q: Работает ли на Windows?**  
A: Да! Проект полностью кроссплатформенный.

**Q: Как обновить зависимости?**  
A: `pip install -r requirements.txt --upgrade`

### Разработка

**Q: Как добавить новый тип токена?**  
A: Отредактируйте `TOKEN_TYPES` в `generator/models.py` и создайте миграцию.

**Q: Как изменить расписание автоочистки?**  
A: Отредактируйте `CronTrigger` в `generator/scheduler.py`.

**Q: Как добавить новую платформу для генерации?**  
A: Добавьте выбор в форму `GenerationForm` и обработку в `views.py`.

**Q: Где логи планировщика?**  
A: В консоли runserver или логах gunicorn. Настраиваются через Django logging.

### Проблемы

**Q: Бот не создает токены**  
A: Проверьте что Django запущен и `DJANGO_API_URL` в `.env` правильный.

**Q: "DatabaseWrapper objects created in a thread"**  
A: Используйте `ghostwriter.test_settings` для тестов.

**Q: Токены не деактивируются автоматически**  
A: Проверьте что планировщик запустился (смотрите логи при старте).

**Q: Ошибки с langchain-core версией**  
A: Переустановите: `pip install "langchain-core>=0.3,<0.4" --force-reinstall`

---

## 📝 Changelog

### Version 2.2 - Anti-Multiaccount Edition (25.01.2026)

#### Новое
- ✅ **Защита от мультиаккаунтов**: Один пользователь = один активный DEMO токен
- ✅ **Обновленные тарифы**: Новые лимиты токенов и цены
- ✅ **Разделение генерации**: Чекбокс и кнопка для генерации изображений
- ✅ **Юридические документы**: Оферта, политика конфиденциальности, отказ от ответственности
- ✅ **GPT-4o-mini**: Обновлена модель OpenAI в Flask генераторе
- ✅ **Деплой HTTPS на 443**: `docker-compose.production.yml`, самоподписанный SSL по IP; [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

#### Улучшения
- ✅ Переработан Telegram Bot с юридическими документами
- ✅ Обновлены Docker файлы для версии 2.2
- ✅ Добавлено поле telegram_user_id в токены для защиты
- ✅ Улучшена обработка ошибок в боте

### Version 2.0 - Automatic Edition (11.01.2026)

#### Новое
- ✅ **Автоматизация**: APScheduler вместо cron
- ✅ **Telegram Bot**: Реальная интеграция через API
- ✅ **Token API**: REST endpoints для создания токенов
- ✅ **Developer Token**: Бессрочные токены для разработки
- ✅ **Middleware**: Автоматическая деактивация истекших токенов

### Version 1.0 (Предыдущая версия)
- Базовая функциональность Django + Flask
- Регистрация и авторизация
- Генерация контента через GigaChat/OpenAI
- Docker deployment

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Как внести вклад

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

### Рекомендации

- Следуйте PEP 8 стилю кода
- Добавляйте тесты для новой функциональности
- Обновляйте документацию
- Используйте понятные commit сообщения

---

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

---

## 👤 Автор

**Artem Lavrov**

- GitHub: [@Crowley55555](https://github.com/Crowley55555)
- Telegram: [@rain511](https://t.me/rain511)

---

## 🙏 Благодарности

- [Django](https://www.djangoproject.com/) - Web framework
- [Flask](https://flask.palletsprojects.com/) - Microservice framework
- [GigaChat](https://developers.sber.ru/portal/products/gigachat) - Russian AI
- [OpenAI](https://openai.com/) - GPT & DALL-E
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram Bot library
- [APScheduler](https://apscheduler.readthedocs.io/) - Task scheduling
- Community - За поддержку и обратную связь

---

## 📞 Поддержка

Если у вас возникли вопросы или проблемы:

1. Проверьте [FAQ](#-faq)
2. Посмотрите [Issues](https://github.com/yourusername/Ghostwriter/issues)
3. Создайте новый Issue с описанием проблемы
4. Свяжитесь с автором

---

<div align="center">

**⭐ Star этот репозиторий если он был полезен! ⭐**

**Создано с ❤️ для генерации качественного контента**

[![GitHub stars](https://img.shields.io/github/stars/yourusername/Ghostwriter?style=social)](https://github.com/yourusername/Ghostwriter/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/yourusername/Ghostwriter?style=social)](https://github.com/yourusername/Ghostwriter/network/members)

</div>
