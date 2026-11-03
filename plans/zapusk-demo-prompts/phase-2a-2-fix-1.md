# Фаза 2а.2, раунд исправлений 1 — промпт исполнителя

Ты — исполнитель короткого раунда исправлений фазы 2а.2 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Это **новая сессия**, не связанная с сессией исполнителя 2а.2 и ревьюера 2а.2. Три замечания — два важных (включая один пограничный с блокирующим) и одна мелочь.

## Сначала прочитай

1. `CLAUDE.md` в корне.
2. `plans/2026-10-06-zapusk-demo.md`:
   - «Checkpoint» — свежие записи от 2026-11-03 (ревью 2а.2 и решения судьи — твоё задание именно оттуда);
   - «Фаза 2а.2» — критерии замечаний 1, 2, 3, 4, 5 (сверка с планом).
3. `plans/zapusk-demo-reviews/phase-2a-2.md` — отчёт ревью (контекст по трём замечаниям).
4. `plans/zapusk-demo-reviews/plan-v5-security.md` — замечания 1 и 4 (контекст безопасности).

`.env`, `.dev_token`, `ssl/` не читай и не выводи. Своих агентов не запускай.

## Состояние рабочего дерева

Основная ветка `dev` — коммит `62ab374` (промпты 2а.2). В рабочем дереве — незакоммиченные правки исполнителя 2а.2 (12 модифицированных + 5 новых файлов). **Не удаляй их**; добавляй правки поверх. Проверь `git status` перед работой.

## Что сделать

### Замечание 1: `load_dotenv()` в `generator/yandex_image_api.py` и `generator/fastapi_client.py` (важное)

**Сверенные факты (2026-11-03):**
- `generator/yandex_image_api.py:1` — `from dotenv import load_dotenv`; `:2` — `load_dotenv()`.
- `generator/fastapi_client.py:22` — `from dotenv import load_dotenv`; `:25` — `load_dotenv()`.
- `generator/views.py:42–43` импортирует эти модули.

**Что сделать:**
- Убрать `from dotenv import load_dotenv` и вызов `load_dotenv()` из обоих файлов.
- Если эти модули читают env через `os.getenv(...)` на уровне модуля — заменить на чтение через `django.conf.settings` или на функцию, вызываемую при реальном использовании. **Не вводить** побочные эффекты при импорте.
- Проверить **все** `generator/*.py` на `load_dotenv`: должно остаться ровно одно вхождение — в `ghostwriter/settings.py`. Команда для сверки:
  `grep -rn "load_dotenv\|from dotenv" generator/ ghostwriter/`
- В checkpoint — вывод этой команды до и после правки.

**Тест (`tests/test_phase_2a_2.py` или аналог):**
- `importlib.reload(generator.yandex_image_api)` c `mock.patch('dotenv.load_dotenv')` → мок **не вызывается**.
- То же для `generator.fastapi_client`.
- Мутация «вернуть `load_dotenv()` в любой из двух файлов» → тест ронит.

### Замечание 2: `check_provider_ceiling` не перепроверяется между промптом картинки и картинкой (важное)

**Сверенные факты (2026-11-03):**
- `generator/views.py:357–380`: `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` вызывается один раз в блоке `if generate_image_flag and result:`. Если проверка проходит, вызываются **и** `generate_image_prompt_from_text`, **и** `generate_image_gigachat` — без второго вызова `check_provider_ceiling`.
- При `GIGACHAT_DAILY_CALL_LIMIT=1` первая проверка проходит (count=0 ≤ 1); промпт картинки создаёт строку учёта (count=1); картинка идёт без проверки, тоже создаёт строку (count=2). Потолок обойдён на 1 вызов.
- Проверка требований плана: действия фазы 2а.2 говорят «Проверка перед каждым вызовом цепочки и учёт вызова, пересёкшего лимит, — для YandexGPT так же, как для GigaChat»; критерий замечания 1 — «мутация „перед вызовом картинки проверять только токен“ ронит тест».

**Что сделать:**
- Единая точка — функция клиента: встрой `check_provider_ceiling` **внутрь** `generate_image_prompt_from_text` и `generate_image_gigachat` (и в соответствующие функции для текста Lite/Pro/Yandex, если они ещё не проверяют), в начале — до вызова HTTP-клиента. Если потолок исчерпан — `raise GigaChatError(MSG_DAILY_LIMIT_GIGACHAT, 429) from None` (константа и код такие же, как в текущем месте). Это убирает дубль и даёт одну точку проверки на провайдера.
- Если встраивание в клиент сломает текущие тесты обобщения — альтернатива: оставить ветку картинки в `views.py:357–380`, но вызвать `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` **перед `generate_image_prompt_from_text`** и **ещё раз перед `generate_image_gigachat`**. Второй вариант проще, выбирай его, если первый тянет большую переделку.
- Проверь прочие цепочки картинки: `generate_image_from_text` (`:691–711`), `regenerate_image` (`:827–842`) — там тоже нужна проверка перед **каждым** вызовом картинки, если их больше одного; если один — одна проверка.
- Критерий фазы 2а.2 плана про `fake_yandexgpt` вызванный раз + `fake_gigachat` ни разу — не должен сломаться; добавь новый критерий про перерасход на 1.

**Тесты:**
- `GIGACHAT_DAILY_CALL_LIMIT=1`, `/generator/` с `model=gigachat-lite&generate_image=on`, фейк GigaChat возвращает успешно текст и промпт картинки, но на картинку — `GigaChatError(..., 429)`. Проверить: `GigaChatTokenUsage.objects.count()` после запроса = **1** (только текст), **не 2**. Либо: `fake_gigachat.image_calls == 0`.
- Мутация «убрать одну из двух проверок `check_provider_ceiling`» → тест ронит.
- Прежние тесты (замечание 1 ревью безопасности, обход через YandexGPT) остаются зелёными.

### Замечание 3: `_PROVIDER_DEFAULT` — хрупкая защита (мелочь)

**Сверенные факты (2026-11-03):**
- `generator/gigachat_api.py:610` — `_PROVIDER_DEFAULT = 'gigachat-lite'`.
- `generator/gigachat_api.py:654` — `provider_value = str(provider or _PROVIDER_DEFAULT)[:provider_max]`.
- Если вызов `log_token_usage` без `provider=`, yandex-строка пойдёт в учёт GigaChat.

**Что сделать:**
- Убрать `_PROVIDER_DEFAULT`.
- Сделать `provider` **обязательным** в `log_token_usage(..., *, provider, model_code=None, ...)` (keyword-only, без значения по умолчанию). Любой вызов без `provider` → `TypeError` (ловится при импорте тестов, а не в проде).
- Если какая-то функция в `gigachat_api.py` сейчас вызывает `log_token_usage` без явного `provider` — передай явно (`PROVIDER_GIGACHAT_LITE`, `PROVIDER_GIGACHAT_PRO`, `PROVIDER_YANDEX`).
- Либо: оставить сигнатуру с `provider=None`, но на `None` или не входящем в закрытый список значении — `logger.error` и `return` без создания строки `GigaChatTokenUsage`.

**Тест:**
- `log_token_usage(..., provider=None)` → `TypeError` (при обязательном параметре) **или** строка `GigaChatTokenUsage` не создана и в логе есть `ERROR` (при `logger.error`-варианте). Выбери одну форму, зафиксируй в тесте и в checkpoint.
- Мутация «вернуть `_PROVIDER_DEFAULT = 'gigachat-lite'` и `provider or _PROVIDER_DEFAULT`» → тест ронит.

### Прогон и checkpoint

- Полная команда тестов:
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2`
- Результат — `OK`, число — 224 или 225+ (если добавил новые тесты). Если упало — остановись и запиши в checkpoint.
- `manage.py check --settings=ghostwriter.settings` — чисто.
- `makemigrations --check --dry-run --settings=ghostwriter.settings` — чисто (миграции не трогай).

Запись в раздел «Checkpoint» плана в конце (ничего не стирая):
- изменённые файлы;
- `grep -rn "load_dotenv\|from dotenv" generator/ ghostwriter/` до и после;
- выбор формы `check_provider_ceiling` (внутри клиента / перед каждым вызовом в view) и обоснование;
- выбор формы для `_PROVIDER_DEFAULT` (keyword-only required / `logger.error`+return) и обоснование;
- результат мутаций: 4 из 5 (ревью 2а.2) → должны стать 7 из 7 или больше;
- итог тестов: было 224 → стало N, `OK`;
- границы соблюдены: `tests/runner.py` не менялся, миграции не менялись, `idea/` не менялся.

Фазу `[x]` не отмечай.

## Границы

- **Разрешено менять:**
  - `generator/yandex_image_api.py`, `generator/fastapi_client.py` — убрать `load_dotenv`;
  - `generator/views.py` — повторная проверка `check_provider_ceiling` перед `generate_image_gigachat` (вариант 2) или удаление дубля (вариант 1);
  - `generator/gigachat_api.py` — `log_token_usage`, `_PROVIDER_DEFAULT`, встраивание `check_provider_ceiling` в функции клиента (вариант 1);
  - `tests/test_phase_2a_2.py` — новые тесты и правка существующих;
  - план — только «Checkpoint».
- **Запрещено:**
  - `tests/runner.py`, `tests/helpers.py` — не трогай (кроме случая, когда без правки `helpers.py` новый тест не написать; тогда одна правка с объяснением);
  - миграции (`0020_*`, `0021_*`), `generator/models.py` — не трогай;
  - форма (`generator/forms.py`), шаблон, настройки — не трогай;
  - лендинг, другие страницы, `generator/access.py` (кроме случая, если `check_provider_ceiling` требует точечной правки сигнатуры — тогда одна правка с объяснением);
  - `idea/`, `.env`, `.dev_token`, `ssl/`;
  - `git add/commit/push/merge` — только оркестратор.
- Не больше 3 попыток исправить одну и ту же проверку.
- Генераций GigaChat/YandexGPT: **0** (правки — чисто в коде и тестах, без вызова живых клиентов).

## В конце сессии

Коротко (3–5 строк): файлы, итог тестов (было/стало), спорные решения, что осталось. Детали — в checkpoint, не в чат.
