# Фаза 4: убрать лишнее из интерфейса — промпт исполнителя

Ты — исполнитель фазы 4 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Короткая фаза (0,5 дня): снять со страниц упоминания OpenAI, Telegram-бота, оплаты; кнопка «Копировать»; тест записи `IMAGE_GENERATION` без картинки; `__str__` токена без срока.

## Сначала прочитай

1. `CLAUDE.md`.
2. `plans/2026-10-06-zapusk-demo.md`:
   - «Фаза 4», «Границы и полномочия»;
   - «Checkpoint» — записи фаз 1 (ревью раунд 2, замечание 1 про IMAGE_GENERATION), 2а.2 (меню «Модель», ветка Flask снята), 3 (аутентификация).
3. Образцы прошлых промптов — `plans/zapusk-demo-prompts/phase-2a-3.md`, `plans/zapusk-demo-prompts/phase-3.md`.

`.env`, `.dev_token`, `ssl/` не читай и не выводи.

## Факты о коде (проверено оркестратором 2026-11-05, после фазы 3 — коммит `1072db5`)

- **Упоминания OpenAI на страницах:** `gigagenerator.html` имеет счётчик токенов OpenAI (`gigagenerator.html:46–53` в факте промпта; после правок 2а.2 номера строк могли сместиться — ищи по `openai`/`OpenAI`/`openai_tokens` в шаблоне). Меню «Модель» уже вместо `generator_type` (2а.2); проверь, что на странице не осталось видимого блока OpenAI.
- **Ссылки на Telegram-бота и оплату** — в `invalid_token.html`, `limit_exceeded.html`, возможно в `landing.html` и других шаблонах. Фаза 1 заменила часть на кнопку «Попробовать»; теперь нужно пройтись по всем страницам:
  - `grep -rn "t\.me\|telegram\.me\|yookassa\|подписк\|оплат\|поддержк\|support\|@bot\|/pay/" generator/templates/` — пройдись по каждому вхождению.
  - `grep -rn "track-subscription-click\|subscription_tracking" generator/templates/ generator/static/` — снять.
- **`subscription_tracking.js`** в `generator/static/` — проверь, подключён ли в `index.html`; если да и шлёт клики на снятый маршрут (404) — удали подключение из `index.html` (или сам файл, если точно нет других потребителей). Запиши в checkpoint, что сделано.
- **Кнопка «Копировать»** — у готового поста в `gigagenerator.html`. Простая JS-функция через `navigator.clipboard.writeText(...)`; текст поста берётся из элемента результата через `textContent`. Атрибут `aria-label="Скопировать пост"` для доступности.
- **`generate_image_gigachat`** в `generator/gigachat_api.py` — учитывает каждый состоявшийся вызов через `_account_gigachat_call` (замечание 1 ревью фазы 1 раунд 2 — исправлено). Нужен тест, что при `download_image` → `None` или ответе без картинки строка учёта всё равно пишется и расход списывается.
- **`TemporaryAccessToken.__str__`** в `generator/models.py:242` — сейчас `strftime` на `expires_at`; если `expires_at is None` — упадёт. Поправить: `expires = self.expires_at.strftime('%d.%m.%Y') if self.expires_at else 'без срока'`.
- **Текущий `[x]` список:** фазы 0, 1, 2, 2а.1, 2а.2, 2а.3, 3 закрыты.

## Что сделать (сначала падающие тесты, потом код)

### 1. Снять упоминания OpenAI со страниц

- В `gigagenerator.html` найти блок с `openai`/`OpenAI`/`openai_tokens` (счётчик токенов); удалить блок в разметке, соответствующий JS и обработку в `gigagenerator.html`/`index.html`; поле `openai_tokens_used` в сессии оставить (фаза 2а.2 его не трогала), просто не показывать. Если JS дёргает элемент `#openaiUsed` — убрать вызовы.
- Текст «Выберите генератор» или «OpenAI/GigaChat» — не должно остаться.

### 2. Снять ссылки на Telegram-бота, оплату, подписки, поддержку и отзывы через бота

- Пройти по `generator/templates/` и `generator/static/` с grep'ом: `t\.me`, `telegram\.me`, `yookassa`, `подписк`, `оплат`, `поддержк`, `/support/`, `/reviews/`, `track-subscription-click`.
- `invalid_token.html`, `limit_exceeded.html`: вместо ссылок на бота — кнопка «Попробовать» (POST на `/try/` с CSRF, как в `landing.html`). Фаза 1 уже это частично сделала (поиск `{% url 'try_demo' %}`); досверь.
- `landing.html`: нижние CTA и футер — если остались ссылки на бота, убрать.
- `subscription_tracking.js` — если только клики на снятый маршрут: снять подключение из `index.html` (если файл только для этого — удалить файл; если есть другие вызовы — оставить, убрать только снятый маршрут).
- Шаблоны со ссылками на `/support/create/`, `/reviews/create/`, `/payments/` и подобные (маршруты сняты в фазе 1) — убрать кнопки и ссылки.

### 3. Кнопка «Копировать»

- В `gigagenerator.html` возле готового поста — кнопка «Копировать» (`<button type="button" class="btn btn-sm ..." aria-label="Скопировать пост">`).
- JS через `navigator.clipboard.writeText(resultEl.textContent)`. На успех — `showToast('Скопировано', 'success')` (из 2а.1 toast уже на `textContent`). На ошибку — `showToast('Не удалось скопировать', 'danger')`.
- Если `navigator.clipboard` недоступен (старый браузер, HTTP без TLS) — fallback через временный `<textarea>` + `document.execCommand('copy')`. На выбор исполнителя; запиши решение в checkpoint.

### 4. Тест записи `IMAGE_GENERATION` без картинки (ревью фазы 1 раунд 2 замечание 1)

- Добавь тест в `tests/test_demo_access.py` или `tests/test_phase_4.py` (новый модуль — если создашь, впиши в команду тестов плана): `generate_image_gigachat` при `download_image` → `None` или ответе без `<img>`/`data:image`:
  - функция возвращает `None`;
  - **строка `GigaChatTokenUsage.operation_type='IMAGE_GENERATION'` записана**;
  - **расход с токена списан** (`token.gigachat_tokens_used` увеличился).
- Мутация «учитывать только при наличии картинки» ронит тест (это `_account_gigachat_call` вне ветки `if image_data`).

### 5. `TemporaryAccessToken.__str__` для токенов без срока

- Если `expires_at is None` — `strftime` падает. Поправить `__str__`: отобразить «без срока» или аналогично.
- Тест: `TemporaryAccessToken(token_type='REGISTERED', expires_at=None)` — `str(token)` возвращает строку без исключения.

### 6. Критерии (тесты)

- Тест-поиск: в ответах страниц `/`, `/token-required/`, `/invalid-token/`, `/limit-exceeded/`, `/profile/`, `/profile/edit/`, `/login/`, `/register/`, `/generator/` **нет** подстрок `t.me/`, `telegram.me`, `yookassa`, `OpenAI` (ищи case-insensitive), ссылок на оплату (`/payments/`, `/subscription-`) и поддержку через бота. `/generator/` требует вход — используй `TokenAuthMixin`.
- Тест разметки: кнопка «Копировать» присутствует в `gigagenerator.html` (можно проверить рендер страницы через `Client`).
- Тест страницы токена без срока в админке — открывается без ошибки: достаточно `str(TemporaryAccessToken(expires_at=None))` без исключения.
- `IMAGE_GENERATION` без картинки — см. п. 4.

### 7. Прогон

- Полная команда тестов: `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2 tests.test_phase_2a_3 tests.test_phase_3`. Добавил новый модуль — впиши.
- Было 300 → стало N (минимум +4–5 новых). Старые не удалять.
- `manage.py check --settings=ghostwriter.settings` — чисто.
- `makemigrations --check --dry-run --settings=ghostwriter.settings` — чисто (миграций в этой фазе нет).

## Ручная проверка

Если есть локальная БД и возможность запустить `runserver`:

- Обойти страницы: лендинг, `/try/`, генератор (после `/try/`), `/profile/`, `/profile/edit/`, `/login/`, `/register/`, `/token-required/`, `/limit-exceeded/`. На каждой — **нет** нерабочих кнопок (бот, оплата, подписка, поддержка).
- Кнопка «Копировать» — работает в десктоп-браузере; в консоли ошибок нет.

Если среда не позволяет — запиши в checkpoint «ручная проверка не выполнена: окружение», тесты закроют основные критерии.

Генерация реального GigaChat **не требуется** в этой фазе — тесты на моках.

## Границы

- **Разрешено менять:** `generator/templates/` (все шаблоны кроме тех, что относятся к другим фазам явно), `generator/static/subscription_tracking.js` (удаление/отключение), `generator/models.py` (только `__str__` токена), `tests/`, план (Checkpoint).
- **Запрещено:** `generator/forms.py` (кроме снятия ссылок, если в формах они), `generator/views.py` (кроме минимальных правок, если шаблон требует), `generator/access.py`, `generator/middleware.py`, `generator/tariffs.py`, миграции, `generator/yandexgpt_api.py`, `tests/runner.py`, `idea/`, `.env`, `.dev_token`, `ssl/`, `git add/commit/push/merge`.
- Генераций GigaChat/YandexGPT — 0 в этой фазе.
- Не больше 3 попыток на проверку.

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- Тесты (Git Bash): как в п. 7.
- `manage.py check --settings=ghostwriter.settings`; `makemigrations --check --dry-run`.

## Checkpoint и отчёт

Допиши в раздел «Checkpoint» плана одну запись в конце (не стирая):
- изменённые файлы (список);
- какие шаблоны очищены и какие маршруты были найдены (`grep`-сводка до и после);
- судьба `subscription_tracking.js` (удалён файл / отключён импорт / оставлен — с причиной);
- форма кнопки «Копировать» (clipboard API + fallback или без);
- итог тестов: было 300 → стало N;
- ручная проверка (или «не выполнена: окружение»).

Фазу `[x]` не отмечай.

В конце сессии — короткая сводка (3–5 строк): файлы, тесты, ручной прогон. Детали — в checkpoint, не в чат.
