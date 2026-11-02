# Ghostwriter — SaaS-генератор постов для соцсетей

Веб-кабинет и Telegram-бот, которые генерируют тексты и изображения для соцсетей (VK, Telegram, Дзен и других площадок) через GigaChat и OpenAI.

## Задача

Автору и небольшому агентству нужно быстро получать готовые посты под разные площадки — с подбором картинки, тоном под аудиторию и без ручной работы в нескольких окнах. При этом доступ нужно давать без регистрации и сбора персональных данных.

## Решение

- Генерация текстов постов под разные соцсети с выбором тона, цели и формата.
- Генерация изображений к посту отдельной кнопкой (экономия токенов).
- Два AI-провайдера: GigaChat (российский контур) и OpenAI GPT-4o-mini + DALL·E (вынесен в отдельный Flask-микросервис).
- Доступ по временным токенам-ссылкам — без email и телефона, пользователь получает ссылку в Telegram-боте.
- История генераций, шаблоны настроек, стена пользователя.
- Встроенный планировщик APScheduler деактивирует истекшие токены и автоматически продлевает подписки по расписанию — без внешнего cron.

## Как устроено

- **Django-приложение** (`generator/`, `ghostwriter/`) — веб-кабинет, модели пользователей и токенов, история генераций, API для бота. Запускается через `manage.py`.
- **Flask-микросервис** (`flask_generator/`) — вынесенная генерация через OpenAI/DALL·E. Общается с Django по зашифрованному каналу (Fernet, модуль `flask_generator/crypto_utils.py`).
- **Telegram-бот** (`bot.py`, python-telegram-bot) — выдаёт пользователю токен-ссылку доступа, вызывая Django API.
- **GigaChat-клиент** (`generator/gigachat_api.py`) — интеграция с российским AI напрямую из Django.
- **Планировщик** (`generator/scheduler.py`) — APScheduler, задачи по расписанию (деактивация истекших токенов, автопополнение подписок по `next_renewal`, чистка старых записей).
- **Инфраструктура** — `Dockerfile`, `docker-compose.yml` (локальная разработка), `docker-compose.production.yml` (prod с nginx и HTTPS), `nginx.prod.conf`, Redis и PostgreSQL в compose.

## Стек

Python 3.9+, Django 4.2+, Flask 2.3+, python-telegram-bot 20.7, langchain-gigachat, OpenAI SDK, APScheduler, PostgreSQL, Redis, Docker, nginx, pytest.

## Результат

- **33 тестовые функции** в `tests/` (`test_django_models.py` — 10, `test_django_isolated.py` — 11, `test_flask_app.py` — 12). Подсчёт: `grep -r "def test_" tests/ | wc -l`.
- Разделение контуров: ПДн и токены — на стороне Django, зарубежный AI — в отдельном Flask-сервисе; связь шифруется.
- Планировщик встроен в приложение — не нужен отдельный cron или Task Scheduler.

## Запуск

Через Docker Compose (локально):

```bash
cp env.example .env
# заполнить .env (GIGACHAT_CREDENTIALS, TELEGRAM_BOT_TOKEN, DJANGO_SECRET_KEY и т.п.)
docker compose up -d
docker compose exec django python manage.py migrate
docker compose exec django python manage.py createsuperuser
```

Сайт — `http://localhost:8000`.

Без Docker:

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env   # заполнить переменные окружения
python manage.py migrate
python manage.py runserver
# в отдельном терминале, если нужен бот:
python bot.py
```

Flask-микросервис запускается отдельно в `flask_generator/` (`python app.py` или через `docker-compose.flask.yml`) и используется опционально — Django может работать только с GigaChat.

## Автор

Артём Лавров — Python-разработчик, AI-боты и автоматизация для бизнеса.

- Telegram: [@rain511](https://t.me/rain511)
- GitHub: [Crowley55555](https://github.com/Crowley55555)
