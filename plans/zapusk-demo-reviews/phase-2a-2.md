# Ревью фазы 2а.2

Дата: 2026-11-03. Ревьюер: отдельная сессия Claude Code (Opus 4.7), только чтение. Фаза 2а.2 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1): меню «Модель», клиент YandexGPT, обобщение защиты фазы 1 на провайдеров, миграции 0020 (дрейф) и 0021 (`provider`, `model_code`). Правки исполнителя — незакоммиченные изменения относительно HEAD `62ab374`.

**Что проверено.**
- Прочитаны: `plans/zapusk-demo-prompts/phase-2a-2-review.md`, `plans/zapusk-demo-prompts/phase-2a-2.md`, план (фаза 2а.2 — действия и критерии; «Ревью версии 5» замечания 1–5; Checkpoint — записи фаз 1, 2, 2а.1 и запись исполнителя 2а.2), `plans/zapusk-demo-reviews/plan-v5-security.md` (контекст замечаний 1–5), `plans/zapusk-demo-reviews/phase-2a-1.md` (контракты фазы 2а.1). `.env`, `.dev_token`, `ssl/` — не читал.
- Code review: полный `git diff HEAD` по 12 изменённым файлам + 5 новых; чтение затронутых мест в `generator/access.py`, `generator/forms.py`, `generator/gigachat_api.py`, `generator/models.py`, `generator/views.py`, `generator/yandexgpt_api.py`, `generator/templates/generator/gigagenerator.html`, `ghostwriter/settings.py`, `ghostwriter/production_settings.py`, `ghostwriter/test_settings.py`, `tests/helpers.py`, `tests/runner.py`, `tests/test_network_guard.py`, `tests/test_phase_2a_2.py`, миграций `0020_rename_...`, `0021_provider_and_model_code.py`. Дополнительно вскрыл `generator/yandex_image_api.py`, `generator/fastapi_client.py` (импортируются из `views.py`).
- Команды:
  - `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2` → `Ran 224 tests in 3.614s`, `OK`. Было 190 (`6399c97`), стало 224 (+34: 6 в `tests.test_network_guard`, 28 в `tests.test_phase_2a_2`). Старые тесты фаз 0–2а.1 не удалены и не ослаблены.
  - `.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings` → `System check identified no issues (0 silenced)`.
  - `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=ghostwriter.settings` → `No changes detected` (дрейф закрыт `0020`, фаза 2а.2 закрыта `0021`).
  - `git log 6399c97..HEAD --oneline` → только `62ab374 docs: промпты...` (коммитов фазы нет, правки — незакоммиченные).
- **Способ эксперимента: в памяти** (`unittest.mock.patch` + `DJANGO_SETTINGS_MODULE=test_settings`), файлы на диске не менялись. Мутационные скрипты — в scratchpad:
  - `C:/Users/lavro/AppData/Local/Temp/claude/c--Users-lavro-OneDrive-----------GitHub-Ghostwriter/9c671af9-0317-4a1a-a6b1-e29ca7afb24b/scratchpad/mutations_2a_2.py` — 4 мутации + probe
  - `C:/Users/lavro/AppData/Local/Temp/claude/c--Users-lavro-OneDrive-----------GitHub-Ghostwriter/9c671af9-0317-4a1a-a6b1-e29ca7afb24b/scratchpad/overrun_isolated.py` — изолированная проверка перерасхода потолка
  Копию проекта не делал. Рабочее дерево не менялось — `git status` до и после совпал.
- Мутации (в памяти). Поймано — 4 из 5 ключевых; одна (внутри цепочки картинки) ловится только тестом замечания 1 для своего сценария (counter=0, limit=0); сценарий «counter=limit-1 внутри цепочки» штатным тестом не покрыт — см. замечание 2.
  - **Пойманы:** `check_provider_ceiling` возвращает `None` всегда → `/generator/` с `yandex+image` при `GIGACHAT_DAILY_CALL_LIMIT=0` вызывает фейк GigaChat (invoke=1, chat=1), тест `GigaChatCeilingNotBypassedByYandexWithImageTests.test_yandex_text_but_image_blocked_by_gigachat_ceiling` ронит на `assertEqual((giga.invoke_calls, giga.chat_calls), (0, 0))`; `from e` вместо `from None` → `__cause__=ConnectionError`, тест `test_from_none_breaks_exception_chain` ронит на `assertIsNone(exc.__cause__)`; `verify=False` подмена в клиенте → `test_verify_true_and_allow_redirects_false` ронит на `assertNotEqual(kwargs['verify'], False)`; удалить `provider=` из звонка `generate_text_yandex` → строка попадёт как `gigachat-lite` (default), тест `test_second_request_hits_429_after_single_call` ронит (ceiling не поймает).
  - **Не поймано:** перерасход потолка GigaChat на 1 вызов из-за отсутствия `check_provider_ceiling` внутри `generate_image_gigachat` и `generate_image_prompt_from_text` (см. замечание 2 ниже).

## Вердикт

**Принять после исправлений.** Пять замечаний ревью безопасности (1 блокирующее + 4 важных) закрыты по основной формулировке и покрыты тестами: `yandexgpt+image` при пустом потолке GigaChat не доходит до GigaChat, `provider`/`model_code` — закрытый список констант кода, страж сокета стоит и ловит DNS-мок, `load_dotenv` в `settings.py` (ровно одно место для `gigachat_api.py`), ключ YandexGPT не попадает в `ExceptionReporter` ни при `DEBUG=True`, ни при `False`, клиент `verify=True`/`trust_env=False`/`allow_redirects=False`, исключения `from None`. Тесты 190 → 224 OK, миграции чистые (две: дрейф и 2а.2), границы соблюдены. Замечаний три: одно важное (замечание 4 закрыто не полностью: `load_dotenv()` остался в `yandex_image_api.py` и `fastapi_client.py`), одно важное (ceiling не перепроверяется внутри image-цепочки — перерасход на 1 вызов), одно мелкое (безопасный default `_PROVIDER_DEFAULT='gigachat-lite'` в `log_token_usage` молча заберёт yandex-строку в GigaChat-учёт, если вызывающий забыл `provider=`). Ни одно не блокирует коммит фазы, но первые два стоит закрыть до запуска демо.

## Замечания

### 1. Замечание 4 ревью безопасности закрыто не полностью: `load_dotenv()` остался в `generator/yandex_image_api.py` и `generator/fastapi_client.py`

- **Серьёзность:** важно.
- **Доказательство:**
  - `generator/yandex_image_api.py:1-2`:
    ```
    from dotenv import load_dotenv
    load_dotenv()
    ```
    Файл импортируется из `generator/views.py:42` (`from .yandex_image_api import generate_image as generate_image_yandex`), значит `load_dotenv()` вызывается при каждом старте Django-процесса, когда загрузится `urls.py` → `views.py`.
  - `generator/fastapi_client.py:22, 25`:
    ```
    from dotenv import load_dotenv
    ...
    load_dotenv()
    ```
    Тоже импортируется из `views.py:43` (`from .fastapi_client import generate_text_and_prompt, generate_image`); Flask-клиент снят с пути запроса, но файл остаётся — импорт у Django на старте есть.
  - Оба вызова — **без аргумента пути**, то есть `load_dotenv()` ищет `.env` вверх по дереву от файла. Именно это план назвал опасным (`settings.py:23–24`: «Файл ищется только в корне проекта — без поиска вверх по дереву (`load_dotenv()` без пути уходил бы в родительскую папку и подтягивал бы чужой `.env`)»).
  - Оба файла читают ключи **напрямую из `os.environ`**, а не через `settings`: `yandex_image_api.py:7-8` (`YANDEX_FOLDER_ID`, `YANDEX_IAM_TOKEN`), `fastapi_client.py:27-28` (`FLASK_GEN_URL`, `GENERATOR_ENCRYPTION_KEY`). Это тоже прямо противоречит пункту 1 задания исполнителя: «Клиенты всех провайдеров читают ключи **через `settings`**, не напрямую `os.environ`».
  - Тест `LoadDotenvOnlyInSettingsTests.test_settings_calls_load_dotenv_once` (`tests/test_phase_2a_2.py:227–244`) ищет `from dotenv import` / `load_dotenv(` только в `generator/gigachat_api.py` — два других файла не проверяются. `test_gigachat_api_reload_does_not_call_load_dotenv` перезагружает только `gigachat_api`, поэтому не ловит это тоже.
- **Сценарий сбоя:**
  - На машине владельца `.env` лежит в корне проекта — там же, где `settings.py` его найдёт. `load_dotenv()` в `yandex_image_api.py` сначала ищет `.env` рядом с собой (`generator/`), потом поднимается к родителю (корень проекта), находит `.env` там и загружает. Это пока работает так же, как load_dotenv в `settings.py`.
  - Если репозиторий окажется в директории с чужим `.env` выше корня (например, OneDrive с общим `.env` на уровне `Документы/GitHub/`), `yandex_image_api.py` поднимется вверх до корня проекта, не найдёт там `.env` и пойдёт дальше. Это уже отдельный путь загрузки — его может подхватить, например, тест, запущенный без установленных env-переменных.
  - На продакшене оба файла импортируются с `urls.py`, но `.env` в образе нет (`.dockerignore`). Поэтому их вызов — no-op на prod, но не на локалке и не в тестах.
  - На тестовом раннере: `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings` — `test_settings.py` сам `load_dotenv` не вызывает, но при импорте `views.py` эти два файла его позовут. На практике `test_settings` переопределяет ключи пустыми строками через `override_settings` в своих тестах, поэтому они туда не прорастают. Но тест критерия замечания 4 этого не покрывает — он только проверяет имена констант в `settings`.
- **Что изменить:**
  - В `generator/yandex_image_api.py` убрать `from dotenv import load_dotenv` и `load_dotenv()`; читать `YANDEX_FOLDER_ID`/`YANDEX_IAM_TOKEN` из `settings`. Файл сейчас — заглушка, возвращающая `None`; можно оставить только тело `def generate_image(prompt): return None` без модульных импортов env.
  - В `generator/fastapi_client.py` то же: убрать `load_dotenv`, читать `FLASK_GEN_URL` и `GENERATOR_ENCRYPTION_KEY` через `settings`.
  - Расширить `test_settings_calls_load_dotenv_once`: обход всех `.py` в `generator/` (grep по `load_dotenv(`), не только `gigachat_api.py`. Или добавить тест с `importlib.reload(generator.yandex_image_api)` и моком `dotenv.load_dotenv`.
- **Как проверить:** мутация — вернуть `load_dotenv()` в любом из этих файлов → расширенный тест ронит. Текущий тест на `gigachat_api.py` после правки файлов остаётся зелёным (ничего не ломается).

### 2. `check_provider_ceiling` не перепроверяется между вызовами цепочки картинки → перерасход потолка GigaChat на 1 вызов

- **Серьёзность:** важно.
- **Доказательство:**
  - План фазы 2а.2 (раздел «Защита фазы 1 обобщается», абзац «Проверка идёт по провайдеру ФАКТИЧЕСКОГО вызова») требует: «Это требование означает, что проверку нельзя делать только один раз в начале запроса. Решение: вводи функцию `check_provider_ceiling(provider_code)` → либо `None`, либо `ProviderError(...)`. Вызывай её **в начале каждой функции цепочки** (`generate_text_gigachat`, `generate_text_yandex`, `generate_image_prompt_from_text`, `generate_image_gigachat`), в дополнение к уже имеющемуся `_gigachat_limit_reached` для токена».
  - Фактически `check_provider_ceiling` вызывается ТОЛЬКО:
    - `generator/access.py:274` — внутри `check_text_access`, то есть один раз на старте запроса в view;
    - `generator/views.py:358` — один раз перед цепочкой картинки в `generator_view`.
  - Внутри четырёх клиентов (`generator/gigachat_api.py:991, 1048, 1122` + `generator/yandexgpt_api.py:253`) — только `_token_limit_reached(token)` (проверка бюджета токена, не потолка).
  - Воспроизведено (`scratchpad/overrun_isolated.py`): `GIGACHAT_DAILY_CALL_LIMIT=1`, `GigaChatTokenUsage.objects.count()=0`, `POST /generator/` с `model=yandexgpt&generate_image=on`:
    ```
    yandex.calls=1
    giga.invoke_calls=1 (image prompt)
    giga.chat_calls=1  (image gen)
    rows: 1 yandex + 2 gigachat-lite → GigaChat ceiling=1 превышен (2 записи).
    ```
    `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` перед цепочкой: 0 < 1 → OK. `generate_image_prompt_from_text` пишет строку → счётчик=1 (ровно потолок). Следующий вызов `generate_image_gigachat` НЕ перепроверяет ceiling → проходит и пишет ещё одну строку → счётчик=2.
  - То же наблюдается в `/generate-image-from-text/` и `/regenerate-image/` (`generator/views.py:676, 817`): `check_gigachat_access` один раз, затем две функции без внутренней проверки ceiling.
- **Сценарий сбоя:**
  - При любом `GIGACHAT_DAILY_CALL_LIMIT=N` и `count=N-1` одна цепочка картинки допишет две строки → `count=N+1`. На выходе потолок превышен на 1.
  - При `GIGACHAT_MAX_CONCURRENT>1` (фаза 6) и K одновременных запросах у края потолка — перерасход до K лишних вызовов GigaChat (замечание 6 плана про очередь — отдельная тема, но этот зазор ту же гонку расширяет).
  - В сценарии блокирующего замечания 1 (`counter=0, limit=0`) ceiling блокирует верхним checkом в `generator_view:358`, image-chain вообще не запускается — критерий замечания 1 выполнен, тест зелёный. Поэтому обязательный тест этот зазор НЕ ловит; его нужен отдельный, с `limit=N, count=N-1`.
- **Что изменить:**
  - Либо добавить `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` в начало `generate_image_prompt_from_text` и `generate_image_gigachat` (с `raise GigaChatError(message, status_code=status)` при не-None результате);
  - либо расширить `_token_limit_reached(token)` до `_text_call_ok(token, provider_code)`, который и смотрит токен, и зовёт `check_provider_ceiling(provider_code)`. Тогда все четыре функции цепочки покроются одной точкой.
  - Для `generate_text_yandex` и `generate_text` (gigachat) тоже добавить вызов — это один вызов в цепочке, но план требует явного вызова в начале каждой функции, и это защитит от мутаций «обойти view-уровень».
- **Как проверить:**
  - Тест: `GIGACHAT_DAILY_CALL_LIMIT=1`, предварительно записать 0 строк; `POST /generator/` с `model=yandexgpt&generate_image=on`; `giga.invoke_calls=1`, `giga.chat_calls=0`, `GigaChatTokenUsage.objects.filter(provider__in=['gigachat-lite', 'gigachat-pro']).count()=1`. Мутация «не ставить check_provider_ceiling в начало generate_image_gigachat» → `chat_calls=1`, тест ронит.
  - Второй тест для `/generate-image-from-text/`: `limit=1, count=0`, вызов эндпоинта → `invoke_calls=1, chat_calls=0`.

### 3. `log_token_usage._PROVIDER_DEFAULT='gigachat-lite'` молча пишет yandex-строку в учёт GigaChat, если вызывающий забыл `provider=`

- **Серьёзность:** мелочь.
- **Доказательство:**
  - `generator/gigachat_api.py:610`: `_PROVIDER_DEFAULT = 'gigachat-lite'`.
  - `generator/gigachat_api.py:654–655`: `provider_value = str(provider or _PROVIDER_DEFAULT)[:provider_max]`; `model_code_value = str(model_code or provider_value)[:model_code_max]`.
  - Если звонок (например, будущий yandex-эндпоинт) передаст `provider=None` или забудет kwarg совсем, строка попадёт в учёт с `provider='gigachat-lite'`. Потолок `check_provider_ceiling(PROVIDER_YANDEXGPT)` фильтрует `provider='yandexgpt'` (`generator/access.py:238–244`) — такую строку он не поймает, и yandex-ceiling молча не сработает.
  - Проверено (`scratchpad/mutations_2a_2.py`, Mut 2): `log_token_usage(operation_type='TEXT_GENERATION', prompt_text='p', response_text='r')` без `provider=` → `provider='gigachat-lite', model_code='gigachat-lite'`.
  - В текущем коде все 4 звонка (`generate_text`, `generate_image_prompt_from_text`, `generate_image_gigachat`, `generate_text_yandex`) передают provider явно; критерий замечания 2 (`test_entry_written_with_closed_list_constant` + `test_second_request_hits_429_after_single_call`) этот фолбек не проходит, потому что `generate_text_yandex` пишет `PROVIDER_YANDEXGPT` явно. Проблема — хрупкая защита от будущих ошибок.
- **Сценарий сбоя:** фаза 2а.3 или будущий провайдер добавит ещё одну функцию, забудет `provider=`, строка молча пишется как `gigachat-lite`. YANDEX-ceiling обходится, учёт перекошен в сторону GigaChat.
- **Что изменить:** сделать `provider` обязательным позиционным аргументом (без default) в `log_token_usage`; либо проверять `provider in PROVIDER_CHOICES` и бросать `ValueError`, если его нет (ошибка попадает в `logger.exception`, строка не пишется). Второй вариант безопаснее: лучше не записать, чем записать в неправильный учёт.
- **Как проверить:** тест: `log_token_usage(operation_type=..., prompt_text=..., response_text=...)` без `provider` → `ValueError` или ровно 0 записей и `logger.error`. Текущий default-поведение `'gigachat-lite'` при явном `provider=None` — ронит.

## Проверено и в порядке

- **Пять замечаний ревью безопасности — по основной формулировке закрыты:**
  - **Зам. 1 (блокирующее):** `GigaChatCeilingNotBypassedByYandexWithImageTests.test_yandex_text_but_image_blocked_by_gigachat_ceiling` — `POST /generator/` с `GIGACHAT_DAILY_CALL_LIMIT=0, model=yandexgpt, generate_image=on` → `yandex.calls=1, giga.invoke=0, giga.chat=0`, `data.image_error=MSG_DAILY_LIMIT`. Мутация `check_provider_ceiling → None` ронит тест (воспроизведено). См. замечание 2 выше — overrun внутри цепочки картинки на 1 вызов этим тестом не ловится.
  - **Зам. 2:** `GigaChatTokenUsage.PROVIDER_CHOICES` = закрытый список `('gigachat-lite', 'gigachat-pro', 'yandexgpt')` в `generator/models.py:441–445`; `log_token_usage` пишет `provider_value = str(provider or _PROVIDER_DEFAULT)[:provider_max]` (из закрытого списка, не из env). `YandexAccountingWithLongEnvModelTests.test_entry_written_with_closed_list_constant` c `YANDEX_GPT_MODEL='y'*200` + `postgres_varchar_lengths(GigaChatTokenUsage)` → `provider='yandexgpt', model_code='yandexgpt'`. `log_token_usage` ошибку пишет в `logger.exception(...)` (`gigachat_api.py:675`), не `print`.
  - **Зам. 3:** `tests/runner.py` расширен заглушками на `socket.socket.connect`, `connect_ex`, `socket.create_connection`, `getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `httpx.HTTPTransport.handle_request`, `urllib.request.urlopen`, `generator.yandexgpt_api._call_completion`. `tests/test_network_guard.py` — постоянный модуль с 6 тестами (сокет, DNS, DNS-мок + urllib3, httpx, urllib, yandex без мока), все зелёные. Модуль в команде тестов плана.
  - **Зам. 4:** `ghostwriter/settings.py:26` — единственный вызов `load_dotenv(BASE_DIR / '.env', override=False)` в `ghostwriter/`. `generator/gigachat_api.py` — вызов убран (комментарий на `:27`). `test_settings.py` ключи провайдеров — пустые строки. Клиент gigachat читает credentials через `_get_credentials()` → `getattr(settings, ...)`; клиент yandex — через `settings` (`generator/yandexgpt_api.py:214–215`). `connection.vendor == 'sqlite'` в тестах. **См. замечание 1 выше** — есть две остаточные точки `load_dotenv()` вне `settings.py` и `gigachat_api.py`.
  - **Зам. 5:** `generator/yandexgpt_api.py`: `_make_session()` c `trust_env=False`; `session.post(..., verify=True, allow_redirects=False, timeout=(connect, read))`; `maxTokens=str(settings.YANDEX_MAX_TOKENS)`. `_do_http_call` + `_call_completion` + `_call_from_settings` — три фрейма, где ключ очищается через `del` до `raise ... from None`, чтобы Django `ExceptionReporter` не нашёл его в `f_locals`. Тесты `test_key_absent_from_traceback_html_in_debug_true/false`, `test_verify_true_and_allow_redirects_false`, `test_from_none_breaks_exception_chain` — зелёные; мутации на `verify=False`, `from e`, keyword leak — поймало.
- **Единый путь текста:** `SingleTextPathTests.test_same_prompt_and_message_across_three_models` — три модели, один набор данных, одинаковый `system_prompt` и `user_message` между `fake_gigachat.invoke_messages` и `fake_yandexgpt.messages`. Lite и Pro идут через один `generate_text(...)`, Yandex — через `generate_text_yandex(...)`, оба зовут `assemble_prompt_from_criteria` и `build_user_message` (общий код в `gigachat_api.py`). Постобработка `postprocess_final_result` применяется одинаково.
- **Меню «Модель» и форма:** `GenerationForm.model` — `ChoiceField(choices=MODEL_CHOICES)` (3 пункта), `required=False`, default/clean → `MODEL_DEFAULT='gigachat-lite'`. View формирует `available_models` без Yandex, если `YANDEX_API_KEY` или `YANDEX_FOLDER_ID` пусты. Разметка (`gigagenerator.html:287–291`) — `<select name="model">` с `{% for value, label in available_models %}`. Без ключа `>YandexGPT<` не встречается (`GeneratorTemplateMenuTests.test_yandex_hidden_without_key`); с ключом — встречается (`test_yandex_visible_with_key`). `generator_type` в разметке нет (`test_generator_type_not_in_markup`). `openai`/`invalid-model` → 400, ни один фейк не вызван (`ModelMenuChoicesTests`). `yandexgpt` без ключа → 400 `MSG_YANDEX_NOT_CONFIGURED`, ни один фейк не вызван.
- **Перегенерация:** `RegenerationGoesToSameModelTests.test_regenerate_follows_last_model` — модель берётся из `last_form_data['model']`, при `yandexgpt` — тот же путь; GigaChat не трогается.
- **Картинки всегда GigaChat:** `ImageAlwaysGigaChatTests.test_image_uses_gigachat_when_text_is_yandex` — Yandex пишет текст, image prompt + image генерируются через `generate_image_prompt_from_text`/`generate_image_gigachat` (всегда с `settings.GIGACHAT_MODEL`).
- **Защита фазы 1 — обобщение.** `check_text_access(request, provider_code, topic, result_text, business_info)` — единая точка. Для yandex: `check_text_access(PROVIDER_YANDEXGPT, ...)` считает `GigaChatTokenUsage.objects.filter(provider='yandexgpt').count()`. Для gigachat: сумма `provider in ('gigachat-lite', 'gigachat-pro')` + `provider=''` (старые строки фазы 1 засчитываются в общий GigaChat, не обнуляют потолок после миграции). Pro упирается в оба потолка — `test_pro_hits_both_ceilings`. Старое имя `check_gigachat_access` — тонкая обёртка (`access.py:294–302`) с `PROVIDER_GIGACHAT_LITE`, чтобы `generate_image_from_text`/`regenerate_image` (GigaChat-only) не правились. Один бюджет токена — поле `gigachat_tokens_limit`/`used` на `TemporaryAccessToken`, имя сохранено (меньшая миграция, запись в checkpoint). `_token_limit_reached(token)` — единая проверка бюджета токена; `_gigachat_limit_reached` — псевдоним для обратной совместимости тестов.
- **Yandex клиент и фейк.** `generator/yandexgpt_api.py` — отдельный файл; API `https://llm.api.cloud.yandex.net/foundationModels/v1/completion`, авторизация `Api-Key`, модель `gpt://<folder_id>/<model>/latest`. `YandexGPTError` с `.message` и `.status_code`. Проверка ключа и каталога **до HTTP-вызова**: `if not api_key or not folder_id: raise YandexGPTError(MSG_YANDEX_NOT_CONFIGURED, 400)`. `tests/helpers.FakeYandexGPT` — счётчик `.calls`, список `.messages=[(system_prompt, user_message), ...]`; `fake_yandexgpt(override_keys=True)` + контекст `_call_completion`. Фейк не трогает `requests`, фиксирует именно сообщения, уходящие в клиент.
- **Миграции.** `0020_rename_generator_g_operati_created_idx_...` — ТОЛЬКО старый дрейф (13 `RenameIndex` + `RemoveField(telegram_user_id_hash)` + `AlterField(total_used)`). `0021_provider_and_model_code.py` — ТОЛЬКО `AddField(model_code, CharField(max_length=100, blank=True, default=''))` и `AddField(provider, CharField(max_length=20, choices=..., blank=True, default=''))`. `TemporaryAccessToken`, `AccessEvent`, `Generation` не затронуты. `AddField` с `default=''` → старые строки получают пустое значение, не ломаются; `check_provider_ceiling` для GigaChat считает их через `provider=''`-ветку. `makemigrations --check --dry-run --settings=ghostwriter.settings` после обеих миграций — `No changes detected`.
- **Границы фазы 2а.2.** В diff — только разрешённые файлы: `generator/access.py`, `forms.py`, `gigachat_api.py`, `models.py`, `templates/generator/gigagenerator.html`, `views.py`, три файла настроек, `tests/helpers.py`, `tests/runner.py`, план (Checkpoint). Новые: `generator/yandexgpt_api.py`, `generator/migrations/0020_...`, `generator/migrations/0021_...`, `tests/test_network_guard.py`, `tests/test_phase_2a_2.py`. Не тронуты: `generator/models.py` в части `TemporaryAccessToken`, `AccessEvent`, `Generation` (только добавление полей в `GigaChatTokenUsage`); лендинг; `tests/test_django_models.py`; `tests/test_demo_access.py` и `tests/test_post_quality.py` (ядро фаз 0–2а.1 — зелёные без правок); `idea/`; `.env`; `.dev_token`; `ssl/`. Flask-клиент `generate_text_and_prompt` остался в `fastapi_client.py` (снят с пути, не удалён — см. замечание 1 про `load_dotenv` там). Коммитов нет (`git log 6399c97..HEAD --oneline` → только `62ab374 docs:`). Новых зависимостей времени выполнения нет (`requirements.txt` не трогали).
- **Тесты (всё OK):** `Ran 224 tests in 3.614s`, `OK`. 190 → 224: +6 `tests.test_network_guard` (постоянный страж), +28 `tests.test_phase_2a_2` (5 замечаний + меню «Модель» + единый путь + потолки + перегенерация + картинка + константы провайдеров + мутации). Старые тесты не удалены. `manage.py check --settings=ghostwriter.settings` — без замечаний.
- **Ручной прогон 10 тем** — не выполнен (`.env` в worktree отсутствует, в основном `.env` нет `YANDEX_API_KEY/FOLDER_ID/GPT_MODEL`), это записано исполнителем в checkpoint и соответствует правилу «если ключа нет — часть ждёт владельца». Не замечание.

## Приложения

- **Команда тестов и итог:** `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2` → `Ran 224 tests in 3.614s`, `OK`.
- **Проверки Django:**
  - `.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings` → `System check identified no issues (0 silenced)`.
  - `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=ghostwriter.settings` → `No changes detected` (с предупреждением о недоступном хосте `db` — это следствие `.env` в корне проекта с `DB_HOST=db`; не блокирует проверку, миграции применяются к SQLite в тестах).
- **Скрипты мутаций в памяти:**
  - `C:\Users\lavro\AppData\Local\Temp\claude\c--Users-lavro-OneDrive-----------GitHub-Ghostwriter\9c671af9-0317-4a1a-a6b1-e29ca7afb24b\scratchpad\mutations_2a_2.py` — 4 мутации (ceiling / log provider / from None vs from e / verify kwarg) + probe перерасхода.
  - `C:\Users\lavro\AppData\Local\Temp\claude\c--Users-lavro-OneDrive-----------GitHub-Ghostwriter\9c671af9-0317-4a1a-a6b1-e29ca7afb24b\scratchpad\overrun_isolated.py` — изолированная проверка overrun на `GIGACHAT_DAILY_CALL_LIMIT=1`.
  Через `patch.object` + `override_settings` + `NoNetworkTestRunner.setup_databases/environment`. Рабочее дерево не менялось — `git diff --stat` до и после эксперимента совпал.
- **Файлы, которые ревью открывало:**
  - `plans/zapusk-demo-prompts/phase-2a-2-review.md`, `plans/zapusk-demo-prompts/phase-2a-2.md`, `plans/2026-10-06-zapusk-demo.md`;
  - `plans/zapusk-demo-reviews/plan-v5-security.md`, `plans/zapusk-demo-reviews/phase-2a-1.md`;
  - `generator/access.py`, `generator/forms.py`, `generator/gigachat_api.py`, `generator/models.py`, `generator/views.py`, `generator/yandexgpt_api.py`, `generator/yandex_image_api.py`, `generator/fastapi_client.py`;
  - `generator/templates/generator/gigagenerator.html`;
  - `generator/migrations/0020_rename_generator_g_operati_created_idx_generator_g_operati_fa3e9b_idx_and_more.py`, `generator/migrations/0021_provider_and_model_code.py`;
  - `ghostwriter/settings.py`, `ghostwriter/production_settings.py`, `ghostwriter/test_settings.py`;
  - `tests/helpers.py`, `tests/runner.py`, `tests/test_network_guard.py`, `tests/test_phase_2a_2.py`.
