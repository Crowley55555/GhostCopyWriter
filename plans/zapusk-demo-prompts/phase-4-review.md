# Фаза 4: независимое ревью — промпт ревьюера

Ты — независимый ревьюер фазы 4 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Фаза короткая: убрать со страниц OpenAI/бота/оплату/подписки, кнопка «Копировать», тест записи `IMAGE_GENERATION` без картинки, `__str__` токена без срока.

## Режим: только чтение

- Не изменяй рабочее дерево; никаких `git add/commit/stash/checkout/reset`.
- Единственный файл, который создаёшь, — отчёт `plans/zapusk-demo-reviews/phase-4.md`.
- Эксперименты — в памяти (`importlib`/`unittest.mock`) или в копии в `%TEMP%`. Способ запиши в отчёт.
- Не обращайся к сети, GigaChat, YandexGPT. `.env`, `.dev_token`, `ssl/` не читай и не выводи.
- Своих агентов не запускай.

## Что прочитать

1. `plans/2026-10-06-zapusk-demo.md`: «Фаза 4», «Checkpoint» — записи фаз 1 (ревью раунд 2 замечание 1), 2а.1 (textContent/showToast), 2а.2 (меню «Модель»), 3 и свежая от исполнителя фазы 4.
2. `plans/zapusk-demo-prompts/phase-4.md` — задание исполнителю (эталон).
3. Изменения: `git diff` относительно HEAD (`1072db5`).

## Что проверить

### Полнота удаления

- Прогон grep по `generator/templates/` и `generator/static/`:
  - `t\.me`, `telegram\.me`, `yookassa`, `подписк`, `оплат`, `поддержк`, `/support/`, `/reviews/`, `/payments/`, `track-subscription-click`, `subscription_tracking` — должно быть пусто (или только в закомментированном коде, если исполнитель так выбрал; оцени критически).
  - `openai`, `OpenAI`, `openai_tokens`, `#openaiUsed` — должно быть пусто в шаблонах и JS (в коде сервера могут оставаться имена полей модели — не замечание).
- Пройди по страницам через `Client` и проверь ответы: ни одно из слов выше в HTML.
- `subscription_tracking.js`: удалён или подключение снято из `index.html`; если оставлен — оправдано ли.

### Кнопка «Копировать»

- В `gigagenerator.html` есть кнопка.
- JS: `navigator.clipboard.writeText(...)` или fallback через временный `<textarea>`. Проверь, что JS не ломает страницу при отсутствии `navigator.clipboard`.
- Текст поста берётся через `textContent`, не `innerHTML`, чтобы не копировать разметку.
- `showToast` — через `textContent` (контракт 2а.1).

### Тест `IMAGE_GENERATION` без картинки

- Проверь, что есть тест на: ответ GigaChat без `<img>`/`data:image` или `download_image` → `None` → `generate_image_gigachat`:
  - возвращает `None`;
  - **пишет** строку `GigaChatTokenUsage.operation_type='IMAGE_GENERATION'`;
  - **списывает** расход с токена (`token.gigachat_tokens_used` увеличивается).
- Мутация «учитывать только при наличии картинки» ронит тест.

### `TemporaryAccessToken.__str__`

- `str(TemporaryAccessToken(expires_at=None))` не бросает. Тест есть или нет — если нет, это мелочь.

### Качество тестов

- Полная команда тестов — `OK`, число: 300 + N. Запусти.
- `manage.py check` чист.
- `makemigrations --check --dry-run` — чисто.
- Старые тесты не ослаблены.

### Границы

- Не тронуты: `generator/access.py`, `generator/middleware.py`, `generator/tariffs.py`, `generator/yandexgpt_api.py`, миграции, `tests/runner.py`, `idea/`.
- Коммитов нет: `git log origin/dev..HEAD` пустой.

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.
- Тесты: `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test <модули>`.

## Формат отчёта (`plans/zapusk-demo-reviews/phase-4.md`)

```
# Ревью фазы 4

Дата, ревьюер, что проверено (команды, мутации, способ).

## Вердикт
Принять / принять после исправлений / вернуть — одной строкой.

## Замечания
### N. Суть
- Серьёзность: блокирует / важно / мелочь
- Доказательство: файл:строка / вывод команды
- Сценарий сбоя
- Что изменить
- Как проверить

(Если замечаний нет — так и напиши.)

## Проверено и в порядке
Короткий список.

## Приложения
Команды, выводы.
```

В конце — одна короткая сводка (3–5 строк): вердикт, число замечаний, тесты, путь к отчёту. Детали — в отчёте.
