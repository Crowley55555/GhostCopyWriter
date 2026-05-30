# 👨‍💻 Developer Guide - Ghostwriter

Руководство для разработчиков проекта Ghostwriter.

---

## 📋 Содержание

- [Quick Start для разработчиков](#-quick-start-для-разработчиков)
- [Вход в систему](#-вход-в-систему)
- [Django Admin Panel](#-django-admin-panel)
- [Разработка](#-разработка)
- [Тестирование](#-тестирование)
- [База данных](#-база-данных)
- [API Endpoints](#-api-endpoints)
- [Отладка](#-отладка)
- [Полезные команды](#-полезные-команды)

---

## 🚀 Quick Start для разработчиков

### 1. Клонирование и настройка

```bash
# Клонирование
git clone https://github.com/yourusername/Ghostwriter.git
cd Ghostwriter

# Виртуальное окружение
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Установка зависимостей
pip install -r requirements.txt

# Переменные окружения
cp env.example .env
# Отредактируйте .env
```

### 2. Инициализация базы данных

```bash
# Миграции
python manage.py migrate

# Создание superuser для админки
python manage.py createsuperuser
# Username: admin
# Email: admin@example.com
# Password: (ваш пароль)
```

### 3. Создание developer токена

```bash
# Создать бессрочный токен разработчика
python manage.py create_dev_token --name="Ваше Имя"
```

**Результат:**
```
======================================================================
>> DEVELOPER token uspeshno sozdan!
======================================================================
Razrabotchik: Ваше Имя
Token: fef1edac-d4eb-4edc-b718-6b8b3f07527a
Tip: Bessrochniy (bezlimit)
Sozdan: 11.01.2026 19:24:27
Istekaet: 18.12.2125 (bessrochniy)
======================================================================
>> VASHA SSYLKA DOSTUPA:
======================================================================
http://localhost:8000/auth/token/fef1edac-d4eb-4edc-b718-6b8b3f07527a/
======================================================================
```

Токен сохраняется в файл `.dev_token` для удобства.

### 4. Запуск сервера

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

---

## 🔑 Вход в систему

### Способ 1: Developer Token (рекомендуется)

**Ваш токен:**
```
Файл: .dev_token
Ссылка: http://localhost:8000/auth/token/<your-token>/
```

**Как использовать:**

1. Откройте файл `.dev_token`
2. Скопируйте строку `LOCAL_URL`
3. Откройте в браузере
4. Вы автоматически авторизованы!

**Преимущества:**
- ✅ Бессрочный (не истекает)
- ✅ Безлимитные генерации
- ✅ Работает как постоянный логин
- ✅ Можно добавить в закладки

**Добавление в закладки:**
```
1. Откройте ссылку из .dev_token
2. Ctrl+D (Add to bookmarks)
3. Переименуйте: "Ghostwriter Dev"
4. Теперь просто кликайте на закладку для входа
```

---

### Способ 2: Quick Login (DEBUG режим)

Доступен только при `DEBUG=True` в настройках.

**URL:**
```
http://localhost:8000/quick-login/<username>/
```

**Примеры:**
```bash
# Войти как admin
http://localhost:8000/quick-login/admin/

# Войти как test_user_1
http://localhost:8000/quick-login/test_user_1/

# Войти как test_user_2
http://localhost:8000/quick-login/test_user_2/
```

**Что происходит:**
- Автоматически создается пользователь если его нет
- Пароль: `testpassword`
- Автоматическая авторизация
- Редирект на `/generator/`

**Важно:** Этот метод недоступен в production (`DEBUG=False`)!

---

### Способ 3: Django Admin

**URL:**
```
http://localhost:8000/admin/
```

**Учетные данные:**
- Username: (созданный через `createsuperuser`)
- Password: (ваш пароль)

---

### Способ 4: Telegram Bot (как обычный пользователь)

Для тестирования пользовательского опыта:

```bash
# Запустите бота
python bot.py

# В Telegram:
1. /start
2. Нажмите "🆓 Демо 5 дней"
3. Получите DEMO токен
4. Откройте ссылку
```

---

## 🎛️ Django Admin Panel

### Доступ к админке

**URL:** `http://localhost:8000/admin/`

**Учетные данные:** superuser созданный через `createsuperuser`

---

### Доступные разделы

#### 1. **Authentication and Authorization**
- **Users** - пользователи Django (legacy, не используется)
- **Groups** - группы пользователей (legacy)

#### 2. **Generator**
- **Generations** - все созданные генерации контента
- **Generation templates** - шаблоны настроек пользователей
- **Temporary access tokens** - все токены доступа
- **User profiles** - профили пользователей (legacy)

---

### Управление токенами

#### Просмотр токенов

Перейдите: **Generator → Temporary access tokens**

**Что видно:**
- UUID токена
- Тип (DEMO, MONTHLY, YEARLY, DEVELOPER)
- Дата создания
- Дата истечения
- Активен / Неактивен
- Счетчик использований
- Последний IP
- Дневной лимит генераций

#### Создание токена вручную

**В админке:**
1. Generator → Temporary access tokens → Add
2. Заполните:
   - Token type: выберите тип
   - Expires at: дата истечения
   - Daily generations left: лимит (или -1 для безлимита)
   - Is active: ✓
3. Save

**Через shell:**
```python
python manage.py shell

from generator.models import TemporaryAccessToken
from django.utils import timezone
from datetime import timedelta

# Создать DEMO токен
token = TemporaryAccessToken.objects.create(
    token_type='DEMO',
    expires_at=timezone.now() + timedelta(days=5),
    daily_generations_left=5,
    generations_reset_date=timezone.now().date(),
    is_active=True
)

print(f"Token: {token.token}")
print(f"URL: http://localhost:8000/auth/token/{token.token}/")
```

#### Деактивация токена

**В админке:**
1. Найдите токен
2. Снимите галочку "Is active"
3. Save

**Через shell:**
```python
from generator.models import TemporaryAccessToken

token = TemporaryAccessToken.objects.get(token='uuid-here')
token.is_active = False
token.save()
```

#### Удаление токена

**В админке:**
1. Выберите токен(ы)
2. Action: Delete selected
3. Confirm

**Через shell:**
```python
# Удалить конкретный токен
token = TemporaryAccessToken.objects.get(token='uuid-here')
token.delete()

# Удалить все истекшие
from django.utils import timezone
TemporaryAccessToken.objects.filter(expires_at__lt=timezone.now()).delete()
```

---

### Просмотр генераций

Перейдите: **Generator → Generations**

**Фильтры:**
- По пользователю
- По дате создания
- По платформе
- С изображением / без

**Полезные действия:**
- Просмотр деталей генерации
- Копирование текста
- Скачивание изображения
- Удаление старых генераций

---

### Статистика

**Полезные запросы в Django Shell:**

```python
python manage.py shell

from generator.models import TemporaryAccessToken, Generation
from django.db.models import Count, Sum
from django.utils import timezone

# Статистика токенов
print(f"Всего токенов: {TemporaryAccessToken.objects.count()}")
print(f"Активных: {TemporaryAccessToken.objects.filter(is_active=True).count()}")

# Токены по типам
stats = TemporaryAccessToken.objects.values('token_type').annotate(count=Count('id'))
for s in stats:
    print(f"{s['token_type']}: {s['count']}")

# Статистика генераций
print(f"Всего генераций: {Generation.objects.count()}")
print(f"За последние 24 часа: {Generation.objects.filter(created_at__gte=timezone.now()-timedelta(hours=24)).count()}")

# Топ платформы
platforms = Generation.objects.values('platform').annotate(count=Count('id')).order_by('-count')
for p in platforms[:5]:
    print(f"{p['platform']}: {p['count']}")
```

---

## 🛠️ Разработка

### Структура проекта

```
Ghostwriter/
├── generator/              # Основное Django приложение
│   ├── models.py          # Модели (Generation, Token, etc.)
│   ├── views.py           # Views и API endpoints
│   ├── urls.py            # URL маршруты
│   ├── forms.py           # Django формы
│   ├── middleware.py      # TokenAccessMiddleware
│   ├── decorators.py      # @token_required, @consume_generation
│   ├── scheduler.py       # APScheduler задачи
│   ├── admin.py           # Django admin настройки
│   ├── apps.py            # AppConfig (запуск scheduler)
│   ├── gigachat_api.py    # GigaChat интеграция
│   ├── fastapi_client.py  # Flask микросервис клиент
│   ├── templates/         # HTML шаблоны
│   ├── static/            # CSS, JS
│   └── management/        # Management команды
│       └── commands/
│           ├── cleanup_tokens.py
│           └── create_dev_token.py
│
├── ghostwriter/           # Django настройки
│   ├── settings.py        # Основные настройки
│   ├── test_settings.py   # Настройки для тестов
│   ├── urls.py            # Главный URL конфиг
│   └── wsgi.py            # WSGI точка входа
│
├── tests/                 # Тестирование
│   ├── test_django_models.py
│   ├── test_django_isolated.py
│   └── test_flask_app.py
│
├── flask_generator/       # Flask микросервис (опционально)
│   ├── app.py             # Flask приложение
│   ├── text_gen.py        # Генерация текста
│   └── image_gen.py       # Генерация изображений
│
├── bot.py                 # Telegram Bot
├── manage.py              # Django management
├── requirements.txt       # Python зависимости
└── .env                   # Переменные окружения
```

---

### Создание новой функции

#### 1. Добавить модель (если нужно)

```python
# generator/models.py

class NewFeature(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
```

```bash
# Создать миграцию
python manage.py makemigrations

# Применить
python manage.py migrate
```

#### 2. Создать view

```python
# generator/views.py

@token_required
def new_feature_view(request):
    """Новая функция"""
    # Ваш код
    return render(request, 'generator/new_feature.html')
```

#### 3. Добавить URL

```python
# generator/urls.py или ghostwriter/urls.py

urlpatterns = [
    # ...
    path('new-feature/', views.new_feature_view, name='new_feature'),
]
```

#### 4. Создать шаблон

```html
<!-- generator/templates/generator/new_feature.html -->
{% extends 'generator/base.html' %}

{% block content %}
<h1>New Feature</h1>
<!-- Ваш HTML -->
{% endblock %}
```

#### 5. Добавить в админку (если нужно)

```python
# generator/admin.py

from .models import NewFeature

@admin.register(NewFeature)
class NewFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
```

---

### Работа с токенами в коде

#### Получить текущий токен пользователя

```python
# В view
def my_view(request):
    token_uuid = request.session.get('access_token')
    token_type = request.session.get('token_type')
    is_demo = request.session.get('is_demo')
    daily_left = request.session.get('daily_generations_left')
    
    # Получить объект токена
    if token_uuid:
        token = TemporaryAccessToken.objects.get(token=token_uuid)
```

#### Проверить доступ в view

```python
from generator.decorators import token_required, consume_generation

@token_required
def protected_view(request):
    """Требует активный токен"""
    pass

@token_required
@consume_generation
def generation_view(request):
    """Требует токен + уменьшает счетчик для DEMO"""
    pass
```

#### Создать токен программно

```python
from generator.models import TemporaryAccessToken
from django.utils import timezone
from datetime import timedelta

# DEMO токен
demo_token = TemporaryAccessToken.objects.create(
    token_type='DEMO',
    expires_at=timezone.now() + timedelta(days=5),
    daily_generations_left=5,
    generations_reset_date=timezone.now().date()
)

# DEVELOPER токен (бессрочный)
from datetime import datetime
dev_token = TemporaryAccessToken.objects.create(
    token_type='DEVELOPER',
    expires_at=datetime(2125, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    daily_generations_left=-1,  # Безлимит
)

print(f"URL: http://localhost:8000/auth/token/{dev_token.token}/")
```

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
python run_tests.py

# Только Django тесты
python manage.py test --settings=ghostwriter.test_settings

# Конкретный тест
python manage.py test tests.test_django_models.UserProfileModelTest --settings=ghostwriter.test_settings

# С verbose
python manage.py test --settings=ghostwriter.test_settings -v 2
```

### Создание тестового токена

```python
# tests/test_my_feature.py

from django.test import TestCase
from generator.models import TemporaryAccessToken
from django.utils import timezone
from datetime import timedelta

class MyFeatureTest(TestCase):
    def setUp(self):
        # Создать тестовый токен
        self.token = TemporaryAccessToken.objects.create(
            token_type='DEVELOPER',
            expires_at=timezone.now() + timedelta(days=365),
            daily_generations_left=-1,
            is_active=True
        )
        
        # Авторизоваться через токен
        self.client.get(f'/auth/token/{self.token.token}/')
    
    def test_my_feature(self):
        response = self.client.get('/my-feature/')
        self.assertEqual(response.status_code, 200)
```

---

## 💾 База данных

### SQLite (Development)

**Расположение:** `db.sqlite3` в корне проекта

**Просмотр:**
```bash
# DB Browser for SQLite
# https://sqlitebrowser.org/

# Или через командную строку
sqlite3 db.sqlite3
.tables
.schema generator_temporaryaccesstoken
SELECT * FROM generator_temporaryaccesstoken LIMIT 10;
.quit
```

### Django Shell

```bash
python manage.py shell
```

**Полезные запросы:**

```python
from generator.models import *
from django.contrib.auth.models import User
from django.utils import timezone

# Все токены
tokens = TemporaryAccessToken.objects.all()

# Активные токены
active = TemporaryAccessToken.objects.filter(is_active=True)

# Developer токены
devs = TemporaryAccessToken.objects.filter(token_type='DEVELOPER')

# Истекшие токены
expired = TemporaryAccessToken.objects.filter(expires_at__lt=timezone.now())

# Последние генерации
gens = Generation.objects.order_by('-created_at')[:10]

# Статистика
from django.db.models import Count
stats = TemporaryAccessToken.objects.values('token_type').annotate(count=Count('id'))
```

### Сброс базы данных

```bash
# Удалить базу
rm db.sqlite3

# Удалить миграции (опционально)
rm generator/migrations/0*.py

# Создать заново
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py create_dev_token
```

---

## 🔌 API Endpoints

### Token API

#### POST /api/tokens/create/
Создать новый токен

```bash
curl -X POST http://localhost:8000/api/tokens/create/ \
  -H "Content-Type: application/json" \
  -d '{
    "token_type": "DEMO",
    "expires_days": 5,
    "daily_limit": 5
  }'
```

**Response:**
```json
{
  "token": "uuid",
  "token_type": "DEMO",
  "expires_at": "2026-01-20T12:00:00Z",
  "daily_limit": 5,
  "url": "http://localhost:8000/auth/token/uuid/",
  "created_at": "2026-01-15T12:00:00Z",
  "is_active": true
}
```

#### GET /api/tokens/<uuid>/
Получить информацию о токене

```bash
curl http://localhost:8000/api/tokens/fef1edac-d4eb-4edc-b718-6b8b3f07527a/
```

**Response:**
```json
{
  "token": "fef1edac-d4eb-4edc-b718-6b8b3f07527a",
  "token_type": "DEVELOPER",
  "is_active": true,
  "expires_at": "2125-12-18T23:59:59Z",
  "daily_generations_left": -1,
  "total_used": 0,
  "is_expired": false
}
```

---

## 🐛 Отладка

### Django Debug Toolbar (рекомендуется)

```bash
# Установить
pip install django-debug-toolbar

# Добавить в settings.py (уже добавлено если DEBUG=True)
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

**Доступно:** Боковая панель на всех страницах при `DEBUG=True`

### Логирование

```python
# В любом файле
import logging
logger = logging.getLogger(__name__)

def my_view(request):
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
```

**Настройка в settings.py:**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
```

### Print debugging

```python
def my_view(request):
    print("=" * 50)
    print(f"Request: {request.method} {request.path}")
    print(f"Token: {request.session.get('access_token')}")
    print("=" * 50)
```

### IPython

```bash
pip install ipython

# В коде
import IPython; IPython.embed()
```

### Проверка планировщика

```python
from generator.scheduler import get_scheduler_status

status = get_scheduler_status()
print(f"Running: {status['running']}")
for job in status['jobs']:
    print(f"- {job['name']}: {job['next_run']}")
```

---

## ⚙️ Полезные команды

### Django Management

```bash
# Создать миграции
python manage.py makemigrations

# Применить миграции
python manage.py migrate

# Откатить миграцию
python manage.py migrate generator 0001

# Проверить проект
python manage.py check

# Собрать статику
python manage.py collectstatic

# Создать superuser
python manage.py createsuperuser

# Shell
python manage.py shell

# Shell Plus (если установлен django-extensions)
python manage.py shell_plus
```

### Кастомные команды

```bash
# Создать developer токен
python manage.py create_dev_token --name="Ваше Имя"

# Очистить просроченные токены
python manage.py cleanup_tokens

# Dry-run (без изменений)
python manage.py cleanup_tokens --dry-run

# Удалить старые токены
python manage.py cleanup_tokens --delete --days=90
```

### Git

```bash
# Статус
git status

# Коммит
git add .
git commit -m "Описание изменений"

# Push
git push origin main

# Pull
git pull origin main

# Новая ветка
git checkout -b feature/new-feature
```

### Виртуальное окружение

```bash
# Создать
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Активировать (Linux/macOS)
source venv/bin/activate

# Деактивировать
deactivate

# Сохранить зависимости
pip freeze > requirements.txt

# Установить зависимости
pip install -r requirements.txt
```

---

## 🔐 Безопасность при разработке

### .env файл

**Никогда не коммитьте:**
- `.env` файл
- `.dev_token` файл
- `db.sqlite3`
- API ключи
- Пароли

**Проверьте .gitignore:**
```bash
cat .gitignore | grep -E "\.env|\.dev_token|db\.sqlite3"
```

### Секретные ключи

```python
# Генерация Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Генерация webhook secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Генерация API key
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🌐 Production (сервер, Docker)

Локальная разработка — `http://localhost:8000`. На сервере — **HTTPS :443** через Docker Nginx.

| Документ | Содержание |
|----------|------------|
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Полный деплой |
| [DEPLOY_UPDATE.md](DEPLOY_UPDATE.md) | `git pull` и обновление |
| [ssl/README.md](ssl/README.md) | SSL-сертификаты |

**SSL перед первым запуском:**

```bash
bash deploy/generate-ssl-ip.sh 85.208.86.148
docker compose -f docker-compose.production.yml up -d --build
curl -Ik https://85.208.86.148/
```

**Ручная выдача токенов на сервере:** [MANUAL_TOKEN_GENERATOR.md](MANUAL_TOKEN_GENERATOR.md)

```bash
docker compose -f docker-compose.production.yml exec django \
  python manual_token_generator.py --quick DEMO_FREE
```

В `.env` на сервере: `SITE_URL=https://85.208.86.148`, `USE_HTTPS=true`, `SECURE_HSTS_SECONDS=0`.

---

## 📚 Дополнительные ресурсы

### Документация

- **Django:** https://docs.djangoproject.com/
- **Deployment:** [README.md — Deployment](README.md#-deployment)
- **APScheduler:** https://apscheduler.readthedocs.io/
- **GigaChat:** https://developers.sber.ru/portal/products/gigachat
- **Telegram Bot:** https://core.telegram.org/bots/api

### Полезные инструменты

- **DB Browser for SQLite:** https://sqlitebrowser.org/
- **Postman:** Тестирование API
- **Django Debug Toolbar:** Профилирование
- **ipdb:** Отладчик Python

---

## 🆘 Помощь

### Частые проблемы

**Проблема:** Не могу войти через токен
```bash
# Проверьте что токен активен
python manage.py shell
from generator.models import TemporaryAccessToken
token = TemporaryAccessToken.objects.get(token='your-uuid')
print(f"Active: {token.is_active}, Expired: {token.is_expired()}")
```

**Проблема:** Миграции не применяются
```bash
python manage.py showmigrations
python manage.py migrate --fake-initial
```

**Проблема:** Планировщик не запускается
```bash
# Проверьте логи при старте
python manage.py runserver --verbosity=2
```

---

## 📝 Чеклист для разработчика

### Первый запуск

- [ ] Клонирован репозиторий
- [ ] Создано виртуальное окружение
- [ ] Установлены зависимости
- [ ] Создан .env файл
- [ ] Применены миграции
- [ ] Создан superuser
- [ ] Создан developer токен
- [ ] Запущен сервер
- [ ] Протестирован вход через токен
- [ ] Доступна админка

### Ежедневная разработка

- [ ] Активировано виртуальное окружение
- [ ] Обновлены зависимости (если нужно)
- [ ] Pull последних изменений
- [ ] Применены новые миграции
- [ ] Запущен сервер
- [ ] Открыт токен для входа

---

**Обновлено:** май 2026  
**Версия:** 2.2+ (Developer Guide)  
**Автор:** Ghostwriter Team
