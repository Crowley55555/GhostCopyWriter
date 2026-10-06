<!-- starter:begin sha256=97e4c51b4e3f5ae500a4a47ee84a121237ee345256f0786d3dbcbb2d7c00f694 -->
# Claude Code: вход в проект

Прочитай общий процесс в `.starter/workflow.md` относительно корня проекта. Используй существующий бизнес-индекс, архитектуру, действующий план и checkpoint. Не заводи дубликаты и не запускай интервью, если контекст уже есть.

Это образец для нового корневого файла, не разрешение перезаписывать существующий. Установщик сам добавляет управляемую ссылку к локальным инструкциям. В клоне starter канонический процесс лежит в `docs/workflow.md`.
<!-- starter:end -->

# Ghostwriter

SaaS для генерации постов в соцсети (VK, Дзен, Telegram и др.) с картинками через GigaChat и OpenAI. Анонимный доступ по токенам из Telegram-бота, бесплатный старт и платные подписки (ЮKassa).

## Стек и структура

- Django — основное приложение (`ghostwriter/` настройки, `generator/` логика, тарифы `generator/tariffs.py`).
- Flask — сервис генерации (`flask_generator/`); Telegram-бот — `bot.py`.
- PostgreSQL, Redis, Docker (`docker-compose*.yml`), nginx.
- Документация: `README.md`, `DEV.md` (локальная разработка, тесты), `DEPLOYMENT_GUIDE.md`.

## Команды (из `DEV.md`, перепроверить при аудите)

- Локально: `python manage.py runserver`; бот: `python bot.py`.
- Тесты (PowerShell): `$env:DJANGO_SETTINGS_MODULE="ghostwriter.test_settings"; python manage.py test tests.test_django_models tests.test_django_isolated`
- Docker: `docker compose up` без `-f` поднимает dev-стек; production — только с `-f docker-compose.production.yml` и только по решению владельца.

## Правила проекта

- Планы — `plans/`, ретро — `retrospectives/`.
- `FINANCIAL_MODEL.md` устарел (2024): тарифы и прогнозы там не совпадают с кодом — не использовать как источник фактов.

## Безопасность (репозиторий публичный)

- В коммиты — никаких секретов, токенов, ПДн, бизнес-цифр и приватного контекста владельца.
- `.env`, `.dev_token`, ключи в `ssl/` не читать и не выводить; проверять только имена переменных.
- Deploy, production, платежи, миграции на проде — только по явному решению владельца.
