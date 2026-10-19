# Фаза 2а.2: меню «Модель» и YandexGPT — промпт исполнителя

Ты — исполнитель фазы 2а.2 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Работаешь в отдельной сессии. После тебя — ревью в отдельной сессии; решения по замечаниям примет оркестратор. Своих рецензентов и агентов не запускай. Коммиты делает оркестратор.

Это крупная фаза: вводит второго провайдера (YandexGPT), меню выбора модели, миграцию строки учёта, обобщает защиту фазы 1 на провайдеров и закрывает **пять замечаний ревью безопасности** (1 блокирующее, 4 важных). Делай последовательно, тестами, по пунктам.

## Сначала прочитай

1. `CLAUDE.md` в корне.
2. `plans/2026-10-06-zapusk-demo.md`:
   - «Порядок исполнения», «Границы и полномочия», «Фаза 2а.2» (включая 5 обязательных критериев в конце);
   - таблица «Ревью версии 5» — твои замечания 1, 2, 3, 4, 5;
   - «Checkpoint» — записи о фазах 1, 2 (защита, учёт, стоп-лист, постобработка) и 2а.1 (`GigaChatError`, `GIGACHAT_IMAGE_MODEL`, фиксы штампов).
3. `plans/zapusk-demo-reviews/plan-v5-security.md` — замечания 1, 2, 3, 4, 5 с деталями (эксперименты рецензента).
4. `idea/principles.md` (принцип 4 с исключением про YandexGPT) и `idea/mvp.md` версия 7 — читай, не меняй. Папка `idea/` в git, но править её нельзя.
5. `.starter/workflow.md`, раздел 4 — сначала падающий тест, потом код.
6. Образец промпта и отчёта предыдущей фазы — `plans/zapusk-demo-prompts/phase-2a-1.md` и `plans/zapusk-demo-reviews/phase-2a-1.md`.

Файлы `.env`, `.dev_token` и содержимое `ssl/` **не читай и не выводи**. Значения ключей не выводи. **Имена переменных в `.env`** читать можно только для записи в checkpoint, без значений.

## Факты о коде (проверено оркестратором 2026-10-20, после коммита фазы 2а.1 `6399c97`)

- **Модели (`generator/models.py`):**
  - `TemporaryAccessToken` (`:106`): поле `gigachat_tokens_limit`, `gigachat_tokens_used`, `openai_tokens_limit`, `openai_tokens_used`, метод `can_use_gigachat()` (`:251`), `consume_gigachat_tokens(n)` (`:295`), `consume_generation(ip_address)` (`:372`).
  - `GigaChatTokenUsage` (`:416`): `operation_type` (`TEXT_GENERATION`, `IMAGE_PROMPT`, `IMAGE_GENERATION`), `generation`, `user`, `token`, оценочные токены, `topic` (`max_length=255`), `platform` (`max_length=50`). **Нет полей `provider` и `model_code`.** Их нужно добавить миграцией этой фазы.
  - `AccessEvent` (`:593`): `event_type`, `ip_hash`, `created_at`.
- **Клиенты и промпт (`generator/gigachat_api.py`):**
  - `load_dotenv()` в `:26` (нужно убрать по замечанию 4 ревью безопасности).
  - `print` длины ключа в `:38–44` (образец, который для YandexGPT **не повторять**).
  - `_init_client(model=...)` берёт модель явно; `_init_direct_client` получает модель из `settings.GIGACHAT_IMAGE_MODEL` (сделано в 2а.1).
  - `_gigachat_limit_reached(token)` — только `can_use_gigachat()`, не смотрит потолок.
  - `_account_gigachat_call(token, tokens_used, **log_kwargs)` — списание и `log_token_usage`.
  - `log_token_usage` в `:634–636` ловит все ошибки через `print` (нужно `logger.error`).
  - Класс `GigaChatError` (из 2а.1): `.message`, `.status_code`.
  - Постобработка, стоп-лист, системный промпт — переиспользуются всеми провайдерами.
- **Доступ (`generator/access.py`):**
  - `check_gigachat_access(request, topic=..., result_text=..., business_info=...)` на `:187–208`: потолок считает `GigaChatTokenUsage.objects.filter(created_at__gte=...).count()` один раз (`:195–197`) и смотрит `GIGACHAT_DAILY_CALL_LIMIT`. **Знает только GigaChat.**
- **View (`generator/views.py`):**
  - `generator_type = request.POST.get('generator_type', 'gigachat')` на `:151`. Ветка Flask/OpenAI — `:158–193`. **Снимается этой фазой.**
  - В ветке GigaChat `check_gigachat_access(...)` стоит на `:197`; `generate_image=on` цепочка — `:221–227`.
- **Форма (`generator/forms.py`):** `GenerationForm` — `topic`, `platform`, `business_info`, 12 настроек. Нужно добавить поле `model`.
- **Шаблон (`generator/templates/generator/gigagenerator.html`):** переключатель `generator_type` — где-то в `:285–300` (сверь); на меню «Модель».
- **Тестовый раннер (`tests/runner.py`):**
  - Заглушки на `_init_client`, `_init_direct_client`, `requests.sessions.Session.request` (`:49–53`).
  - **Нет** заглушек на `socket.socket.connect`, `connect_ex`, `socket.create_connection`, `getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `httpx`, `urllib.request.urlopen` — замечание 3 ревью.
  - `UNGUARDED` сохраняет настоящие `_init_client` и `_init_direct_client`. Этот механизм — не ломать (его использует `test_init_client_passes_model`).
- **Настройки (`ghostwriter/settings.py`):**
  - `DEBUG = True` (`:27`).
  - `if os.environ.get('DB_HOST'):` на `:83` переключает на PostgreSQL. `env.example:24` содержит `DB_HOST=db` — если `load_dotenv()` переехать в `settings.py` без защиты, локальный `runserver`, `migrate`, `makemigrations --check` уйдут в PostgreSQL (замечание 4 ревью безопасности).
  - `GIGACHAT_MODEL`, `GIGACHAT_IMAGE_MODEL`, `GIGACHAT_DAILY_CALL_LIMIT`, `DEMO_GIGACHAT_TOKENS_LIMIT`, `DEMO_TOKENS_PER_IP_PER_DAY`, `BEHIND_PROXY`, `GENERATION_MAX_*` — читаются из env в `settings.py` и `production_settings.py`; в `test_settings.py` — константы.
- **Env (`env.example`, `env.production.example`):** содержат `GIGACHAT_*`, `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_GPT_MODEL` (из прошлых правок), `DB_*` и т. п. **Имена уже заготовлены** — читать `.env` в проекте владельца не нужно; сверка — по `env.example`.
- **Миграции:** на 2026-10-20 `makemigrations --dry-run --settings=ghostwriter.settings` показывает старый дрейф (13 `Rename index`, `telegram_user_id_hash`, `total_used`). Фаза 2а.2 начинает с миграции дрейфа отдельным коммитом.
- **Текущий статус тестов:** `Ran 190 tests`, `OK` (команда — ниже).

## Что сделать (сначала падающие тесты, потом код)

### 0. Подготовка: миграция дрейфа — отдельным коммитом **в начале**

- Прогон до правок: `makemigrations --check --dry-run --settings=ghostwriter.settings` — должен показать старый дрейф.
- Создай миграцию дрейфа: `makemigrations generator --settings=ghostwriter.settings`. Проверь, что она содержит **только** `Rename index`, удаление `telegram_user_id_hash`, изменение `total_used` — ничего другого.
- Проверь: `makemigrations --check --dry-run --settings=ghostwriter.settings` — чисто.
- **Исполнитель не коммитит**, но оркестратор ждёт, что миграция дрейфа лежит отдельным файлом в `generator/migrations/`, чтобы потом сделать два коммита: один с дрейфом, второй с 2а.2.
- Если `.env` в проекте владельца переключает локальную базу на PostgreSQL — не трогай БД владельца: временно переименуй `.env` на время `makemigrations`, выполни команду, верни `.env` на место. Способ выбери сам, запиши в checkpoint. Содержимое `.env` не читай и не выводи, только имена переменных.

**Этот шаг — предусловие** всех дальнейших, иначе `makemigrations --check` после 2а.2 упадёт.

### 1. Загрузка `.env` (замечание 4 ревью безопасности)

- В `ghostwriter/settings.py` в самом верху (сразу после `BASE_DIR = ...`): `from dotenv import load_dotenv; load_dotenv(BASE_DIR / '.env', override=False)`.
- В `generator/gigachat_api.py:26` — убрать `load_dotenv()`.
- `test_settings.py`, `production_settings.py`, `wsgi.py` — не трогать (убедись, что `load_dotenv` там нет и не появляется).
- Все клиенты (`gigachat_api`, новый `yandexgpt_api`) читают ключи **через `settings`**, не напрямую `os.environ`. Для GigaChat: `settings.GIGACHAT_CREDENTIALS`, `settings.GIGACHAT_CLIENT_ID`, `settings.GIGACHAT_CLIENT_SECRET`, `settings.GIGACHAT_SCOPE`. Если этих настроек ещё нет в `settings.py` — добавь (значения — `os.environ.get(...)`).
- В `test_settings.py` все ключи провайдеров — пустые строки. Тесты, которым нужен ключ, подставляют его через `override_settings`.
- **Образец печати длины ключа** (`gigachat_api.py:38–44`): можно оставить, но для YandexGPT не повторять. Если `print` длины ключа идёт только при импорте — он теперь выполнится в контексте настроек; это допустимо.
- **Перед включением** посмотри имена переменных в `.env` (без значений) и запиши в checkpoint, какие сменят поведение локально: `DB_HOST`, `DB_PASSWORD`, `DB_NAME`, `DB_USER`, `DB_PORT`, `DEBUG`, `ALLOWED_HOSTS`, `REDIS_URL` и т. п. Если `DB_HOST` установлен в `.env`, временно его защитить **через выбор миграции в п. 0** (`.env` переименован на время `makemigrations`).

### 2. Клиент YandexGPT (замечание 5 ревью безопасности)

Новый файл `generator/yandexgpt_api.py`:

- **API — Yandex AI Studio**, нативный `foundationModels.completion` (сверь по актуальной документации Yandex Cloud; ссылка и дата проверки — в checkpoint). Авторизация: `Authorization: Api-Key <ключ>`. URL — `https://llm.api.cloud.yandex.net/foundationModels/v1/completion`. Модель — `gpt://<folder_id>/<model_name>/latest`.
- Класс `YandexGPTError(Exception)` c `.message` и `.status_code` — такой же контракт, как у `GigaChatError` в `gigachat_api.py` (из 2а.1). Используется для единого `try/except` на уровне view.
- Функция `generate_text_yandex(form_data, user=None, token=None, generation_id=None)` — та же сигнатура, что `generate_text` в `gigachat_api`. Внутри строит те же сообщения через `assemble_prompt_from_criteria` или аналог из `gigachat_api` (чтобы системный промпт и пользовательское сообщение были **идентичны** между провайдерами).
- **Безопасность** (замечание 5):
  - сессия `requests.Session()`: `trust_env=False` (не берёт прокси/CA/.netrc из окружения);
  - на запросе: `verify=True` (не отключать), `allow_redirects=False`, явные таймауты соединения и чтения;
  - тело: `maxTokens` явный предел (например, 2000);
  - любое исключение транспорта (`requests.exceptions.*`, таймаут, OSError) → `raise YandexGPTError(message=MSG_GENERATION_FAILED, status_code=502) from None`. Ответ 4xx: аналогично, но для 429 — `status_code=429` и своё сообщение (ровно одно сообщение-константа на уровне view, не разные тексты).
  - в текст исключения, в логи и в ответ пользователю **не попадают** ключ, заголовки запроса и тело ответа. Логировать можно факт ошибки и код статуса; тело — не писать.
  - образец `print` длины ключа при импорте **не повторять**.
- Проверка ключа и каталога **до вызова HTTP**: `if not settings.YANDEX_API_KEY or not settings.YANDEX_FOLDER_ID: raise YandexGPTError(MSG_YANDEX_NOT_CONFIGURED, 400) from None`. На уровне view этот случай ловится и отвечает 400 (как `openai` в п. 3).

### 3. Форма и шаблон: меню «Модель»

- `generator/forms.py` — новое поле `model` в `GenerationForm`:
  - закрытый список: `MODEL_CHOICES = (('gigachat-lite', 'GigaChat Lite'), ('gigachat-pro', 'GigaChat Pro'), ('yandexgpt', 'YandexGPT'))`;
  - по умолчанию `gigachat-lite`;
  - при пустом — `gigachat-lite`.
- При отсутствии `YANDEX_API_KEY` или `YANDEX_FOLDER_ID` — пункт `yandexgpt` **не показывать в разметке** шаблона: собирай choices на стороне view (контекст `available_models`), а в форме допускается `yandexgpt`, но валидация и ответ view — проверяют доступность и отвечают 400.
- Запрос с `generator_type=openai` или модель вне списка → 400, ни один клиент не вызван.
- `generator/templates/generator/gigagenerator.html` — переключатель `generator_type` (OpenAI/GigaChat) заменить на меню «Модель» с тремя пунктами (или двумя при отсутствии ключа Яндекса). `generator_type` в разметке нет.

### 4. View — единый путь текста

- `generator/views.py:generator_view`:
  - ветка `generator_type=='openai'` (`:158–193`) **удаляется** с пути запроса (код функции `generate_text_and_prompt` в Flask-клиенте оставить в файле).
  - На входе читается `request.POST.get('model', 'gigachat-lite')`. Неизвестное значение, `openai`, `yandexgpt` без ключа — `JsonResponse({'success': False, 'error': MSG_MODEL_UNAVAILABLE}, status=400)`, ни один клиент не вызван.
  - По модели выбирается функция (`generate_text_gigachat` или `generate_text_yandex`); имя системного промпта и сообщение пользователя — те же. Единая `check_gigachat_access` переименовывается в `check_text_access` (или остаётся с добавлением аргумента `model_code`), и теперь ПРОВЕРЯЕТ ПРОВИДЕРСКИЕ ПОТОЛКИ. См. п. 5.
  - `try/except` вокруг цепочки — ловит `GigaChatError` и `YandexGPTError` одинаково (общий базовый класс `ProviderError` в `generator/providers.py` — на твой выбор, можно и явно два `except`). При ошибке — `JsonResponse({'success': False, 'error': err.message}, status=err.status_code)`; `Generation` не создаётся; следующие вызовы цепочки не выполняются (как в 2а.1).
- `regenerate_text` берёт `last_form_data['model']`; если ключа нет — модель по умолчанию (`gigachat-lite`).
- `generate_image_from_text` и `regenerate_image` — **всегда GigaChat**, независимо от выбранной модели (как указано в плане: картинки на YandexGPT не идут).

### 5. Защита фазы 1 — обобщить на провайдеров (замечание 1 — блокирующее)

Центральная задача фазы.

- **Переименуй** `check_gigachat_access` → `check_text_access` (или оставь имя, но измени смысл; выбор — в checkpoint). Сигнатура: `check_text_access(request, model_code, topic=..., business_info=...)` — модель передаётся явно.
- **Единая точка проверки потолка** знает модель и провайдер. Потолки:
  - `GIGACHAT_DAILY_CALL_LIMIT` — все вызовы GigaChat (сумма Lite + Pro + картинки);
  - `GIGACHAT_PRO_DAILY_CALL_LIMIT` — только текст Pro, **входит и в общий потолок GigaChat**;
  - `YANDEX_DAILY_CALL_LIMIT` — только YandexGPT.
  Значения по умолчанию выбирает исполнитель (`YANDEX_DAILY_CALL_LIMIT=50` — предложение). В `test_settings` — константы.
- **Проверка идёт по провайдеру ФАКТИЧЕСКОГО вызова, не выбранной модели пользователя** (замечание 1):
  - Перед `/generator/`: проверяем потолок текста (GigaChat или YandexGPT). Если модель — `yandexgpt` и в том же запросе `generate_image=on`, то **перед вызовом промпта картинки и картинки** — проверяем потолок GigaChat (это тот провайдер, который фактически будет вызван). Если потолок GigaChat исчерпан — промпт картинки и картинка не вызываются, в ответе `data.image_error` (как в 2а.1).
  - Это требование означает, что проверку нельзя делать только один раз в начале запроса. Решение: вводи функцию `check_provider_ceiling(provider_code)` → либо `None`, либо `ProviderError(MSG_DAILY_LIMIT_<PROVIDER>, 429)`. Вызывай её **в начале каждой функции цепочки** (`generate_text_gigachat`, `generate_text_yandex`, `generate_image_prompt_from_text`, `generate_image_gigachat`), в дополнение к уже имеющемуся `_gigachat_limit_reached` для токена. Либо выноси проверку в один помощник `_text_call_ok(token, provider_code)` и расширяй `_gigachat_limit_reached` на провайдера.
- **Лимит токена — один бюджет на все модели.** `TemporaryAccessToken.gigachat_tokens_limit` и `gigachat_tokens_used` используются и для YandexGPT, и для Pro. Переименовывать поля не нужно (большое изменение контракта миграции); можно либо оставить имя, либо добавить алиасы — на выбор, с запиской в checkpoint.
- **Строка учёта** `GigaChatTokenUsage` (замечание 2):
  - Миграция (вместе с миграцией этой фазы): добавить поля `provider` (`CharField(max_length=20, choices=...)` — закрытый список `('gigachat-lite', 'gigachat-pro', 'yandexgpt')`) и `model_code` (`CharField(max_length=100, blank=True, default='')`). `model_code` — короткое имя из закрытого списка констант кода (**не из env**), с обрезкой до `max_length`. Либо: переименовать модель в `ProviderTokenUsage`, добавить поля — но это бо́льшая миграция; оставь прежнее имя `GigaChatTokenUsage` и добавь поля (запиши в checkpoint «имя класса сохранено для меньшей миграции»).
  - `log_token_usage` принимает `provider`, `model_code` и пишет их в новые поля. **Значения из env в поля не идут.** Если захочется писать имя модели из env — добавь отдельное поле `provider_model_env` с обрезкой по `max_length`.
  - Ошибка `log_token_usage` — не `print`, а `logger.error('token usage logging failed', exc_info=True)` или `logger.exception(...)`.
- **Учёт вызова, пересёкшего лимит** (как в фазе 1 для GigaChat): для YandexGPT — такая же логика. Строка учёта пишется и для него, бюджет токена списывается.

### 6. Предохранитель тестов (замечание 3 ревью безопасности)

В `tests/runner.py`:

- Добавь заглушки:
  - `socket.socket.connect` (bound method на экземпляре → используй `patch` на классе);
  - `socket.socket.connect_ex`;
  - `socket.create_connection`;
  - `socket.getaddrinfo`;
  - `socket.gethostbyname`;
  - `socket.gethostbyname_ex`;
  - `httpx.Client.send` (или `httpx.HTTPTransport.handle_request`, на выбор — проверь, что перехватывает и sync, и async);
  - `urllib.request.urlopen`;
  - клиент YandexGPT: `generator.yandexgpt_api.<функция>` — такой же путь, как у GigaChat.
- Все — поднимают `NetworkAccessBlocked` (как сейчас GigaChat).
- `UNGUARDED` расширяется, если тест создания клиента YandexGPT проверяет аргументы (по образцу `test_init_client_passes_model`).

**Постоянный тест-страж** в `tests/test_network_guard.py` (новый модуль, добавить в команду тестов):

- `test_socket_connect_blocked`: сырой `socket.socket.connect((<192.0.2.1>, 80))` → `NetworkAccessBlocked`;
- `test_getaddrinfo_blocked`: `socket.getaddrinfo('example.com', 80)` → `NetworkAccessBlocked`;
- `test_urllib3_blocked_via_mocked_dns`: мокаем `socket.getaddrinfo` → `[('192.0.2.1', 80)]`, вызываем `urllib3.PoolManager().request('GET', ...)` → `NetworkAccessBlocked` (защита срабатывает на `socket.connect`);
- `test_httpx_blocked`: `httpx.get('https://example.com')` → `NetworkAccessBlocked`;
- `test_urllib_blocked`: `urllib.request.urlopen('http://example.com')` → `NetworkAccessBlocked`;
- `test_yandexgpt_client_blocked`: `yandexgpt_api.generate_text_yandex(...)` без мока → `NetworkAccessBlocked`.

Эти тесты **постоянные**, не удаляются.

### 7. Фейк YandexGPT в `tests/helpers.py`

По образцу `FakeGigaChat`: контекстный менеджер `fake_yandexgpt()` подменяет функцию клиента (не `requests`), считает вызовы, сохраняет сообщения. Атрибуты `.calls`, `.messages`. Используется в тестах.

### 8. Критерии (все 5 обязательных из плана)

Все новые тесты — в `tests/test_demo_access.py` и/или `tests/test_post_quality.py`; новые модули создать можно, добавь их имена в команду тестов плана.

**Критерий замечания 1 (блокирующее — обязательный):** потолок GigaChat исчерпан; `POST /generator/` с `model=yandexgpt` и `generate_image=on`. `fake_yandexgpt` вызван один раз, `fake_gigachat` — **ни разу**; в ответе текст и `data.image_error` (как в 2а.1 для лимита); мутация «перед вызовом картинки проверять только токен» ронит тест.

**Критерий замечания 2 (обязательный):** `postgres_varchar_lengths(GigaChatTokenUsage)` и `settings.YANDEX_GPT_MODEL = 'y' * 200` — строка учёта записывается (поле `provider='yandexgpt'`, `model_code='yandexgpt'` — короткое имя из закрытого списка). При потолке 1 второй запрос получает 429, `fake_yandexgpt` вызван один раз. Мутация «писать в `model_code` значение из env без обрезки» ронит тест.

**Критерий замечания 3 (обязательный):** постоянные тесты в `tests/test_network_guard.py` — см. п. 6. Не удаляются.

**Критерий замечания 4 (обязательный):** `importlib.reload(generator.gigachat_api)` с `mock.patch('dotenv.load_dotenv')` → мок **не вызывается**; в `test_settings` ключи провайдеров пустые. Ручная проверка `connection.vendor` до и после — SQLite (запиши в checkpoint).

**Критерий замечания 5 (обязательный):** фейковый транспорт YandexGPT бросает `ConnectionError`, в заголовках `test-key-ABC123`. Отрендеренный `ExceptionReporter(sys.exc_info()).get_traceback_html()` **не содержит `test-key-ABC123`** ни при `DEBUG=True`, ни при `False`. Мок `Session.request` проверяет, что клиент **не передаёт** `verify=False`. Мутация `from e` вместо `from None` ронит тест.

**Прочие обязательные тесты (из плана):**

- Для каждой из трёх моделей в фейк уходят **одинаковые** системный промпт и сообщение пользователя (сравнение строк между фейками через `fake_gigachat` и `fake_yandexgpt`); постобработка применяется (находит те же метки) и даёт одинаковый `clean_result` на одинаковом сыром ответе.
- Модель не из списка, `openai`, `yandexgpt` без ключа → 400, ни один фейк не вызван. Без ключа пункт `yandexgpt` в разметке отсутствует (тест разметки по шаблону); `generator_type` в разметке отсутствует.
- Защита фазы 1 для каждой модели: без токена, с исчерпанным лимитом токена, при потолке провайдера — ни один фейк не вызван. Вызов YandexGPT пишет строку учёта (с `provider='yandexgpt'`) и списывает бюджет. При потолке YandexGPT генерация на GigaChat работает, и наоборот. Pro упирается и в `GIGACHAT_PRO_DAILY_CALL_LIMIT`, и в `GIGACHAT_DAILY_CALL_LIMIT`.
- Ошибка YandexGPT (401, 429, таймаут) → `success: False`, `Generation` не создаётся, ключа нет в ответе и в логах теста (используй `assertLogs`).
- Перегенерация идёт в ту же модель; картинка при `yandexgpt` идёт в GigaChat.
- Мутации (минимум): снять проверку потолка YandexGPT в единой проверке → тест ронит; не писать `provider` в строку учёта → ронит; списывать бюджет Pro с другого токена → ронит; `from e` вместо `from None` → ронит.
- `makemigrations --check --dry-run --settings=ghostwriter.settings` после миграции 2а.2 — **без изменений** (дрейф закрыт в п. 0).

**Тесты фаз 0, 1, 2, 2а.1 не ослаблены.** Исходное число — 190 после коммита `6399c97`. Новые добавляются; переделки — строже.

### 9. Ручная проверка (сравнение трёх моделей)

Если ключи GigaChat и YandexGPT в `.env` доступны (значения не выводи):

- Прогон 10 тем (из `plans/zapusk-demo-reviews/phase-2-samples.md`, темы 1–10) на трёх моделях: Lite, Pro, YandexGPT.
- Сводка — дополни `plans/zapusk-demo-reviews/phase-2-samples.md` **новым разделом** «Сравнение трёх моделей (фаза 2а.2)»: для каждой темы — пост от каждой модели, штампы по `find_stop_phrases`, выдумки (цены/скидки/адреса/акции и прочие факты не из ввода), длина против нормы площадки, хэштеги, эмодзи, время ответа.
- **Лимит генераций всей фазы: GigaChat — до 25, YandexGPT — до 15.** В этом числе: Lite — до 10, Pro — до 10, запас 5; YandexGPT — 10 проб + 5 запас.
- **Стоимость YandexGPT** — по официальной странице тарифов Yandex AI Studio: сверь текущие цифры (стоимость за 1000 входных и выходных токенов), оцени среднюю цену одного поста (сравни с Lite и Pro). Ссылка и дата проверки — в checkpoint.
- Если ключ YandexGPT отсутствует — запиши в checkpoint «ручная часть YandexGPT не выполнена: ключа нет», сделай часть по GigaChat и закончи. Не ищи другие ключи, не обходи.

Решение по выбору модели по умолчанию и оценка «не стыдно показать» — за владельцем, не за исполнителем.

## Границы

- **Разрешено менять:**
  - `generator/gigachat_api.py` — убрать `load_dotenv`, добавить `check_provider_ceiling` или помощник, расширить `log_token_usage` на `provider`/`model_code`, учёт с новыми полями, `logger.error` вместо `print`;
  - `generator/views.py` — убрать ветку `openai` с пути, добавить выбор клиента по `model`, обобщить `try/except` на `GigaChatError`/`YandexGPTError`;
  - `generator/access.py` — переименовать/расширить `check_gigachat_access` → `check_text_access`, добавить `check_provider_ceiling`;
  - `generator/forms.py` — поле `model`, `MODEL_CHOICES`;
  - `generator/templates/generator/gigagenerator.html` — меню «Модель» вместо `generator_type`;
  - **новый файл** `generator/yandexgpt_api.py`;
  - **новый файл** `generator/providers.py` (общие константы `PROVIDER_*`, `MSG_*`) — на выбор, можно оставить в `gigachat_api`/`yandexgpt_api`;
  - `generator/models.py` — поля `provider`, `model_code` в `GigaChatTokenUsage` (и, при необходимости, миграция имён, но без переименования класса);
  - `generator/migrations/` — новая миграция 2а.2 (одна или две, см. п. 0);
  - `ghostwriter/settings.py` — `load_dotenv`, `YANDEX_*`, `GIGACHAT_PRO_MODEL`, потолки, `YANDEX_DAILY_CALL_LIMIT`, `GIGACHAT_PRO_DAILY_CALL_LIMIT`;
  - `ghostwriter/production_settings.py`, `ghostwriter/test_settings.py` — те же новые настройки (константы для тестов, env-чтение для прод);
  - `tests/runner.py` — расширение заглушек;
  - `tests/helpers.py` — `FakeYandexGPT`, `fake_yandexgpt`;
  - `tests/` — новые модули (`test_network_guard.py` и т. п.) и новые тесты в существующих модулях;
  - `plans/zapusk-demo-reviews/phase-2-samples.md` — новый раздел «Сравнение трёх моделей (фаза 2а.2)»;
  - в плане — только «Checkpoint» и команда тестов (при добавлении модуля).
- **Запрещено:**
  - Flask-клиент `generator.openai_api` или аналог — не удалять, только снимать с пути запроса;
  - `generator/models.py` в части `TemporaryAccessToken`, `AccessEvent`, `Generation` — только добавление, не изменение контракта;
  - `tests/test_demo_access.py` и `tests/test_post_quality.py` — старые тесты фаз 0–2а.1 не удалять и не ослаблять; переделки — строже и с запиской в checkpoint;
  - лендинг, страницы входа и регистрации, другие шаблоны кроме `gigagenerator.html` — не трогать;
  - `idea/`;
  - `.env`, `.dev_token`, `ssl/`;
  - `git add`, `commit`, `push`;
  - новые зависимости времени выполнения (сверь: клиент YandexGPT — на уже установленном `requests`).
- Не больше **3 попыток** исправить одну и ту же проверку.
- Генерации — **GigaChat до 25, YandexGPT до 15** (учти в checkpoint, сколько реально истратил).

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- Тесты (Git Bash):
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard`
  Добавил другой модуль — впиши сюда и в команду тестов в плане.
- Проверки:
  - `.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings`;
  - `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=ghostwriter.settings` — после 2а.2 должен быть чист (п. 0 закрыл старый дрейф, п. 5 добавил свою миграцию).
- Предохранитель тестов — не ослаблять; тесты, которым нужно соединение (например, TLS-эксперимент), снимают только `socket.socket.connect` явным `UNGUARDED` для `127.0.0.1`, но для 2а.2 это не требуется.

## Checkpoint и отчёт

Допиши в раздел «Checkpoint» плана одну запись в конце (ничего не стирая):

- изменённые и новые файлы;
- миграции (их две: дрейф + 2а.2; либо две — но оркестратор ждёт **миграцию дрейфа отдельным файлом**);
- выбор имени `check_text_access` vs расширение `check_gigachat_access` — с обоснованием;
- выбор формы учёта (новые поля в `GigaChatTokenUsage` vs отдельная модель) — с обоснованием;
- список провайдерских констант (значения `PROVIDER_*`) — ровно 3 строки;
- что покажет `makemigrations --check --dry-run --settings=ghostwriter.settings` до и после (а также результат временного переименования `.env`, если делал);
- ссылка и дата проверки документации Yandex AI Studio и прайса;
- итог тестов: было 190 → стало N (сверь, что не упало);
- итог ручного прогона 10 тем: сколько генераций потрачено, ссылка на раздел `phase-2-samples.md`;
- стоимость одного поста — Lite / Pro / YandexGPT;
- спорные решения.

Фазу `[x]` не отмечай.

В конце сессии — одна короткая сводка (3–5 строк): какие файлы, итог тестов, миграции, итог прогона, спорные решения, что осталось. Детали — в checkpoint. **В чат ничего не копируй**, кроме этой сводки.
