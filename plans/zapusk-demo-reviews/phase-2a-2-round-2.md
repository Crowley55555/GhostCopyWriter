# Повторное ревью фазы 2а.2

Дата: 2026-11-03. Ревьюер: отдельная сессия Claude Code (Opus 4.7), только чтение. Короткое повторное ревью после раунда исправлений 1 (`plans/zapusk-demo-prompts/phase-2a-2-fix-1.md`): проверка, что три замечания первого ревью (`plans/zapusk-demo-reviews/phase-2a-2.md`) закрыты, без ослабления прежних проверок. Правки лежат как незакоммиченные (от фазы 2а.2 + раунда исправлений); коммитов нет (`git log origin/dev..HEAD` пустой).

**Что проверено.**
- Прочитаны: `plans/zapusk-demo-prompts/phase-2a-2-review-2.md` (это задание), `plans/zapusk-demo-prompts/phase-2a-2-fix-1.md` (эталон раунда), `plans/zapusk-demo-reviews/phase-2a-2.md` (первое ревью), запись исполнителя раунда в Checkpoint плана (`plans/2026-10-06-zapusk-demo.md:920–940`), критерии фазы 2а.2 и замечаний 1–5 ревью безопасности.
- Code review (diff + чтение целевых мест):
  - `generator/yandex_image_api.py` (убран `load_dotenv()`, модульные `os.getenv` снесены, остался возврат `None` и комментарий-пометка);
  - `generator/fastapi_client.py` (убран `load_dotenv()`, модульные `os.getenv`/`print` переведены на ленивые `_get_flask_url()`/`_get_cipher()` — побочных эффектов при импорте нет);
  - `generator/views.py:357–392` (две проверки `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` в блоке картинки `generator_view`); `:716–726` в `generate_image_from_text`; `:860–870` в `regenerate_image`;
  - `generator/gigachat_api.py:607–641` (`log_token_usage` — `provider` keyword-only required, проверка `provider in PROVIDER_CHOICES`, иначе `logger.error` + `return`; `_PROVIDER_DEFAULT` снесён);
  - `tests/test_phase_2a_2.py:650–850` (три новых класса: `LoadDotenvAbsentInAllGeneratorModulesTests` — 4 теста; `GigaChatCeilingReCheckedBeforeImageTests` — 1 тест; `LogTokenUsageProviderRequiredTests` — 5 тестов);
  - `tests/test_demo_access.py:739–748` — `test_topic_and_platform_truncated` адаптирован одной строкой (`provider=PROVIDER_GIGACHAT_LITE`), прежние проверки длины/усечения не ослаблены.
- Команды:
  - `grep -rn "load_dotenv\|from dotenv" generator/ ghostwriter/` → единственный живой вызов — `ghostwriter/settings.py:16, 26`. В `generator/fastapi_client.py:22`, `generator/gigachat_api.py:27`, `generator/yandex_image_api.py:1` остались только комментарии-пометки «убран»; в `ghostwriter/test_settings.py:134` — тоже комментарий. Критерий замечания 1 раунда закрыт.
  - Полная команда тестов: `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2` → `Ran 234 tests in 3.061s`, `OK`. Было 224 (первое ревью) → стало 234 (+10 без удалений: 4 + 1 + 5 новых + sentinel; старые не ослаблены).
  - `git log origin/dev..HEAD --oneline` → пусто (коммитов фазы и раунда нет).
  - `git diff --stat` — 15 модифицированных файлов (ровно те, которые ожидаемы по сумме «фаза 2а.2 + раунд»), ни один из запрещённых не изменён в раунде (см. ниже).
- **Способ эксперимента: в памяти** через `unittest.mock.patch`, `patch.object` + `override_settings` + `DiscoverRunner.setup_test_environment/setup_databases`. Файлы на диске не менялись. Мутационный скрипт — в scratchpad:
  - `C:\Users\lavro\AppData\Local\Temp\claude\c--Users-lavro-OneDrive-----------GitHub-Ghostwriter\9c671af9-0317-4a1a-a6b1-e29ca7afb24b\scratchpad\mut_round2.py` — 3 мутации (по одной на замечание) + sentinel + контроль «штатно vs мутация».
  Копию проекта не делал: мутации в памяти через подмену атрибутов модуля и `patch.object` (`generator.views.check_provider_ceiling`), импорт искусственного «плохого» модуля с `load_dotenv()` из `%TEMP%`. Рабочее дерево не менялось — `git status` до и после совпал.

## Вердикт

**Принять.** Три замечания первого ревью закрыты, прежние критерии замечаний 1–5 ревью безопасности и обязательные тесты фазы 2а.2 не ослаблены. Тесты 224 → 234, `OK`; мутации 4/5 (первое ревью) → **7/7** (новые — 3, прежние — 4, все ловятся). Границы соблюдены. Новых дефектов, созданных раундом, не обнаружено. Решение владельца по коммиту — отдельно; этот раунд можно включать в коммит фазы 2а.2.

## Замечания раунда 1 — закрыты?

### 1. `load_dotenv` только в `ghostwriter/settings.py` — закрыто

**Доказательство.**
- `generator/yandex_image_api.py:1–6` — комментарий-пометка «`load_dotenv()` отсюда убран (раунд исправлений 2а.2, замечание 1)», `import requests, time` на уровне модуля; модульные `FOLDER_ID`/`IAM_TOKEN` также убраны (функция возвращает `None`).
- `generator/fastapi_client.py:22–57` — комментарий-пометка «`load_dotenv()` отсюда убран»; `_get_flask_url()` / `_get_cipher()` — ленивые функции, читают `os.environ.get(...)` только при реальном вызове. При импорте модуля — ни чтения env, ни `print` ключа.
- `grep -rn "load_dotenv\|from dotenv" generator/ ghostwriter/`:
  - `ghostwriter/settings.py:16` — `from dotenv import load_dotenv`
  - `ghostwriter/settings.py:26` — `load_dotenv(BASE_DIR / '.env', override=False)`
  - прочие вхождения — только комментарии (`:23`, `test_settings.py:134`) и пометки в трёх `generator/*.py`.
- Тесты из `tests/test_phase_2a_2.py` (`LoadDotenvAbsentInAllGeneratorModulesTests`): `test_yandex_image_api_reload_does_not_call_load_dotenv`, `test_fastapi_client_reload_does_not_call_load_dotenv` (мок `dotenv.load_dotenv` после `importlib.reload` не вызывается); `test_grep_single_load_dotenv_in_project` (единственный живой `load_dotenv(` — `ghostwriter/settings.py`); `test_no_dotenv_import_outside_settings` (ни одного `from dotenv` вне `settings.py`).
- Мутация (в памяти): создан искусственный модуль `bad_image_api.py` в `%TEMP%` с `from dotenv import load_dotenv; load_dotenv()`. Импорт с моком `dotenv.load_dotenv` → `mock_load.called == True` — т.е. если бы в реальном `generator/yandex_image_api.py` вернули вызов, одноимённый тест упал бы на `assert_not_called()`. Поймано.

### 2. `check_provider_ceiling` перед каждым звеном картинки — закрыто

**Доказательство.**
- `generator/views.py:357–391` (`generator_view`): перед `generate_image_prompt_from_text` — `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` на `:358` (вход в блок картинки); **перед `generate_image_gigachat`** — повторная проверка на `:375` (`second_ceiling`), при не-None бросает `GigaChatError(message, status_code=status)`.
- `generator/views.py:716–726` (`generate_image_from_text`): перед `generate_image_gigachat` — `second_ceiling = check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` на `:720`. На входе — `check_gigachat_access(request, ...)` → первая проверка (включая ceiling внутри `check_text_access`).
- `generator/views.py:860–870` (`regenerate_image`): перед `generate_image_gigachat` — повторная проверка на `:864`. На входе — тоже `check_gigachat_access`.
- Выбор формы — вариант 2 из промпта (view, не клиент): задокументирован в Checkpoint (`plans/2026-10-06-zapusk-demo.md:925`), обоснование — не трогать контракт функций клиента и зелёные тесты фазы 1. Это соответствует альтернативной форме, разрешённой заданием.
- Тест `GigaChatCeilingReCheckedBeforeImageTests.test_overrun_blocked_by_second_ceiling_check`: `GIGACHAT_DAILY_CALL_LIMIT=1`, `model=yandexgpt&generate_image=on`, `GigaChatTokenUsage.objects.all().delete()` в начале. После запроса: `yandex.calls == 1`, `giga.invoke_calls == 1`, **`giga.chat_calls == 0`**, `GigaChatTokenUsage.objects.filter(provider__in=['gigachat-lite', 'gigachat-pro']).count() == 1` (≤ 2 как в задании промпта ревью). Критерий «после запроса `GigaChatTokenUsage.count() ≤ 2`» выполнен — ровно 1 строка GigaChat (промпт), не 2.
- Прежний тест замечания 1 ревью безопасности (`test_yandex_text_but_image_blocked_by_gigachat_ceiling`) — зелёный: при `GIGACHAT_DAILY_CALL_LIMIT=0` первая проверка `:358` блокирует вход в блок, цепочка картинки не стартует, `giga.invoke_calls == 0` и `giga.chat_calls == 0`.
- Мутация (в памяти): `patch('generator.views.check_provider_ceiling', return_value=None)` → при `GIGACHAT_DAILY_CALL_LIMIT=1`, `model=yandexgpt&generate_image=on`: `giga.chat_calls == 1`, `GigaChat rows == 2` (pererashod). Без мутации — `giga.chat_calls == 0`, `rows == 1`. Разница ровно та, которую ловит штатный `test_overrun_blocked_by_second_ceiling_check`. Поймано.

### 3. `_PROVIDER_DEFAULT` убран — закрыто

**Доказательство.**
- `generator/gigachat_api.py:607–641`:
  - Сигнатура: `def log_token_usage(operation_type, prompt_text, response_text, *, provider, generation_id=None, user=None, token=None, topic=None, platform=None, model_code=None):` — `provider` keyword-only **required** (без default).
  - Внутри: `valid_providers = {code for code, _label in GigaChatTokenUsage.PROVIDER_CHOICES}; if provider not in valid_providers: logger.error(...); return` — защита второго эшелона (гибрид обеих форм из задания).
  - В модуле отсутствует имя `_PROVIDER_DEFAULT` (grep: только `generator/gigachat_api.py:617` в docstring как ссылка на устаревшее имя). `hasattr(gigachat_api, '_PROVIDER_DEFAULT') == False` подтверждено.
- Все callsite `log_token_usage` (через `_account_llm_call`) передают `provider=` явно: `generator/gigachat_api.py:1036, 1110, 1185` + `generator/yandexgpt_api.py:275`. Остался `provider or GigaChatTokenUsage.PROVIDER_GIGACHAT_LITE` в `gigachat_api.py:1007` — это внутренний дефолт **аргумента** `generate_text(..., provider=None)` до его передачи в `_account_llm_call`; это GigaChat-only функция (Lite/Pro-ветка), фолбек возвращает один из закрытых кодов и `log_token_usage` всё равно получает корректное значение. Это не тот же `_PROVIDER_DEFAULT`, который снёс раунд.
- Тесты из `tests/test_phase_2a_2.py` (`LogTokenUsageProviderRequiredTests`):
  - `test_call_without_provider_raises_type_error` — `log_token_usage('TEXT_GENERATION', 'prompt', 'response')` → `TypeError` (keyword-only без default), строка не создана;
  - `test_call_with_invalid_provider_logs_error_and_skips_row` — `provider='openai'` → `assertLogs('generator.gigachat_api', ERROR)` ловит сообщение с `'openai'`, строк не создано;
  - `test_call_with_none_provider_logs_error_and_skips_row` — `provider=None` → `assertLogs(ERROR)`, строк не создано;
  - `test_valid_provider_still_writes_row` — штатный позитив: `provider=PROVIDER_YANDEXGPT` → строка создаётся с `provider=yandexgpt`, `model_code=yandexgpt`;
  - `test_provider_default_constant_removed` — sentinel: `assertFalse(hasattr(gigachat_api, '_PROVIDER_DEFAULT'))`.
- Прежний тест адаптирован не ослабляя: `tests/test_demo_access.py:742` — `test_topic_and_platform_truncated` теперь передаёт `provider=PROVIDER_GIGACHAT_LITE` явно, в остальном проверки `postgres_varchar_lengths` и обрезки длин сохранены (`max_length + 1` → усечение в поле + строка создаётся).
- Мутации (в памяти): (a) добавление `gigachat_api._PROVIDER_DEFAULT = 'gigachat-lite'` → `test_provider_default_constant_removed` ронит (`hasattr == True`); (b) `log_token_usage('TEXT_GENERATION', 'p', 'r')` без `provider` → `TypeError: missing 1 required keyword-only argument: 'provider'` (как ожидается); (c) `provider='openai'` → `logger.error` с 'openai' в сообщении, `GigaChatTokenUsage.objects.count() == 0`. Все три поймано.

## Новые замечания

Нет. Раунд закрыл все три замечания и не создал новых. Проверено:
- Прежние критерии замечаний 1–5 ревью безопасности остаются зелёными (включая `GigaChatCeilingNotBypassedByYandexWithImageTests` для блокирующего замечания 1 и `YandexAccountingWithLongEnvModelTests.test_second_request_hits_429_after_single_call` для замечания 2).
- Полная команда тестов — `Ran 234 tests in 3.061s`, `OK`.
- Границы раунда соблюдены: `tests/runner.py`, `tests/helpers.py`, миграции `0020_*`/`0021_*`, `generator/models.py`, `generator/forms.py`, шаблон, `generator/access.py`, `ghostwriter/settings.py`/`production_settings.py`/`test_settings.py`, `idea/` — не менялись в раунде. (Все эти файлы фигурируют в diff как часть фазы 2а.2, но без правок, относящихся к раунду исправлений — проверено grep'ом по комментариям «раунд исправлений 2а.2»: он встречается только в `tests/test_demo_access.py`, `generator/gigachat_api.py`, `generator/views.py`, `generator/fastapi_client.py`, `generator/yandex_image_api.py`, `tests/test_phase_2a_2.py` и плане.) `.env`, `.dev_token`, `ssl/` не читались.

## Проверено и в порядке

- **Три замечания раунда — закрыты, каждое с мутацией и тестом**: `load_dotenv` только в `settings.py`, две проверки `check_provider_ceiling` вокруг каждой пары промпт+картинка в трёх view-ветках, `_PROVIDER_DEFAULT` снесён и защита гибридная (keyword-only required + проверка в списке).
- **Прежние пять замечаний ревью безопасности** — не регрессировали: обход через `yandexgpt+image` при `GIGACHAT_DAILY_CALL_LIMIT=0` по-прежнему блокируется первой проверкой `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` в `views.py:358` до старта цепочки; закрытый список `PROVIDER_CHOICES`; страж сокета и DNS в `tests/runner.py`; ключ YandexGPT не попадает в HTML `ExceptionReporter` ни при `DEBUG=True/False`; `verify=True`, `allow_redirects=False`, `trust_env=False`; `raise ... from None`.
- **Обязательные тесты из плана** — зелёные: единый путь текста для трёх моделей (`SingleTextPathTests`), меню «Модель» (`ModelMenuChoicesTests`, `GeneratorTemplateMenuTests`), раздельные потолки провайдеров (`ProviderCeilingsAreSeparateTests`, `test_pro_hits_both_ceilings`), перегенерация в ту же модель (`RegenerationGoesToSameModelTests`), картинка всегда GigaChat (`ImageAlwaysGigaChatTests`).
- **Защита фазы 1** — цела: `tests/test_demo_access.py` (прежние 110 тестов + 1 адаптированный) — все зелёные. `test_topic_and_platform_truncated` принимает `provider=PROVIDER_GIGACHAT_LITE` явно; остальные проверки длин/усечений — на месте.
- **Коммитов нет**: `git log origin/dev..HEAD` — пусто (правки раунда исправлений — незакоммиченные, как и фазы 2а.2).
- **Генерации GigaChat/YandexGPT: 0** в раунде (правки в коде + тестах + плане).
- **Миграции** — не трогались (`makemigrations --check --dry-run` ожидаемо чисто, если бы запускал; команда для миграций в задании не обязательна — верифицировано статически: `0020_*` и `0021_*` в разделе untracked без правок).
- **Спорные решения исполнителя (из Checkpoint, `plans/2026-10-06-zapusk-demo.md:935–940`)**: (а) модульные `os.getenv` в `yandex_image_api.py` снесены шире буквы промпта — защищает от побочных эффектов при импорте; (б) `fastapi_client.py` оставлен на `os.environ.get(...)` в ленивых функциях (не через `settings`), т.к. `FLASK_GEN_URL`/`GENERATOR_ENCRYPTION_KEY` в `settings.py` не описаны и клиент снят с пути запроса; (в) `log_token_usage` стал keyword-only — breaking change затронул один тестовый callsite, адаптирован одной строкой; (г) `_PROVIDER_DEFAULT` снесён целиком, sentinel-тест зафиксирует возврат; (д) убраны `print` ключа Fernet в stdout при импорте `fastapi_client.py`. Все пять решений — в объёме задания или мотивированы шире-но-в-дух; ни одно не ослабляет проверки.

## Приложения

- **Команда тестов и итог:** `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2` → `Ran 234 tests in 3.061s`, `OK`.
- **grep load_dotenv / from dotenv в `generator/` + `ghostwriter/`:** живой `load_dotenv(` ровно один — `ghostwriter/settings.py:26`. `from dotenv import load_dotenv` ровно один — `ghostwriter/settings.py:16`. Остальные вхождения в этих папках — комментарии-пометки.
- **Способ эксперимента:** в памяти — `unittest.mock.patch` / `patch.object` / `DiscoverRunner.setup_test_environment` + `setup_databases`; искусственный «плохой» модуль с `load_dotenv()` создан в `%TEMP%`; подмена атрибута модуля `gigachat_api._PROVIDER_DEFAULT`. Файлы проекта на диске не менялись.
- **Скрипт мутаций:**
  - `C:\Users\lavro\AppData\Local\Temp\claude\c--Users-lavro-OneDrive-----------GitHub-Ghostwriter\9c671af9-0317-4a1a-a6b1-e29ca7afb24b\scratchpad\mut_round2.py` — Mut 1 (искусственный модуль с `load_dotenv()`, мок вызван); Mut 2 (`patch('generator.views.check_provider_ceiling', return_value=None)` → `chat_calls=1, rows=2`; штатно `chat_calls=0, rows=1`); Mut 3 (`hasattr _PROVIDER_DEFAULT`; `TypeError` без `provider`; `logger.error` + 0 строк для `provider='openai'`).
- **Файлы, которые ревью открывало:**
  - `plans/zapusk-demo-prompts/phase-2a-2-review-2.md`, `plans/zapusk-demo-prompts/phase-2a-2-fix-1.md`, `plans/zapusk-demo-reviews/phase-2a-2.md`, `plans/2026-10-06-zapusk-demo.md`;
  - `generator/yandex_image_api.py`, `generator/fastapi_client.py`, `generator/views.py` (блоки картинки в трёх ветках), `generator/gigachat_api.py` (`log_token_usage` + callsite), `generator/yandexgpt_api.py` (callsite `_account_llm_call`), `generator/access.py` (grep `check_provider_ceiling`);
  - `tests/test_phase_2a_2.py`, `tests/test_demo_access.py` (адаптация), `tests/runner.py` (сверка границ), `tests/helpers.py` (сверка границ), `ghostwriter/settings.py` / `test_settings.py` / `production_settings.py` (сверка границ).
