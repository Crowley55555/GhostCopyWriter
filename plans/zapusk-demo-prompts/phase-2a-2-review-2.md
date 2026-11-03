# Фаза 2а.2, повторное ревью — промпт ревьюера

Ты — независимый ревьюер второго раунда фазы 2а.2 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Это **короткое повторное ревью** — проверка, что исполнитель раунда исправлений 1 закрыл три замечания первого ревью, не ослабив прежние проверки. Полный разбор фазы делал первый ревьюер; его отчёт — `plans/zapusk-demo-reviews/phase-2a-2.md`, не повторяй его работу.

## Режим: только чтение

- Не изменяй рабочее дерево; никаких правок кода, тестов и плана; никаких `git add/commit/stash/checkout/reset`.
- Единственный файл, который ты создаёшь, — отчёт `plans/zapusk-demo-reviews/phase-2a-2-round-2.md`.
- Эксперименты и мутации — в памяти через `importlib`/`unittest.mock` или в копии в `%TEMP%`. Основное дерево не трогай. Способ запиши в отчёт.
- Не обращайся к сети, GigaChat, YandexGPT. `.env`, `.dev_token`, `ssl/` не читай и не выводи.
- Своих агентов не запускай.

## Что прочитать

1. `plans/zapusk-demo-prompts/phase-2a-2-fix-1.md` — задание исполнителю раунда (эталон).
2. `plans/zapusk-demo-reviews/phase-2a-2.md` — первое ревью с тремя замечаниями.
3. `plans/2026-10-06-zapusk-demo.md`:
   - «Checkpoint» — записи от 2026-11-03: решения судьи и свежая запись исполнителя раунда исправлений;
   - «Фаза 2а.2» — критерии замечаний 1–5 ревью безопасности (для сверки, что фаза в целом цела).
4. `git diff <коммит перед раундом>..HEAD` — не нужен, работаем от незакоммиченных правок. Используй `git status`.

## Что проверить

### Замечания раунда 1 ревью 2а.2 — закрыты?

**1. `load_dotenv` только в `ghostwriter/settings.py`.**

- Запусти: `grep -rn "load_dotenv\|from dotenv" generator/ ghostwriter/`.
- Ожидание: ровно одно вхождение `load_dotenv` + один `from dotenv import load_dotenv` в `ghostwriter/settings.py`. Все остальные `.py` в `generator/` и `ghostwriter/` — чистые.
- В `generator/yandex_image_api.py` и `generator/fastapi_client.py` ранее `os.getenv` вызывался на уровне модуля — проверь, что теперь это ленивые функции или читается через `settings`. Побочных эффектов при импорте быть не должно.
- Тест `importlib.reload(generator.yandex_image_api)` с `mock.patch('dotenv.load_dotenv')` — мок не вызывается. То же для `generator.fastapi_client`.
- Мутация: вернуть `load_dotenv()` в один из файлов → соответствующий тест ронит.

**2. `check_provider_ceiling` перед каждым звеном картинки.**

- В `generator/views.py` в трёх местах — `generator_view` (ветка с `generate_image=on`), `generate_image_from_text`, `regenerate_image` — проверка `check_provider_ceiling(PROVIDER_GIGACHAT_LITE)` стоит **перед каждым** вызовом `generate_image_prompt_from_text` и `generate_image_gigachat`, а не один раз.
- Либо проверка встроена в сами функции в `gigachat_api.py` — проверь оба варианта.
- Тест: `GIGACHAT_DAILY_CALL_LIMIT=1`, `/generator/` с `model=gigachat-lite&generate_image=on`, фейк GigaChat успешно возвращает текст, затем успешно промпт картинки; картинка не должна вызваться. После запроса `GigaChatTokenUsage.objects.count()` **≤ 2** (текст + промпт), **не 3**. Либо: `fake_gigachat.image_calls == 0`.
- Мутация: убрать повторную проверку перед `generate_image_gigachat` → тест ронит.
- Прежние тесты (замечание 1 ревью безопасности — обход через `model=yandexgpt&generate_image=on`) — зелёные.

**3. `_PROVIDER_DEFAULT` убран.**

- В `generator/gigachat_api.py` нет константы `_PROVIDER_DEFAULT` и нет `provider or ...` в `log_token_usage`.
- `provider` — keyword-only required параметр **или** проверка на корректный `provider` с `logger.error` + return без создания строки — одна из двух форм.
- Все вызовы `log_token_usage` внутри `gigachat_api.py` и `yandexgpt_api.py` передают `provider=` явно.
- Тест: `log_token_usage(..., provider=None)` → `TypeError` или строка не создаётся + `ERROR` в логе (одна из форм, зафиксированная тестом).
- Мутация: вернуть `_PROVIDER_DEFAULT = 'gigachat-lite'` и `provider or _PROVIDER_DEFAULT` → тест ронит.

### Общая целостность

- Полная команда тестов: `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2`. Исходное — 224 после фазы 2а.2 (первое ревью). Должно быть **234** (по отчёту исполнителя раунда) или больше. Старые тесты не удалены; переделки — строже или нейтральны. Проверь, что `test_topic_and_platform_truncated` в `tests/test_demo_access.py` правильно адаптирован (`provider=PROVIDER_GIGACHAT_LITE`), не ослаблен.
- Защита фазы 1 цела: тесты в `tests/test_demo_access.py` зелёные.
- Критерии замечаний 1–5 ревью безопасности остались закрытыми: прогон соответствующих тестов — зелёный, мутации на ключевых путях ловятся. Полный перепрогон мутаций не нужен — только убедись, что замечания 1 (блокирующее) и 2 (учёт) не регрессируют (одна-две контрольные мутации).
- Границы: `tests/runner.py` не менялся; миграции `0020_*` и `0021_*` не менялись; `generator/models.py` не менялся; `idea/` не менялся; `.env`, `.dev_token`, `ssl/` не читались.
- Коммитов нет: `git log origin/dev..HEAD` пустой.

### Если нашёл новый дефект

- Если он создан именно этим раундом исправлений — отдельное замечание в отчёт (как в первом ревью).
- Если это дефект первого раунда, который рецензент пропустил, — тоже отдельное замечание, с пометкой «не связано с раундом исправлений».
- Если дефект относится к другой фазе — не замечание, но упомяни в разделе «Проверено и в порядке» для контекста.

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- Тесты (Git Bash): `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test <модули из команды тестов в плане>`.

## Формат отчёта (`plans/zapusk-demo-reviews/phase-2a-2-round-2.md`)

```
# Повторное ревью фазы 2а.2

Дата, ревьюер, что проверено (команды и итог, мутации и результат), способ эксперимента (копия/в памяти).

## Вердикт
Принять / принять после исправлений / вернуть — одной строкой и почему.

## Замечания раунда 1 — закрыты?
### 1. load_dotenv — закрыто / не закрыто (доказательство)
### 2. check_provider_ceiling — закрыто / не закрыто
### 3. _PROVIDER_DEFAULT — закрыто / не закрыто

## Новые замечания (если есть)
Нумерация подряд. Если новых замечаний нет — так и напиши.

## Проверено и в порядке
Короткий список.

## Приложения
Команды, выводы.
```

В конце сессии — одна короткая сводка: вердикт, что закрыто, число тестов, путь к отчёту. Детали — в отчёте.
