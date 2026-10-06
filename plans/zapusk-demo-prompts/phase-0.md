# Фаза 0: зелёная база тестов — промпт исполнителя

Ты — исполнитель фазы 0 плана `plans/2026-10-06-zapusk-demo.md`. Работаешь в отдельной сессии. Ревью твоей работы проведёт оркестратор — другая сессия, поэтому своих рецензентов и агентов не запускай. Коммиты делает оркестратор после ревью.

## Сначала прочитай

1. `CLAUDE.md` в корне — правила проекта и безопасности.
2. `plans/2026-10-06-zapusk-demo.md` — разделы «Порядок исполнения», «Границы и полномочия», «Фаза 0», «Checkpoint».
3. `.starter/workflow.md`, раздел 4 — цикл фазы.

Папка `idea/` для этой фазы не нужна. Файлы `.env`, `.dev_token` и содержимое `ssl/` не читай и не выводи.

## Цель фазы

Набор тестов зелёный и проверяет текущее поведение продукта. Ни один тест не ходит в сеть и в GigaChat. Код продукта в `generator/` не меняется.

## Исходное состояние (проверено оркестратором 2026-10-06)

Команда тестов — 21 тест, 8 падений (FAIL) и 3 ошибки (ERROR):

- `tests.test_django_models`: `test_create_user_profile`, `test_user_profile_optional_fields`;
- `tests.test_django_isolated`: `test_models_creation`, `test_form_validation`, `test_generation_deletion`, `test_generation_detail_view`, `test_generator_completely_mocked`, `test_profile_management`, `test_quick_login_functionality`, `test_template_management`, `test_user_wall`.

Причины:

- Тесты входят по логину и паролю (`self.client.login`), а страницы теперь открываются по токену в сессии (`@token_required`, в продакшене ещё `TokenAccessMiddleware`). Отсюда `302 != 200` и редирект на `/token-required/`.
- Поля `UserProfile` удалены (`city`, `bio`, `first_name`) — `TypeError` и `AttributeError`.
- `test_quick_login_functionality` проверяет маршрут, который есть только при `DEBUG`, а в тестовых настройках `DEBUG = False`.

## Что сделать

1. **Подтверди исходное состояние.** Запусти команду тестов (см. «Окружение»), запиши число тестов и список упавших.
2. **Middleware как в продакшене.** В `ghostwriter/test_settings.py` добавь `'generator.middleware.TokenAccessMiddleware'` последним элементом `MIDDLEWARE` — так же, как в `ghostwriter/production_settings.py`.
3. **Предохранитель от сети.** Создай тестовый раннер в `tests/` (например, `tests/runner.py`, класс на основе `django.test.runner.DiscoverRunner`) и подключи его через `TEST_RUNNER` в `test_settings.py`. В `setup_test_environment` раннер ставит глобальные заглушки через `unittest.mock.patch`, в `teardown_test_environment` снимает их:
   - `generator.gigachat_api._init_client` и `generator.gigachat_api._init_direct_client` бросают исключение с текстом «Тест обратился к GigaChat без мока»;
   - `requests.sessions.Session.request` бросает исключение с текстом «Тест обратился к сети без мока».

   Тесты, которые сами мокают `generator.views.generate_text` и подобное, продолжают работать: их моки срабатывают раньше. Проверь предохранитель: временно убери мок в одном тесте и убедись, что тест падает с этим текстом. Затем верни мок.
4. **Перепиши упавшие тесты под текущее поведение.**
   - **Доступ** — через настоящий путь входа по токену: создай `TemporaryAccessToken` и открой `/auth/token/<uuid>/` (`token_auth_view` в `generator/views.py`). Если тесту нужны данные пользователя (стена, детали, удаление, шаблоны, профиль), создай токен с `telegram_user_id`: `token_auth_view` создаст пользователя Django `tg_<id>` и выполнит вход. Общий код вынеси во вспомогательную функцию или базовый класс в `tests/`.
   - **Профиль** — проверяй только поля, которые реально есть в `generator/models.py`.
   - **Не закрепляй дефект.** Не пиши тестов, которые проверяют, что анонимный посетитель видит анонимные генерации (ветка `user__isnull=True` в `user_wall_view`). Это известная утечка; её закрывает фаза 3.
   - **Не ослабляй.** Каждый переписанный тест проверяет то же намерение, что и раньше (например, «стена показывает генерации пользователя», «удаление удаляет»), а не только код ответа. Не заменяй проверки более слабыми.
   - **Удалять** можно только тест функции, которой больше нет. Сейчас это `test_quick_login_functionality`. Любое другое удаление — только с причиной в checkpoint и в отчёте.
5. **Финальная проверка.**
   - Команда тестов — `OK`, число тестов записано.
   - `git diff --stat -- generator/` — пусто.
   - `git status --short` — изменены только разрешённые файлы.
6. **Checkpoint.** Допиши в раздел «Checkpoint» плана одну запись, ничего не стирая: дата; изменённые и созданные файлы; команда и результат «было → стало»; удалённые тесты с причинами; тесты, которые фаза 3 переделает (стена, детали, удаление, шаблоны, профиль — там поменяются правила доступа); спорные решения. Фазу `[x]` не отмечай — это сделает оркестратор после ревью.

## Границы

- **Разрешено менять:** файлы в `tests/`, `ghostwriter/test_settings.py`, раздел «Checkpoint» в `plans/2026-10-06-zapusk-demo.md`.
- **Запрещено:**
  - любые файлы в `generator/`, другие настройки, `idea/`;
  - `git add`, `commit`, `push`;
  - сеть и GigaChat;
  - трогать и запускать `tests/test_flask_app.py` — Flask вне объёма.
- **Если тест не сделать зелёным без правки `generator/`,** не правь `generator/` и не прячь тест за `expectedFailure` или `skip`. Остановись на этом тесте, опиши причину в checkpoint и в отчёте.
- **Не больше 3 попыток** исправить одну и ту же проверку. Потом остановка и описание в отчёте.

## Окружение

Windows. Python из виртуального окружения проекта.

- PowerShell:
  `$env:DJANGO_SETTINGS_MODULE="ghostwriter.test_settings"; .venv\Scripts\python.exe manage.py test tests.test_django_models tests.test_django_isolated`
- Git Bash:
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated`

## Отчёт в конце (для оркестратора)

- Изменённые и созданные файлы.
- Итоговые строки вывода тестов до и после.
- Как проверен предохранитель.
- Удалённые тесты и причины.
- Спорные решения, сомнения, что осталось.
