# Фаза 1, исправления (раунд 1) — промпт исполнителя

Ты — исполнитель исправлений по ревью фазы 1 плана `plans/2026-10-06-zapusk-demo.md`. Работаешь в отдельной сессии. После тебя будет повторное ревью в отдельной сессии. Своих рецензентов и агентов не запускай. Коммиты делает оркестратор.

## Важно о рабочем дереве

Изменения фазы 1 **ещё не закоммичены** и лежат в рабочем дереве: `generator/access.py`, миграция `0019`, правки `views.py`, `models.py`, `middleware.py`, тесты `tests/test_demo_access.py` и другие. Не откатывай их и не делай `git stash`, `checkout`, `reset`. Дорабатывай поверх.

## Сначала прочитай

1. `CLAUDE.md` в корне.
2. `plans/zapusk-demo-reviews/phase-1.md` — отчёт ревьюера: замечания 1–3, раздел «Заметки на следующие фазы» про гонки.
3. `plans/2026-10-06-zapusk-demo.md`, раздел «Checkpoint»: записи о фазе 1, ревью и **решения судьи** (п. 1–6). Исправляешь ровно то, что судья принял в исправления фазы 1: п. 1–4.
4. `plans/zapusk-demo-prompts/phase-1.md` — исходная спецификация фазы. Её требования остаются в силе.

Файлы `.env`, `.dev_token` и содержимое `ssl/` не читай и не выводи. Папка `idea/` не нужна. К настоящему GigaChat не обращайся: ключ сейчас не работает, а для этих исправлений он и не нужен.

## Что исправить (сначала падающий тест, потом код)

### 1. Длинная тема выключает дневной потолок (блокирует)

**Причина.** `GigaChatTokenUsage.topic` — `CharField(max_length=255)`, а `platform` — `max_length=50` (`generator/models.py`). Допустимая тема — до `GENERATION_MAX_TOPIC_LENGTH` (500). На PostgreSQL запись строки падает, а `log_token_usage` в `generator/gigachat_api.py` проглатывает ошибку. Строка учёта не появляется, и потолок не растёт. На SQLite в тестах этого не видно.

**Исправление.** В `log_token_usage` обрежь `topic` и `platform` до `max_length` их полей. Длину бери из `GigaChatTokenUsage._meta.get_field(...).max_length`, а не числом в коде.

**Тест** с моком на уровне клиента (см. «Как мокать GigaChat»), чтобы работал настоящий `log_token_usage`:
- POST `/generator/` (AJAX) и POST `/regenerate-text/` с темой длиной ровно `GENERATION_MAX_TOPIC_LENGTH`;
- строка `GigaChatTokenUsage` есть, и `len(row.topic) <= max_length` поля;
- при `GIGACHAT_DAILY_CALL_LIMIT=1` (`override_settings`) второй такой запрос получает 429 и клиент не вызывается.

### 2. Цепочка вызовов после пересечения лимита (важно)

**Причина.** `generator_view` проверяет доступ один раз. Затем при `generate_image=on` вызывает `generate_text`, `generate_image_prompt_from_text`, `generate_image_gigachat`. Если `generate_text` пересёк лимит токена, `consume_gigachat_tokens` возвращает `False`. Тогда функция отдаёт `"WARNING: Лимит токенов…"` и не пишет строку учёта. Строка непустая, поэтому цепочка запускает ещё два вызова — они тоже без учёта. Так же устроен `generate_image_from_text`.

**Решение судьи:**
- (а) Строка `GigaChatTokenUsage` пишется для **каждого** состоявшегося вызова GigaChat, включая вызов, который пересёк лимит.
- (б) Текст, промпт или картинка, на которые квота уже потрачена, возвращаются как обычный результат, а не `WARNING`.
- (в) Перед **каждым** обращением к клиенту в `generate_text`, `generate_image_prompt_from_text`, `generate_image_gigachat` — если токен передан и `token.can_use_gigachat()[0]` ложно, выйти **без** обращения к клиенту:
  - `generate_text` возвращает строку-сообщение о лимите в прежнем стиле;
  - функции картинок возвращают `None`.

  Проверь: в `generator_view` при `image_prompt is None` есть запасной вызов `generate_image_gigachat(topic)` — он тоже должен выйти без обращения к клиенту.
- Объект токена в памяти должен отражать списание, чтобы проверка (в) перед следующим вызовом его увидела — см. п. 4.
- Другие `WARNING`-ответы (ошибки аутентификации, rate limit GigaChat) не трогай — это фазы 2 и 4.

**Тесты** с моком на уровне клиента:
- токен с `gigachat_tokens_used = limit - 1`, AJAX POST `/generator/` с `generate_image=on` → ровно **1** обращение к клиенту, ровно **1** строка `GigaChatTokenUsage`, в ответе сгенерированный текст, а не `WARNING`;
- то же для POST `/generate-image-from-text/` → 1 обращение, 1 строка;
- токен с исчерпанным лимитом (проверку во view обойти прямым вызовом функций `gigachat_api` с этим токеном) → 0 обращений к клиенту у всех трёх функций.

### 3. Ветка «нет токена» в `check_gigachat_access` не покрыта (мелочь)

**Тесты** на `generator.access.check_gigachat_access` напрямую (`RequestFactory`, сессия через `SessionMiddleware`):
- нет токена в сессии;
- токен истёк;
- токен неактивен.

Ожидается отказ 403, для AJAX — JSON с `success: false` и `error`; `request.token` не выставлен.

**Проверка, что тест ловит дефект.** Временно замени ветку `if token is None:` на возврат `None`, убедись, что новые тесты падают, и верни код. Затем сверь файл через `git diff`: в нём не должно остаться следов мутации. Это же можно сделать в копии проекта во временной папке вне репозитория — без `.env`, `.dev_token`, `ssl/`.

### 4. Потерянные обновления счётчиков (принято судьёй из заметок ревьюера)

**Причина.** `consume_gigachat_tokens`, `consume_openai_tokens` и `consume_generation` в `TemporaryAccessToken` делают `+=` и полный `save()`. Параллельные запросы одного токена (в том числе с разных IP) теряют списания.

**Исправление:**
- атомарное обновление через `F()` в `QuerySet.update(...)` или `save(update_fields=[...])` с `F()`;
- после него — `refresh_from_db(fields=[...])`, чтобы объект в памяти видел новое значение (нужно для п. 2в);
- возвращаемое значение и прежняя семантика сохраняются: тарифы с `-1` и типы без учёта не списываются; расход сверх лимита записывается; при пересечении лимита возвращается `False`.

**Тест:** загрузи два экземпляра одного токена до списания, спиши через каждый → в базе сумма обоих списаний. То же для `consume_generation` (поле `total_used`).

## Как мокать GigaChat на уровне клиента

- Текст и промпт картинки: `generator.gigachat_api._init_client()` возвращает клиент, у которого вызывается `.invoke(messages)`; у результата читается `.content`.
- Картинка: `generator.gigachat_api._init_direct_client()` возвращает клиент, у которого вызывается `.chat(payload)`. Посмотри в коде `generate_image_gigachat`, какой ответ он разбирает (`extract_image_id`, `download_image`), и сделай фейк, который проходит этот путь без сети. Если для этого нужно замокать `download_image`, мокай его.
- Вынеси фейковый клиент во вспомогательный код в `tests/`, например в `tests/helpers.py`, рядом с `TokenAuthMixin`.
- Подменяй через `unittest.mock.patch('generator.gigachat_api._init_client', ...)` внутри теста. Это перекрывает глобальный предохранитель из `tests/runner.py`.
- Число обращений считай по вызовам `.invoke` и `.chat` фейка.

## Границы

- **Разрешено менять:**
  - `generator/gigachat_api.py` — только `log_token_usage` и проверки и учёт в трёх функциях;
  - `generator/models.py` — только методы списания `TemporaryAccessToken`;
  - `generator/access.py` и `generator/views.py` — только если без этого не исправить п. 1–4;
  - `tests/`;
  - раздел «Checkpoint» плана.
- **Запрещено:**
  - промпты и форма — фаза 2;
  - тексты и шаблоны;
  - новые миграции (поля моделей не меняются);
  - `git add`, `commit`, `push`, `stash`, `checkout`, `reset`;
  - сеть и настоящий GigaChat.
- **Не ослабляй** существующие тесты фаз 0 и 1. Все 60 тестов остаются зелёными.
- **Не больше 3 попыток** исправить одну и ту же проверку. Потом остановка и описание в checkpoint и в отчёте.

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- Git Bash:
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access`
  Если добавишь новый модуль тестов, впиши его и в эту команду, и в команду в плане.
- После правок: `.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings` и `.venv/Scripts/python.exe manage.py makemigrations --dry-run --settings=ghostwriter.settings`. Должен остаться только старый дрейф (13 `Rename index`, `telegram_user_id_hash`, `total_used`), новых изменений моделей — нет.

## Checkpoint и отчёт

Допиши в раздел «Checkpoint» плана одну запись «фаза 1, исправления раунд 1», ничего не стирая:

- что изменено по каждому из п. 1–4;
- новые тесты;
- результат мутационной проверки п. 3;
- команда тестов и итог (было 60 → стало N);
- поправка к спорному решению 1 исполнителя: число неучтённых вызовов теперь 0.

Фазу `[x]` не отмечай.

В конце сессии выведи отчёт:

- изменённые файлы;
- итоговые строки тестов;
- результат мутации;
- спорные решения;
- что не получилось.
