# Фаза 1: «Попробовать» и защита генерации — промпт исполнителя

Ты — исполнитель фазы 1 плана `plans/2026-10-06-zapusk-demo.md`. Работаешь в отдельной сессии. Ревью проведёт оркестратор — другая сессия, поэтому своих рецензентов и агентов не запускай. Коммиты делает оркестратор после ревью.

## Сначала прочитай

1. `CLAUDE.md` в корне — правила проекта и безопасности.
2. `plans/2026-10-06-zapusk-demo.md`:
   - разделы «Порядок исполнения», «Границы и полномочия», «Фаза 1»;
   - таблицу «Ревью версии 1» (п. 1–6, 11);
   - «Checkpoint», особенно запись о фазе 0.
3. `.starter/workflow.md`, раздел 4 — цикл фазы: сначала падающий тест, потом код.

Файлы `.env`, `.dev_token` и содержимое `ssl/` не читай и не выводи. Папка `idea/` не нужна.

## Цель фазы

Посетитель без Telegram-бота нажимает «Попробовать» на лендинге, получает демо-доступ и генерирует пост. Ни один путь к GigaChat не работает без действующего токена и лимитов. Лимиты нельзя обойти подменой заголовков, очисткой cookies или прямыми запросами к API.

## Факты о коде (проверено оркестратором 2026-10-06, после коммита фазы 0 `5fd0a03`)

- **Маршруты.**
  - Корневые — `ghostwriter/urls.py`.
  - Под `/api/` — `generator/urls.py`, подключены через `path('api/', include('generator.urls'))`. Префикс `/api/` исключён из `TokenAccessMiddleware` (`generator/middleware.py`, список `exempt_urls`).
- **Фронтенд** (`generator/templates/generator/gigagenerator.html`):
  - перегенерация вызывается через **корневые** `/regenerate-text/` и `/regenerate-image/`;
  - шаблоны — через `/api/save-template/`, `/api/get-templates/`, `/api/load-template/`, `/api/delete-template/`, `/api/rename-template/`, `/api/set-default-template/`;
  - ответы читаются как JSON, ошибка показывается из `data.error`.
- **Вызовы GigaChat** (`generator/gigachat_api.py`: `generate_text`, `generate_image_prompt_from_text`, `generate_image_gigachat`) идут из четырёх view в `generator/views.py`:
  - `generator_view` — `@consume_generation`;
  - `regenerate_text` — `@csrf_exempt`, лимиты не проверяет;
  - `generate_image_from_text` — `@csrf_exempt`, `@token_required`, лимиты не проверяет;
  - `regenerate_image` — `@csrf_exempt`, лимиты не проверяет.
- **Учёт.** Каждая операция пишет строку `GigaChatTokenUsage` через `log_token_usage` — после вызова (`gigachat_api.py:415-457`, вызовы около строк 568, 651, 737, 766). Списание с токена (`consume_gigachat_tokens`) тоже идёт после вызова.
- **Проверка лимита.** `consume_generation` (`generator/decorators.py`) отправляет на страницу лимита только при `not can_gc and not can_oa`. У `DEMO_FREE` в `generator/tariffs.py` `openai_tokens: 30_000`, токен бессрочный, поэтому при исчерпанном GigaChat проверка не срабатывает.
- **IP.** `get_client_ip` (`generator/decorators.py`) берёт первый элемент `X-Forwarded-For`, а его подделывает клиент. Nginx в проде выставляет `X-Real-IP $remote_addr` (`nginx.prod.conf`).
- **Сессия по токену.** `token_auth_view` (`generator/views.py`, около строк 1060–1150) выставляет в сессию `access_token`, `token_type`, `is_demo`, лимиты и срок. Для токена с `telegram_user_id` он создаёт пользователя Django и выполняет вход.
- **Ссылки на бота.** `landing.html` ведёт на `https://t.me/Ghostcopywriterregistration_bot` (две кнопки, около строк 351 и 370); `token_required.html` — тоже (около строки 62).
- **Кто зависит от снимаемых маршрутов.**
  - `manual_token_generator.py` создаёт токены через ORM, а не через API.
  - Ни один шаблон не ссылается по имени на снимаемые маршруты (`{% url %}`). Проверь ещё раз после правок.
  - `bot.py` перестанет работать — это ожидаемо, бот вне объёма.
- **Тесты** из фазы 0: `tests/helpers.py` (`TokenAuthMixin.login_by_token`), `tests/runner.py` (предохранитель: GigaChat и сеть без мока бросают `NetworkAccessBlocked`). В `test_settings` кэш — `DummyCache`.

## Что сделать (сначала падающие тесты, потом код)

Новые тесты положи в новый модуль, например `tests/test_demo_access.py`. Добавь его в команду тестов в плане (раздел «Фазы всего результата»).

1. **Снять маршруты.** Из URLconf убрать (код view остаётся в файлах):
   - `tokens/create/`, `tokens/<uuid>/`;
   - `track-subscription-click/`;
   - `payments/create/`, `payments/yookassa/webhook/`, `payments/<id>/confirm/`;
   - `support/create/`, `reviews/create/`, `support/stats/`;
   - дубли `regenerate-text/` и `regenerate-image/` под `/api/`;
   - корневой `telegram/webhook/`.

   Маршруты шаблонов под `/api/` не трогай — их переделает фаза 3.
2. **Общая функция сессии.** Вынеси из `token_auth_view` код, который выставляет сессию по токену, в одну функцию, например `start_token_session(request, token)` в новом модуле `generator/access.py`. `token_auth_view` должен вызывать её же. Поведение `token_auth_view` не меняется.
3. **Реальный IP.** Одна функция определения IP клиента:
   - при включённой настройке «за прокси» (`BEHIND_PROXY`, из env) — `X-Real-IP`;
   - иначе — `REMOTE_ADDR`;
   - `X-Forwarded-For` не используется.

   Новые проверки используют её. Существующий `get_client_ip` переведи на неё или оставь только там, где он нужен для статистики, — решение запиши в checkpoint.
4. **POST «Попробовать».** Новый маршрут (например, `/try/`), только POST; GET → 405 или редирект на лендинг. Добавь путь в исключения `TokenAccessMiddleware`.
   - В сессии уже есть действующий токен (активный, не истёк) → редирект в генератор, новый токен не создаётся.
   - Иначе: если с этого IP за последние 24 часа выдано меньше N токенов (N из env, по умолчанию 3–5), создать `TemporaryAccessToken`:
     - тип `DEMO_FREE`, без `telegram_user_id`;
     - `openai_tokens_limit=0`;
     - `expires_at = сейчас + 24 часа`;
     - `gigachat_tokens_limit` из env.
   - Затем `start_token_session`, редирект в генератор.
   - Лимит N исчерпан → понятная страница или сообщение, не 500.
   - **Счётчик выдачи — в БД, без IP в открытом виде.** Новая модель (например, `AccessEvent`: тип события, HMAC-хэш IP с ключом из настроек, время) и миграция. Фаза 3 будет использовать её же для лимита регистраций. Записи старше суток удаляются — при записи или командой; способ запиши в checkpoint.
5. **Единая проверка перед каждым вызовом GigaChat.** Одна функция (в `generator/access.py`) вызывается в `generator_view`, `regenerate_text`, `generate_image_from_text`, `regenerate_image` до первого обращения к GigaChat. Она проверяет:
   - есть действующий токен (активен, не истёк);
   - остаток лимита GigaChat у токена (`can_use_gigachat`); с OpenAI-лимитом не смешивать;
   - общий дневной потолок: число строк `GigaChatTokenUsage` за последние 24 часа меньше значения из env;
   - длина пользовательского ввода, который уходит в промпт (`topic`, `result_text` и т. п.), не больше значений из env.

   При отказе GigaChat не вызывается. AJAX-запросы получают JSON `{"success": false, "error": "<понятный текст>"}` — фронтенд покажет `data.error`; код ответа выбери сам (например, 429 или 403) и запиши в checkpoint. Обычные запросы получают редирект на страницу лимита.
6. **CSRF.** Сними `@csrf_exempt` с `regenerate_text`, `generate_image_from_text`, `regenerate_image`. Фронтенд уже отправляет CSRF-токен — убедись в этом по `gigagenerator.html`.
7. **Кнопка «Попробовать»** — POST-форма с `{% csrf_token %}`:
   - на `landing.html` — вместо двух ссылок на бота;
   - на `token_required.html` — вместо ссылки на бота.

   Остальные тексты про бота, оплату и тарифы не трогай — это фазы 4 и 5.
8. **Настройки.** Новые значения (`BEHIND_PROXY`, N, лимит GigaChat демо-токена, дневной потолок, максимальная длина ввода) читаются из env с разумными значениями по умолчанию. Они должны быть доступны в `ghostwriter/settings.py`, `ghostwriter/production_settings.py` и `ghostwriter/test_settings.py`: продакшен-настройки не импортируют `settings.py`. Названия и значения по умолчанию запиши в checkpoint — фаза 6 внесёт их в `env.production.example`.

## Обязательные тесты

- Лендинг → POST «Попробовать» → редирект в генератор → POST генерации (AJAX) → `success: true`. `generate_text` замокан.
- Повторный POST «Попробовать» с живым токеном в сессии → новый токен не создан.
- С одного IP сверх N (новые клиенты без cookies) → новый токен не создаётся, ответ понятный.
- При `BEHIND_PROXY=True`: запросы с одним `X-Real-IP` и разными `X-Forwarded-For` считаются одним IP.
- `POST /api/tokens/create/` с `{"token_type": "DEVELOPER"}` → 404, токен не создан. `POST /api/payments/yookassa/webhook/` → 404. `/telegram/webhook/` → 404.
- Для каждого из четырёх эндпоинтов генерации мок GigaChat-функции **не вызывается**:
  - без токена в сессии;
  - с истёкшим токеном;
  - с исчерпанным лимитом GigaChat у токена;
  - при достигнутом дневном потолке;
  - при слишком длинном вводе.

  AJAX получает JSON с `error`.
- `Client(enforce_csrf_checks=True)`: POST без CSRF на «Попробовать» и на четыре эндпоинта генерации → 403.
- Демо-токен из «Попробовать» имеет `openai_tokens_limit=0`, срок 24 часа и лимит GigaChat из настроек.
- Старые тесты фазы 0 остаются зелёными.

## Ручная проверка

Запусти `python manage.py runserver` (настройки `ghostwriter.settings`, локальная база). Пройди сценарий в браузере или скриптом с сессией и CSRF: лендинг → «Попробовать» → генератор → 1–3 генерации через настоящий GigaChat.

- Не больше 3 генераций.
- Если ключ GigaChat недоступен или квота закончилась — запиши это в checkpoint и не обходи.
- Значения ключей не выводи.

Если твои модели требуют миграции, применяй её к локальной базе только через `migrate`. Старые данные не удаляй.

## Границы

- **Разрешено менять:** `generator/` (код, шаблоны `landing.html` и `token_required.html` — только кнопка, новая миграция), `ghostwriter/settings.py`, `ghostwriter/production_settings.py`, `ghostwriter/test_settings.py`, `ghostwriter/urls.py`, `tests/`, а в плане — раздел «Checkpoint» и команду тестов.
- **Запрещено:**
  - `git add`, `commit`, `push`;
  - `idea/`, `bot.py`, `nginx.prod.conf`, docker-файлы — это фаза 6;
  - тексты лендинга и других страниц сверх кнопки;
  - форма генерации и промпт — это фаза 2;
  - регистрация — это фаза 3.
- **Не меняй поведение** `token_auth_view`, кроме выноса общего кода.
- **Не ослабляй** существующие тесты.
- **Не больше 3 попыток** исправить одну и ту же проверку. Потом остановка и описание в отчёте и checkpoint.

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- PowerShell:
  `$env:DJANGO_SETTINGS_MODULE="ghostwriter.test_settings"; .venv\Scripts\python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access`
- Git Bash:
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access`
- Миграции:
  `.venv\Scripts\python.exe manage.py makemigrations generator --settings=ghostwriter.settings`
  Явно указывай `--settings=ghostwriter.settings`: в `test_settings` миграции отключены.

## Checkpoint и отчёт

Допиши в раздел «Checkpoint» плана одну запись, ничего не стирая:

- изменённые и созданные файлы;
- снятые маршруты;
- названия и значения по умолчанию новых настроек;
- код ответа при отказе;
- способ чистки счётчика;
- команда тестов и результат;
- ручная проверка: сколько генераций, результат;
- спорные решения.

Фазу `[x]` не отмечай.

В конце сессии выведи отчёт для оркестратора:

- изменённые и созданные файлы;
- итоговые строки вывода тестов;
- результат ручной проверки;
- спорные решения;
- что осталось или не получилось.
