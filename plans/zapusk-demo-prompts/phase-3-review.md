# Фаза 3: независимое ревью — промпт ревьюера

Ты — независимый ревьюер фазы 3 плана `plans/2026-10-06-zapusk-demo.md` (версия 5.1). Фаза средняя: регистрация, вход, свои данные, лимиты. Главные угрозы — аутентификация (ключ сессии, пароль в сессии, слабый пароль, выход GET), доступ к чужим данным, XSS в именах шаблонов настроек, IP-лимит регистраций.

## Режим: только чтение

- Не изменяй рабочее дерево; никаких `git add/commit/stash/checkout/reset`.
- Единственный файл, который создаёшь, — отчёт `plans/zapusk-demo-reviews/phase-3.md`.
- Эксперименты и мутации — в памяти через `importlib`/`unittest.mock` или в копии в `%TEMP%`. Способ запиши в отчёт.
- Не обращайся к сети, GigaChat, YandexGPT. `.env`, `.dev_token`, `ssl/` не читай и не выводи. Своих агентов не запускай.

## Что прочитать

1. `plans/2026-10-06-zapusk-demo.md`: «Фаза 3» (действия, критерии), таблицы «Ревью версии 1» п. 7 и «Ревью версии 3» п. 1–4, Checkpoint — свежая запись исполнителя фазы 3.
2. `plans/zapusk-demo-prompts/phase-3.md` — задание исполнителю (эталон).
3. `plans/zapusk-demo-reviews/phase-2a-3.md`, `plans/zapusk-demo-reviews/phase-2a-2-round-2.md` — контракты предыдущих фаз (единый путь текста, `check_text_access`, образцы).
4. `idea/principles.md`, `idea/mvp.md` версия 7 — читай, не меняй.
5. Изменения: `git diff` относительно HEAD (`79fd8ff`).

## Что проверить

### Миграция и модели

- `UserProfile`: поля `business_info`, `samples` — текстовые, `blank=True`, `default=''`.
- `TemporaryAccessToken.user`: `ForeignKey(User, null=True, blank=True, on_delete=CASCADE)`; `UniqueConstraint(fields=['user'], condition=Q(token_type='REGISTERED', is_active=True))`. Если условие ограничения более слабое или широкое — замечание.
- Одна миграция `0022_...`; `makemigrations --check --dry-run --settings=ghostwriter.settings` после — чисто.

### Тариф `REGISTERED`

- Добавлен в `TARIFF_CONFIGS`; `gigachat_tokens_limit=-1`; `openai_tokens=0`; `is_hidden=True`; срок большой (`duration_days` ≥ 365).
- `can_use_gigachat()` и `consume_gigachat_tokens(n)` при `limit=-1` работают как раньше (неограниченно, но пишут строку учёта — фаза 1).

### Аутентификация

- `login(request, user)` вызывается после регистрации и в `login_view` — ключ сессии меняется (`SessionMiddleware.process_request` + `auth.login` делает `session.cycle_key()`).
- Пароль **нигде** не сохраняется в сессии (ни в `agreement`, ни в формы). `agreement_view` снят с маршрутов; код оставлен.
- `logout` **только POST** (`@require_POST`). GET → 405 или редирект без выхода. Протестируй через `Client.get('/logout/')`.
- Формы валидируют пароль через `AUTH_PASSWORD_VALIDATORS` (слабый пароль типа `12345` отклоняется).
- `quick_login` маршрут снят; в шаблонах нет `{% url 'quick_login' %}` — `grep -rn "quick_login" generator/templates/`.

### Правило доступа в middleware

- При `request.user.is_authenticated`:
  - `request.token = issue_or_get_registered_token(request.user)`;
  - демо-токен из сессии игнорируется;
  - `session.flush()` не вызывается;
- `/auth/token/<uuid>/` при залогиненом → 403 или редирект, демо-токен не ставится.
- `/login/`, `/register/`, `/logout/` в `exact_exempt_urls`.
- При деактивации текущего `REGISTERED`-токена пользователя (например, в админке) — `issue_or_get_registered_token` возвращает **новый** активный токен, пользователь не выброшен из аккаунта.

### Свои данные

- История (`/wall/` или `/history/`), детали генерации, удаление, шаблоны:
  - залогиненый — только свои (`filter(user=request.user)`); чужое — 404;
  - аноним — предложение зарегистрироваться (шаблон / редирект), не 500. Доказательство — тест.
- На стене демо-посетителя — не светить чужие посты. Если видно — замечание (был пункт 7 ревью версии 1).

### XSS в именах шаблонов настроек

- `gigagenerator.html:824` переписан: имя шаблона вставляется через `textContent` или `createElement`, не как часть HTML-строки.
- Тест: имя шаблона `<img src=x onerror=alert(1)>` рендерится как текст. Проверь источник: собранный JS выдаёт `.textContent = t.name`, не `.innerHTML +=`.
- Тест-поиск по шаблонам аналогичен `ServerTextMarkupTests` из 2а.1.

### Дневной лимит зарегистрированного

- `check_text_access` считает `GigaChatTokenUsage.objects.filter(user=request.user, created_at__gte=now-24h).count()` и сравнивает с `settings.REGISTERED_DAILY_CALL_LIMIT`.
- При исчерпании → 429 с константой.
- Выход и повторный вход не обнуляют счётчик (считается по user, не по сессии).
- При подмене времени через mock `timezone.now()` на +25 часов — лимит восстанавливается.
- Провайдерские потолки (`check_provider_ceiling`) по-прежнему проверяются для залогиненого; тест с исчерпанным `GIGACHAT_DAILY_CALL_LIMIT` и залогиненым пользователем → отказ.

### IP-лимит регистраций

- `AccessEvent` типа `REGISTER_ATTEMPT` пишется и при успехе, и при неуспехе.
- `settings.REGISTER_PER_IP_PER_DAY` проверяется **до** создания пользователя.
- Hash IP, не plain IP (через `hash_ip` из `access.py`).
- Тест с `LocMemCache`/БД-сессиями, не `DummyCache`.

### Качество тестов

- Полная команда тестов — `OK`, число — 272 + N (минимум 10–15 новых). Проверь, что старые 272 не удалены.
- Мутации (минимум 4):
  - убрать фильтр `user=request.user` в истории → тест ронит;
  - `logout` допускает GET → тест ронит;
  - `register_view` пишет `AccessEvent` только при успехе → тест IP-лимита ронит;
  - `login()` не вызывается (ручная `request.session['user_id'] = user.id`) → тест смены ключа ронит;
  - `issue_or_get_registered_token` создаёт новый токен каждый раз → тест «деактивированный заменяется» может пройти из-за уникального ограничения; проверь мутацией `ignore_conflicts=True`.
- `manage.py check --settings=ghostwriter.settings` — без замечаний.
- `makemigrations --check --dry-run` после — чисто.

### Границы

- Не тронуты: `generator/yandexgpt_api.py` (кроме места, где он читает `request.user` для учёта — сверь), `tests/runner.py`, лендинг, `idea/`, `.env`, `.dev_token`, `ssl/`.
- Нет новых зависимостей (`requirements.txt` не изменился или добавление оправдано).
- Коммитов нет: `git log origin/dev..HEAD` пустой.

### Ручная проверка

- `plans/2026-10-06-zapusk-demo.md` Checkpoint исполнителя сообщает, выполнено или нет; если нет — не замечание.

Не требуй того, что план относит к другим фазам (оформление — фаза 5, импорт по ссылке — доработки).

## Окружение

Windows. Python — `.venv\Scripts\python.exe`.

- Тесты (Git Bash): `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test <модули из команды тестов в плане>`.

## Формат отчёта (`plans/zapusk-demo-reviews/phase-3.md`)

```
# Ревью фазы 3

Дата, ревьюер, что проверено (команды и итог, мутации и результат), способ эксперимента.

## Вердикт
Принять / принять после исправлений / вернуть — одной строкой и почему.

## Замечания
### N. Суть
- Серьёзность: блокирует / важно / мелочь
- Доказательство: файл:строка или вывод команды
- Сценарий сбоя
- Что изменить
- Как проверить (тест или мутация)

(Нумерация подряд. Если замечаний нет — так и напиши.)

## Проверено и в порядке
Короткий список.

## Приложения
Команды, выводы.
```

В конце сессии — одна короткая сводка (3–5 строк): вердикт, число замечаний, число тестов, способ эксперимента, путь к отчёту. Детали — в отчёте.
