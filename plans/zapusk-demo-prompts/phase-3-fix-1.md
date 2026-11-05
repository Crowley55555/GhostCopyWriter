# Фаза 3, раунд исправлений 1 — промпт исполнителя

Короткий раунд: три точечные правки в `generator/views.py` и `generator/forms.py`. Повторное ревью не требуется (решение оркестратора — правки не поведенческие).

## Сначала прочитай

1. `CLAUDE.md`.
2. `plans/2026-10-06-zapusk-demo.md`:
   - «Checkpoint» — свежие записи 2026-11-05 (ревью фазы 3 и решения судьи — твоё задание оттуда).
3. `plans/zapusk-demo-reviews/phase-3.md` — отчёт ревью (контекст).

`.env`, `.dev_token`, `ssl/` не читай и не выводи. Своих агентов не запускай.

## Состояние

Основная ветка `dev` — HEAD `6488d94`. В дереве — незакоммиченные правки исполнителя фазы 3 (22 файла). Не удаляй их; добавляй поверх.

## Что сделать

### 1. Убрать автосохранение `business_info`/`samples` из `generator_view` (важное)

**Сверено 2026-11-05:** `generator/views.py:406–408`:
```python
profile.business_info = form_data.get('business_info', '') or ''
profile.samples = form_data.get('samples', '') or ''
profile.save(update_fields=['business_info', 'samples'])
```

Удали эти 3 строки (плюс любые `get_or_create(profile)` строки, которые остались только ради этого автосохранения — сверь по контексту). Логика сессионного сохранения ниже (`:410–417`, `request.session['business_info']` / `samples`) остаётся — она нужна для демо-посетителя.

**Тест** — в `tests/test_phase_3.py`, новый или расширенный:

```python
def test_profile_business_info_not_overwritten_from_generator_form(self):
    # 1. регистрация + вход
    # 2. явная правка профиля через /profile/edit/: business_info='Я — пекарня'
    # 3. POST на /generator/ с business_info='' (мок GigaChat)
    # 4. assert UserProfile.business_info == 'Я — пекарня'
```

**Мутация**: вернуть `profile.business_info = form_data.get('business_info', ...)` → тест должен ронять.

### 2. Убрать мёртвый `LoginForm` в `generator/forms.py` (мелочь)

**Сверено 2026-11-05:** `generator/forms.py:448` — `class LoginForm(AuthenticationForm)`. Проверь: используется ли он где-то, кроме `generator/views.py:21` (там импорт). Если `login_view` использует `AuthenticationForm` напрямую — `LoginForm` мёртв, убери и класс, и импорт. Если используется (как `form_class` где-то) — оставь, но запиши в checkpoint.

Если убираешь:
- удали класс в `forms.py`;
- удали `LoginForm` из `from .forms import ...` в `views.py:21`;
- проверь, что `login_view` корректно использует `AuthenticationForm`.

### 3. Убрать двойной `session.flush()` в `logout_view` (мелочь)

**Сверено 2026-11-05:** `generator/views.py:1083–1095`:
```python
@require_POST
def logout_view(request):
    ...
    logout(request)
    request.session.flush()   # ← избыточно: logout() уже делает flush
    messages.success(...)
    return redirect('landing')
```

Удали `request.session.flush()`. Добавь короткий комментарий перед `logout(request)`:
```python
# django.contrib.auth.logout() сам вызывает request.session.flush().
# Вторая очистка не нужна.
```

**Тест** — проверь, что критерий фазы 3 про «после выхода демо-токена в сессии нет» всё ещё работает (он уже есть в `tests/test_phase_3.py` — должен остаться зелёным).

### 4. Прогон

- Полная команда тестов:
  `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2 tests.test_phase_2a_3 tests.test_phase_3`
- Результат — `OK`, число — 299 (или 300 с новым тестом). Если упало — остановись и запиши в checkpoint.
- `manage.py check --settings=ghostwriter.settings` — чисто.
- `makemigrations --check --dry-run --settings=ghostwriter.settings` — чисто (миграции не трогай).

Запись в «Checkpoint» (не стирая):
- изменённые файлы;
- было `LoginForm` мёртвым или нет (результат сверки);
- итог тестов: было 299 → стало N.

Фазу `[x]` не отмечай — это делает оркестратор.

## Границы

- **Разрешено:** `generator/views.py`, `generator/forms.py`, `tests/test_phase_3.py`, план (только Checkpoint).
- **Запрещено:** всё остальное; миграции, настройки, шаблоны (кроме случая, когда `LoginForm` висит ещё в шаблоне — тогда минимальная правка), `tests/runner.py`, `idea/`, `.env`, `.dev_token`, `ssl/`, `git add/commit/push/merge`.
- Генераций GigaChat/YandexGPT — 0.
- Не больше 3 попыток на проверку.

## В конце

Коротко (3–5 строк): файлы, тесты было/стало, был ли `LoginForm` мёртвым, что осталось.
