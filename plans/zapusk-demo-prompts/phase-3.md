# Фаза 3: регистрация по логину и паролю — промпт исполнителя

Ты — исполнитель фазы 3 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Фаза средняя (2 дня): регистрация, вход, свои данные, лимиты регистраций и дневной лимит зарегистрированного. Работаешь в отдельной сессии. После тебя — ревью в отдельной сессии; решения примет оркестратор. Своих рецензентов и агентов не запускай. Коммиты делает оркестратор.

## Сначала прочитай

1. `CLAUDE.md` в корне.
2. `plans/2026-10-06-zapusk-demo.md`:
   - «Порядок исполнения», «Границы и полномочия», «Фаза 3»;
   - «Checkpoint» — записи фаз 0, 1, 2, 2а.1, 2а.2, 2а.3 (контракт токена, access.py, провайдерская защита, образцы в сессии);
   - таблица «Ревью версии 3» (пункты 1–4 про регистрацию) и таблица «Ревью версии 1» (пункт 7 про чужие данные).
3. `idea/principles.md`, `idea/mvp.md` версия 7 — читай, не меняй. Папка `idea/` в git, но править её нельзя.
4. `.starter/workflow.md`, раздел 4 — сначала падающий тест, потом код.
5. Образцы прошлых промптов и отчётов: `plans/zapusk-demo-prompts/phase-2a-3.md`, `plans/zapusk-demo-reviews/phase-2a-3.md`.

`.env`, `.dev_token`, `ssl/` не читай и не выводи.

## Факты о коде (проверено оркестратором 2026-11-04, после фазы 2а.3 — коммит `79fd8ff`)

- **`generator/models.py`:**
  - `UserProfile` (`:21–37`) — `OneToOneField(User)`, поля: `avatar`, `terms_accepted`. **Нет полей `business_info` и `samples`** — добавь их в миграции этой фазы.
  - `TemporaryAccessToken` (`:106–242`) — `token`, `token_type`, `telegram_user_id` (`:209`, `BigIntegerField`, nullable), `is_active`, `expires_at`, лимиты, `current_ip`. **Нет поля `user`** — добавь: `ForeignKey(User, on_delete=CASCADE, null=True, blank=True, related_name='access_tokens')`. Нужен также уникальный индекс на `user` при `token_type='REGISTERED'` (частичный) или проверка в коде + `UniqueConstraint` с условием.
  - `Generation` (`:40–74`) — `user` nullable, `null=True, blank=True` (демо). Поле не меняй; меняется только фильтрация в view.
  - `GenerationTemplate` — поищи по коду; тоже должен иметь `user` nullable (демо-посетитель создаёт шаблон без пользователя?). Сверь и запиши в checkpoint.
- **`generator/tariffs.py`:**
  - `TARIFF_CONFIGS` содержит `DEMO_FREE` (`:8`), `UNLIMITED` (`:38`), `HIDDEN_14D` (`:48`), `HIDDEN_30D` (`:58`), `DEVELOPER` (`:68`). Добавь `REGISTERED`:
    ```python
    'REGISTERED': {
        'name': 'Зарегистрированный пользователь',
        'duration_days': 365 * 10,   # условно долгоживущий
        'openai_tokens': 0,
        'gigachat_tokens_limit': -1,   # без лимита токенов — ограничивает только дневной потолок
        'daily_calls_limit': None,     # ставится в коде из env settings.REGISTERED_DAILY_CALL_LIMIT
        'is_hidden': True,
    },
    ```
    Точные ключи — по образцу существующих тарифов (`get_tariff_config()` возвращает dict).
- **`generator/views.py`:**
  - `register_view` (`:1029`) — сейчас заглушка.
  - `agreement_view` (`:1035`) — старый вид на основе сессии, не используется в фазе 3; **снять маршрут**, вид оставить в файле.
  - `quick_login` (`:175`) — DEBUG-only; **снять** из URLconf и шаблонов. Страницы входа и регистрации не используют его.
  - `edit_profile_view` — текущая заглушка возвращает редирект; **переделать** под редактирование `business_info`, `samples` (и обязательной галочки согласия? — оставь как есть). Шаблон профиля сделать минимальным.
  - **История**, **детали**, **удаление генераций**, **шаблоны** — сейчас есть ветка `user__isnull=True` (ревью версии 1, п. 7): все анонимы видят всё. Для фазы 3:
    - для `request.user.is_authenticated` — фильтр `user=request.user`;
    - для анонима — страницы профиля, истории, шаблонов показывают **предложение зарегистрироваться** (не 500). На стене и в деталях — только свои демо-записи, которые создала текущая сессия (по токену в сессии, фильтром `token=request.token` или `id__in=request.session.get('generations', [])`). Сверь ветвление и закрой.
  - **Шаблон** `gigagenerator.html:824`: сейчас имя шаблона настроек попадает в `innerHTML` как есть — XSS. Экранировать через `textContent` / `createElement` (подход как в 2а.1 с `showToast`).
- **`generator/middleware.py` → `TokenAccessMiddleware`:**
  - Правило доступа: если `request.user.is_authenticated`, токен берётся/создаётся через общую функцию сессии (из фазы 1 — `start_token_session`/`issue_demo_token` в `generator/access.py`), **демо-токен в сессии игнорируется**, `session.flush()` для вошедших не делается. Нужна новая функция `issue_or_get_registered_token(user)` в `access.py`, создающая/возвращающая токен типа `REGISTERED` для пользователя (`get_or_create` по `user`+`token_type='REGISTERED'`+`is_active=True`).
  - `/auth/token/` при `request.user.is_authenticated` → отказ (403 или редирект на профиль).
  - `/login/`, `/register/`, `/logout/` — в `exact_exempt_urls` middleware.
- **`generator/access.py` (из фаз 1 и 2а.2):**
  - `check_text_access(request, model_code, topic=..., business_info=..., samples=...)` — не ломать. Расширение для зарегистрированных:
    - дневной лимит зарегистрированного — скользящие 24 часа по строкам `GigaChatTokenUsage.objects.filter(user=request.user).count()`, значение из `settings.REGISTERED_DAILY_CALL_LIMIT` (новая настройка, env);
    - Pro и YandexGPT упираются и в свои общие провайдерские потолки (`check_provider_ceiling`).
  - `start_token_session` после фазы 1 раунда 1 использует `update_fields=['last_used', 'current_ip']` (ревью фазы 1 раунд 2 замечание 2) — сверь, что в текущем коде `access.py` это уже так. Если нет — исправь.
- **Регистрация — счётчик по IP:**
  - новый счётчик `AccessEvent` типа `REGISTER_ATTEMPT` (расширение существующей модели `AccessEvent`, не новая миграция): `ip_hash` + `created_at`. Лимит `settings.REGISTER_PER_IP_PER_DAY` (env). Проверка при `POST /register/`: считать успешные и неуспешные попытки, 429 если сверх лимита.
- **Шаблон базовый:**
  - `generator/templates/generator/index.html` (из 2а.1 — `showToast` на `textContent`), наследуется страницами. Добавь блок-условие: если `user.is_authenticated` — ссылка на профиль/выход, иначе — ссылки на вход/регистрацию.
- **Старые тесты:**
  - `TokenAuthMixin.login_by_token` в `tests/helpers.py` — создаёт `DEMO_FREE` токен, вход через `/auth/token/<uuid>/`. Для новых тестов регистрации нужна функция-помощник `register_and_login(client, username, password)` в `tests/helpers.py`.
- **Миграции:** `0020_rename_...` (дрейф, 2а.2), `0021_provider_and_model_code.py` (поля учёта, 2а.2). Твоя миграция — `0022_user_profile_business_info_samples_and_registered_token.py` (или короче): поля `UserProfile.business_info`, `UserProfile.samples`, поле `TemporaryAccessToken.user` (nullable `ForeignKey`), `UniqueConstraint(fields=['user'], condition=Q(token_type='REGISTERED', is_active=True))`.

## Что сделать (сначала падающие тесты, потом код)

### 1. Миграция и модели

- **`UserProfile`**: добавь поля `business_info = models.TextField(blank=True, default='')`, `samples = models.TextField(blank=True, default='')`. Константы длины — те же, что в фазе 2а.3 (`GENERATION_MAX_BUSINESS_INFO_LENGTH`, `GENERATION_MAX_SAMPLES_LENGTH`), проверяются в формах и `check_text_access` (уже есть).
- **`TemporaryAccessToken`**: добавь поле `user = models.ForeignKey(User, on_delete=CASCADE, null=True, blank=True, related_name='access_tokens', verbose_name='Пользователь')`. Добавь `UniqueConstraint(fields=['user'], condition=Q(token_type='REGISTERED', is_active=True), name='uniq_active_registered_token_per_user')` в `class Meta.constraints`.
- Миграция — одна, `0022_...`. Убедись: `makemigrations --dry-run --settings=ghostwriter.settings` — **только твоя миграция**, старый дрейф чист (закрыт в 2а.2).

### 2. Тариф `REGISTERED`

- В `generator/tariffs.py` — новый ключ `REGISTERED` в `TARIFF_CONFIGS`. `is_hidden=True` (чтобы не светился в публичных местах). `openai_tokens=0`, `gigachat_tokens_limit=-1` (без лимита токенов), `duration_days` — большой (10 лет), `daily_calls_limit=None` (тариф сам не несёт потолок — потолок приходит из `settings.REGISTERED_DAILY_CALL_LIMIT`).
- Если `TOKEN_TYPES` в модели — `CharField(choices=...)` — добавь `('REGISTERED', 'Зарегистрированный')` в `choices`. Сверь, что `can_use_gigachat()` и `consume_gigachat_tokens(n)` для `gigachat_tokens_limit=-1` работают как в фазе 1 (неограниченно, но пишут строку учёта). Если не работают — поправь.

### 3. `access.py`: `issue_or_get_registered_token` и дневной лимит зарегистрированного

- **`issue_or_get_registered_token(user)`** в `generator/access.py`:
  - ищет активный токен типа `REGISTERED` у `user`;
  - если нет — создаёт; возвращает токен.
  - `expires_at` — из `tariffs.get_tariff_config('REGISTERED')['duration_days']`.
- **`check_text_access` расширение**:
  - если `request.user.is_authenticated` — считает `GigaChatTokenUsage.objects.filter(user=request.user, created_at__gte=timezone.now()-ACCESS_WINDOW).count()`;
  - при `>= settings.REGISTERED_DAILY_CALL_LIMIT` — 429 с константой `MSG_DAILY_LIMIT_USER`;
  - провайдерские потолки (`check_provider_ceiling`) по-прежнему проверяются до и после очереди (2а.2);
  - демо-посетитель — старая логика (`settings.GIGACHAT_DAILY_CALL_LIMIT` и `check_provider_ceiling`).
- **`start_token_session`** — убедись, что `save(update_fields=['last_used', 'current_ip'])` вместо полного `save()` (замечание 2 ревью фазы 1 раунд 2).
- **Новая настройка** `REGISTERED_DAILY_CALL_LIMIT` в трёх файлах настроек. Значение по умолчанию — предложи по формуле (демо: 50, зарегистрированный: 150), запиши в checkpoint.

### 4. Регистрация и вход

- **`generator/forms.py`**: новая форма `RegisterForm(UserCreationForm)`:
  - поля `username`, `password1`, `password2`, `terms_accepted` (BooleanField, required=True);
  - без email;
  - валидаторы паролей — `AUTH_PASSWORD_VALIDATORS` из `settings.py` (сверь, есть ли, если нет — добавь стандартные Django).
- **`generator/views.py`**:
  - `register_view`: при GET — страница с формой; при POST — проверка IP-лимита (`REGISTER_PER_IP_PER_DAY`), валидация формы, создание пользователя (`user.set_password(cleaned_data['password1'])`, `user.save()`), создание `UserProfile`, создание активного токена `REGISTERED` через `issue_or_get_registered_token`, вход через `django.contrib.auth.login(request, user)` (смена ключа сессии — встроена в `login`), редирект на профиль.
  - `login_view`: пользуется `django.contrib.auth.forms.AuthenticationForm`. После входа — `login(request, user)` (смена ключа сессии). Выход GET-запросом **недоступен** — только POST через `/logout/`. Снять `logout_view` GET, оставить `logout_post_view` под `@require_POST`.
  - Старый `agreement_view` — не используется, маршрут снят. Шаблон `user_agreement.html` оставь в файлах (на случай возврата).
  - `quick_login` — маршрут снят. Шаблоны без `{% url 'quick_login' ... %}` (сверь grep'ом).
- **Правило доступа в middleware**:
  - в `TokenAccessMiddleware.__call__` (или `process_request`) — если `request.user.is_authenticated`:
    - `request.token = issue_or_get_registered_token(request.user)`;
    - **НЕ** читать `session['token_id']` для подстановки демо-токена;
    - НЕ `session.flush()`;
  - `/auth/token/` при `request.user.is_authenticated` → 403 (или редирект на `/profile/`). Проверить `token_auth_view`.
  - `/login/`, `/register/`, `/logout/` — в `exact_exempt_urls`.
- **Шаблоны**:
  - `generator/templates/generator/register.html` — форма регистрации, уведомление что хранится (логин, хэш пароля, «О бизнесе», образцы, посты, технические данные для защиты от злоупотреблений); без ссылок на несуществующие документы.
  - `generator/templates/generator/login.html` — форма входа.
  - `generator/templates/generator/index.html` (базовый): шапка с условным выводом — залогинен → ссылка профиля + выход (POST-форма), нет → ссылки «Вход» / «Регистрация».
  - **Снять** блоки `quick_login` из всех шаблонов. Снять ссылки `{% url 'quick_login' %}`.
  - **Из промпта**: `gigagenerator.html:824` — имена шаблонов настроек: сейчас список собирается через `innerHTML` + `${t.name}`; переписать через `createElement` + `textContent` для `name`, иконку — через `createElement('i')` с классом. Тест разметки — по образцу `ServerTextMarkupTests` фазы 2а.1, но для шаблонов настроек.

### 5. Свои данные (ревью версии 1, п. 7)

- **История**, **детали**, **удаление генераций**, **шаблоны**:
  - `request.user.is_authenticated`: фильтр `user=request.user`. Ветку `user__isnull=True` убрать.
  - анониму: редирект на страницу-заглушку «Зарегистрируйтесь, чтобы видеть историю» (не 500).
  - На стене демо-посетителя (`wall.html` или аналог) — показывать только свои демо-генерации по сессии/токену. Если такой логики нет — оставь показ пустой стены для всех анонимов (минимум — не светить чужое).
  - Шаблоны настроек `GenerationTemplate` — только свои для залогиненого; анониму — заглушка.
- Удаление чужого поста, шаблона: 404 вместо 403 (не разглашать существование чужого объекта).

### 6. Лимит регистраций по IP

- В `register_view` до создания пользователя:
  - `ip_hash = hash_ip(get_client_ip(request))`;
  - `count = AccessEvent.objects.filter(event_type='REGISTER_ATTEMPT', ip_hash=ip_hash, created_at__gte=timezone.now()-ACCESS_WINDOW).count()`;
  - `if count >= settings.REGISTER_PER_IP_PER_DAY: return 429 с страницей-заглушкой (можно переиспользовать `demo_limit.html` или сделать `register_limit.html`)`;
  - **каждую** попытку (успешную и неуспешную) писать как `AccessEvent.objects.create(event_type='REGISTER_ATTEMPT', ip_hash=ip_hash)`.
- `AccessEvent.event_type` — `CharField(choices=...)`. Добавь константу `REGISTER_ATTEMPT` в choices. Миграции на choices не нужно (только на поля), но проверь.
- Новая настройка `REGISTER_PER_IP_PER_DAY` в трёх файлах (по умолчанию 5).

## Обязательные тесты

Новые тесты — в `tests/test_phase_3.py` (новый модуль; добавь имя в команду тестов плана).

Критерии из «Фаза 3 → Критерии (тесты)» плана:

- Регистрация → вход → генерация сохраняется у пользователя → после выхода и входа пост, «О бизнесе» и образцы на месте.
- Тест разметки: имя шаблона настроек с `<img src=x onerror=alert(1)>` не попадает в `innerHTML` без экранирования; тест-поиск, аналогичный `ServerTextMarkupTests` 2а.1.
- Вход при живом демо-токене — дальше работает токен пользователя; деактивированный токен вошедшего заменяется без выхода из аккаунта; суперпользователь после `/admin/` открывает генератор; после выхода демо-токена в сессии нет.
- Пользователь B не открывает и не удаляет пост и шаблон пользователя A; демо-посетитель не видит ничьих постов; демо-посетитель на страницах профиля и шаблонов получает **предложение зарегистрироваться**, а не 500.
- Выход и вход не обнуляют дневной лимит; с подменой времени (`freezegun` или `timezone.now()` через mock) лимит восстанавливается через 24 часа; при общем потолке зарегистрированный тоже получает отказ.
- Ключ сессии меняется после входа (`session.session_key` до и после `login` отличается); пароля нет в данных сессии (сверка `dict(client.session)`); слабый пароль отклоняется формой; регистрации с одного IP сверх `REGISTER_PER_IP_PER_DAY` отклоняются. В тестах `SESSION_ENGINE='django.contrib.sessions.backends.db'` или `LocMemCache`, не `DummyCache`.
- Страницы входа и регистрации рендерятся при `DEBUG=False` (у нас тесты так и идут).
- Выход GET-запросом не срабатывает (POST — работает).
- `makemigrations --check --dry-run --settings=ghostwriter.settings` — без изменений после твоей миграции.
- **Мутации** (минимум 4):
  - убрать фильтр `user=request.user` в истории → тест «B не видит пост A» ронит;
  - убрать `logout POST`-only (`require_POST`) → тест «выход GET» ронит;
  - `register_view` писать `AccessEvent` **только** при успехе → тест IP-лимита с чередованием успех/отказ ронит;
  - убрать `session.cycle_key()` или `login()` → тест смены ключа ронит;
  - `issue_or_get_registered_token` создаёт **новый** токен каждый раз → тест «деактивированный токен заменяется» ронит.

## Ручная проверка

Если ключ GigaChat в `.env` работает и `.env` не переключает БД:

- Пройти цепочку: открыть `/register/`, зарегистрироваться (логин `demo_owner_test`, пароль сложный); увидеть профиль; пойти в генератор, создать пост с `business_info` и `samples`; выйти; войти; увидеть пост в истории; «О бизнесе» и образцы подставляются в форму.
- Атака XSS: шаблон настроек с именем `<img src=x onerror=alert(1)>` — в списке показывается как текст, не исполняется.
- Два аккаунта: B не видит стену A.

Если ключа нет или `.env` переключает БД — запиши «ручная проверка не выполнена: окружение».

**Лимит генераций всей фазы: GigaChat — до 10, YandexGPT — 0.** Из них 4–5 — на ручной сценарий регистрации/входа.

## Границы

- **Разрешено менять:**
  - `generator/models.py` — поля `UserProfile.business_info`, `UserProfile.samples`, `TemporaryAccessToken.user`, `UniqueConstraint`;
  - `generator/migrations/` — одна новая миграция `0022_...`;
  - `generator/tariffs.py` — тариф `REGISTERED`;
  - `generator/access.py` — `issue_or_get_registered_token`, расширение `check_text_access` на дневной лимит зарегистрированного, если ещё не было `start_token_session.save(update_fields=...)` — поправить;
  - `generator/middleware.py` — `TokenAccessMiddleware` — правило для залогиненого;
  - `generator/views.py` — `register_view`, `login_view`, `logout_view` (POST), `edit_profile_view`, `token_auth_view` (отказ при залогинeном), история/детали/шаблоны (фильтр по user);
  - `generator/forms.py` — `RegisterForm`, `UserProfileForm` (редактирование `business_info` и `samples`);
  - `generator/urls.py` — маршруты `/register/`, `/login/`, `/logout/`, `/profile/`, `/profile/edit/`; снять `quick_login` и `agreement_view`;
  - `generator/templates/generator/` — новые/обновлённые `register.html`, `login.html`, `index.html` (условная шапка), `profile.html`, `profile_edit.html`, экранирование имён шаблонов настроек в `gigagenerator.html`;
  - три файла настроек — `REGISTERED_DAILY_CALL_LIMIT`, `REGISTER_PER_IP_PER_DAY`; `AUTH_PASSWORD_VALIDATORS` при отсутствии;
  - `tests/helpers.py` — функция `register_and_login`;
  - `tests/test_phase_3.py` — новые тесты;
  - план — только «Checkpoint» и команда тестов (добавить `tests.test_phase_3`).
- **Запрещено:**
  - новая логика провайдеров / меню «Модель» / единый путь текста — это 2а.2, не ослаблять;
  - образцы: поля формы — добавляй в `UserProfileForm`, но контракт промпта и санитайзер в сборщике промпта **не трогай** (из 2а.3);
  - `tests/runner.py` — не ослаблять предохранитель;
  - лендинг и оформление — фаза 5;
  - импорт по ссылке — отложен в «Возможные доработки», не делать;
  - `idea/`, `.env`, `.dev_token`, `ssl/`;
  - `git add/commit/push/merge`;
  - новые зависимости времени выполнения.
- Не больше **3 попыток** исправить одну и ту же проверку.
- Генерации — **GigaChat до 10, YandexGPT 0**.

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- Тесты (Git Bash):
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2 tests.test_phase_2a_3 tests.test_phase_3`
  Добавил новый модуль — впиши сюда и в команду тестов в плане.
- Проверки:
  - `.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings`;
  - `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=ghostwriter.settings` — должна быть **только** твоя миграция до применения; **чисто** после применения.

## Checkpoint и отчёт

Допиши в раздел «Checkpoint» плана одну запись в конце (ничего не стирая):

- изменённые и новые файлы;
- новая миграция (имя, что содержит);
- значения `REGISTERED_DAILY_CALL_LIMIT`, `REGISTER_PER_IP_PER_DAY` + обоснование;
- форма `UniqueConstraint` для `TemporaryAccessToken.user+REGISTERED+is_active`;
- результат ручной проверки (или «не выполнена: окружение»);
- итог тестов: было 272 → стало N, `OK`;
- спорные решения.

Фазу `[x]` не отмечай.

В конце сессии — одна короткая сводка (3–5 строк): файлы, миграция, тесты, ручной прогон, спорные решения. Детали — в checkpoint.
