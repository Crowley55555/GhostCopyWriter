# Ревью фазы 3

Дата: 2026-11-05. Ревьюер: отдельная сессия Claude Code (Opus 4.7), только чтение. Фаза 3 — средняя (2 дня): регистрация по логину и паролю, вход, выход POST-формой, свои данные, дневной лимит зарегистрированного, IP-лимит регистраций, автосохранение «О бизнесе»/образцов в профиль. Главные угрозы — аутентификация (ключ сессии, пароль в сессии, слабый пароль, выход GET), доступ к чужим данным, XSS в именах шаблонов настроек, IP-лимит регистраций.

Правки исполнителя лежат как незакоммиченные относительно HEAD (`6488d94`); `git log origin/dev..HEAD` пустой; новые файлы — `generator/migrations/0022_user_profile_business_info_samples_and_registered_token.py` и `tests/test_phase_3.py` (26 тестов).

**Что прочитано.**
- `CLAUDE.md` (корень), `plans/2026-10-06-zapusk-demo.md` (Фаза 3 действия/критерии, таблицы «Ревью версии 1» п.7 и «Ревью версии 3» п.1–4, запись Checkpoint исполнителя 2026-11-04 полностью), промпт `plans/zapusk-demo-prompts/phase-3.md` и `plans/zapusk-demo-prompts/phase-3-review.md`, контракты предыдущих фаз (`plans/zapusk-demo-reviews/phase-2a-3.md`, `plans/zapusk-demo-reviews/phase-2a-2-round-2.md`).
- Code review (`git diff HEAD`): `generator/models.py` (`UserProfile.business_info`/`samples`, `TemporaryAccessToken.user`, индекс `['user','token_type','is_active']`, `UniqueConstraint(fields=['user'], condition=Q(token_type='REGISTERED', is_active=True))`, `AccessEvent.REGISTER_ATTEMPT`, choice `('REGISTERED','Зарегистрированный')`); `generator/migrations/0022_...py` (6 операций — AddField x3, AlterField x2, AddIndex, AddConstraint); `generator/tariffs.py:83–96` (тариф `REGISTERED`); `generator/access.py:7–9, 38–39, 101–153, 195–240, 306–365` (`issue_or_get_registered_token`, `check_text_access` + дневной лимит зарегистрированного по `GigaChatTokenUsage.filter(user=...)`, `start_token_session` c `update_fields=['last_used','current_ip']`, `MSG_DAILY_LIMIT_USER`); `generator/forms.py:372–404, 407–445, 448–459` (`RegisterForm(UserCreationForm)` без email + `terms_accepted` BooleanField с обязательным согласием; `UserProfileForm(ModelForm)` для `business_info`/`samples` с `MaxLengthValidator`; `LoginForm(AuthenticationForm)`); `generator/views.py:982–1095, 1112–1220, 1347–1399` (`register_view`, `login_view`, `@require_POST logout_view`, `profile_view`, `edit_profile_view`, `_anon_sees_registration_offer`, фильтр `user=request.user` в стене/деталях/удалении, блок `/auth/token/` для залогиненого); `generator/middleware.py` (ветка `is_authenticated` с `issue_or_get_registered_token`, демо-токен игнорируется, `session.flush()` не вызывается; `/login/`, `/register/`, `/logout/` в `exact_exempt_urls`; принудительная подстановка `access_token` в сессию для залогиненого); `generator/decorators.py` (`@token_required` и `@consume_generation` поддерживают залогиненого без flush; истёкший REGISTERED заменяется без выхода); `ghostwriter/urls.py` (маршруты `register`/`login` ведут на новые view, `quick_login` снят); `ghostwriter/settings.py:117–130, 279–284`, `ghostwriter/production_settings.py:83, 270–271`, `ghostwriter/test_settings.py:68, 192–193` (валидаторы паролей Django по умолчанию в prod и dev; `REGISTERED_DAILY_CALL_LIMIT=150`, `REGISTER_PER_IP_PER_DAY=5`); `generator/templates/generator/{register,login,profile,edit_profile,index}.html` (POST-форма Выйти, условная шапка, уведомление об этих хранимых данных); `generator/templates/generator/gigagenerator.html:825–917` (`renderTemplateDropdown` переписан на `createElement`+`textContent`); `tests/helpers.py` (функция `register_and_login`); `tests/test_django_isolated.py` (`test_profile_management` закрепляет новое поведение `/profile/edit/`); `tests/test_phase_3.py` (26 тестов, 9 классов).
- Команды:
  - `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2 tests.test_phase_2a_3 tests.test_phase_3` → `Ran 299 tests in 9.391s`, `OK`. Было 272 после 2а.3 → стало **299** (+27, старые не удалены).
  - `.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings` → `System check identified no issues (0 silenced)`.
  - `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=ghostwriter.settings` → `No changes detected` (одна RuntimeWarning о недоступном PostgreSQL — ожидаемо, миграции применяются из файлов).
  - `git log origin/dev..HEAD --oneline` → пусто (коммитов нет).
  - `grep -rn "quick_login\|agreement_view" generator/templates/` → пусто. `grep -rn "quick_login\|agreement_view" generator/views.py generator/urls.py ghostwriter/urls.py` → только комментарии «снят» в `views.py:181` и `urls.py:56`.
- **Способ эксперимента: в памяти** через `importlib`/`unittest.mock.patch` + `DiscoverRunner.setup_test_environment/setup_databases` + `DJANGO_SETTINGS_MODULE=ghostwriter.test_settings`. Файлы на диске не менялись; `%TEMP%`-копий проекта не делал. Мутационный скрипт — в scratchpad сессии: `C:\Users\lavro\AppData\Local\Temp\claude\c--Users-lavro-OneDrive-----------GitHub-Ghostwriter\9c671af9-0317-4a1a-a6b1-e29ca7afb24b\scratchpad\mutations.py`. Рабочее дерево (`git status`) до и после ревью совпал.

## Вердикт

**Принять.** Все главные угрозы фазы закрыты: `django.contrib.auth.login` в `register_view` и `login_view` даёт встроенную смену ключа сессии; пароль в сессии не сохраняется (тест закрепляет); `logout` только POST (`@require_POST`) — GET возвращает 405; слабый пароль отклоняется формой через стандартные `AUTH_PASSWORD_VALIDATORS` (тест с `@override_settings` в `test_settings`); чужие посты/детали/удаление/шаблоны недоступны (`get_object_or_404(..., user=request.user)` отдаёт 404, не раскрывая существование); имя шаблона настроек идёт в DOM через `nameSpan.textContent = t.name` + `createElement('i')`, старая строка-шаблон `innerHTML` + `${t.name}` снята. Миграция одна (`0022_...`), частичный `UniqueConstraint(fields=['user'], condition=Q(token_type='REGISTERED', is_active=True))` правильно оставляет NULL-user и неактивные дубликаты вне индекса; `makemigrations --check --dry-run` чист. 299/299 тестов зелёные; 5/5 обязательных мутаций ловятся (проверил в памяти). Границы соблюдены (`tests/runner.py`, лендинг, `idea/`, `.env`, `.dev_token`, `ssl/` не тронуты). Одно важное наблюдение (§1 ниже) — автосохранение `business_info`/`samples` в профиль после каждой успешной генерации молча перезаписывает значения, которые пользователь явно поставил через `/profile/edit/`; это спорное решение 7 исполнителя, зафиксированное в checkpoint — не блокирует запуск демо, но подлежит обсуждению перед релизом. Остальное — мелочи (§2–3).

## Замечания

### 1. Автосохранение `business_info`/`samples` тихо перезаписывает профиль

- Серьёзность: **важно**
- Доказательство: `generator/views.py:401–408`:
  ```python
  if request.user.is_authenticated:
      profile, _ = UserProfile.objects.get_or_create(user=request.user)
      profile.business_info = form_data.get('business_info', '') or ''
      profile.samples = form_data.get('samples', '') or ''
      profile.save(update_fields=['business_info', 'samples'])
  ```
  Выполняется в успешной ветке `generator_view` после каждого поста. На входе формы `initial` подставляет текущие значения из профиля (`:216–221`), но при POST значения берутся из `request.POST`.
- Сценарий сбоя: пользователь зашёл в `/profile/edit/`, записал `business_info='Семейная кофейня у метро'`, вернулся в генератор, случайно (или намеренно для одной темы) очистил поле «О бизнесе» в форме, сгенерировал пост. После успешной генерации `form_data.get('business_info','') or ''` вернёт пустую строку — `profile.business_info` перезапишется `''`. То же для `samples`. Пользователь не предупреждён; `/profile/edit/` и форма генератора ведут себя неявно связанно (оба пишут один и тот же объект).
- Что изменить: не трогать профильные поля из `generator_view` (писать только в сессию для анонима, как сейчас в `:410–417`). Поля профиля заполняет `/profile/edit/` — там явная форма. Критерий «после выхода и входа пост, О бизнесе и образцы на месте» в `FullCycleAfterRelogin.test_business_info_and_samples_persist` всё равно выполнится, т. к. тест редактирует профиль через `/profile/edit/`, а не через форму генератора. Альтернатива — писать в профиль только если текущее значение в профиле пустое (миграция поведения без потери данных).
- Как проверить: тест «отредактировал профиль через `/profile/edit/` → перешёл в генератор → удалил «О бизнесе» в форме → сгенерировал пост с моком → перезашёл → `profile.business_info` по-прежнему равен значению из `/profile/edit/`» — сейчас упадёт на последнем ассерте.

### 2. Мёртвый `LoginForm` в `generator/forms.py`

- Серьёзность: **мелочь**
- Доказательство: `generator/forms.py:448–459` определяет `LoginForm(AuthenticationForm)` (с полем `remember_me` и своими `error_messages`), но `login_view` в `generator/views.py:1057, 1063, 1077` использует `AuthenticationForm` напрямую (`from django.contrib.auth.forms import AuthenticationForm`). `grep -n "LoginForm" generator/views.py` возвращает только строку импорта в заголовке (`:21`). Поле `remember_me` не используется.
- Сценарий сбоя: несоответствие между определением формы и реальным use-case приведёт будущего разработчика к ошибке «а почему remember_me не работает?»
- Что изменить: либо подключить `LoginForm` в `login_view`, либо удалить его из `forms.py` и убрать импорт в `views.py:21`.
- Как проверить: `grep -n "LoginForm" generator/` → только определение и импорт.

### 3. Двойной `session.flush()` в `logout_view`

- Серьёзность: **мелочь**
- Доказательство: `generator/views.py:1083–1095`:
  ```python
  logout(request)
  request.session.flush()
  ```
  `django.contrib.auth.logout(request)` уже делает `request.session.flush()` (см. `django/contrib/auth/__init__.py`) — после него сессия пуста и ключ сброшен. Повторный `flush()` безвреден, но путает читателя кода.
- Сценарий сбоя: нет (поведение корректное).
- Что изменить: убрать строку `request.session.flush()` после `logout(request)`, оставив комментарий «logout сам делает flush». Или, наоборот, снять `logout(request)` и оставить `flush()` + `messages.success` — но тогда `auth.SESSION_KEY` вручную не снимается.
- Как проверить: `test_logout_requires_post` уже закрепляет итог (`SESSION_KEY not in session`); без `flush()` тест по-прежнему зелёный.

## Проверено и в порядке

- **Миграция.** `0022_user_profile_business_info_samples_and_registered_token.py`: шесть операций — `AddField user` (FK на `AUTH_USER_MODEL`, `null=True, blank=True, on_delete=CASCADE, related_name='access_tokens'`), `AddField business_info` (TextField, `blank=True, default=''`), `AddField samples` (TextField, `blank=True, default=''`), `AlterField event_type` с choice `REGISTER_ATTEMPT`, `AlterField token_type` с choice `REGISTERED`, `AddIndex ['user','token_type','is_active']`, `AddConstraint UniqueConstraint(fields=['user'], condition=Q(token_type='REGISTERED', is_active=True), name='uniq_active_registered_token_per_user')`. Зависимость от `migrations.swappable_dependency(settings.AUTH_USER_MODEL)` и `('generator', '0021_provider_and_model_code')` — верная. `makemigrations --check --dry-run --settings=ghostwriter.settings` после применения — `No changes detected` (RuntimeWarning о недоступном PostgreSQL ожидаем — проверка `migration_consistency` требует подключения к БД, у нас локально это невозможно; сама проверка на дрейф при этом отрабатывает).
- **`UniqueConstraint` — частичный, как и было в промпте.** `fields=['user']` + `condition=Q(token_type='REGISTERED', is_active=True)` — проверено в `generator/models.py:267–277` и в миграции `:78–85`. NULL-user не попадает (демо-токены и Telegram-токены без пользователя не конфликтуют с constraint), неактивные дубликаты — разрешены. Тест-защитник мутации — `RegisteredTokenTests.test_repeat_calls_do_not_pile_up_tokens`: подменил `issue_or_get_registered_token` на вариант «всегда `create()`» — второй вызов упал `IntegrityError` (constraint работает).
- **Тариф `REGISTERED`.** `generator/tariffs.py:83–96`: `gigachat_tokens=-1`, `openai_tokens=0`, `duration_days=3650`, `is_hidden=True`, `is_subscription=False`, `visible_in_bot=False`. `can_use_gigachat()` при `gigachat_tokens_limit=-1` возвращает `(True, None)` (`generator/models.py:300`), `consume_gigachat_tokens(n)` с `-1` пропускает проверку лимита, но строку учёта пишет (поведение фазы 1 сохранено).
- **`issue_or_get_registered_token(user)`.** `generator/access.py:195–240`: fast-path `TemporaryAccessToken.objects.filter(user=user, token_type='REGISTERED', is_active=True).first()`; при отсутствии — `transaction.atomic()` + `create(...)` с ловушкой `IntegrityError`, которая читает токен, созданный параллельным запросом. Тест `RegisteredTokenTests.test_repeat_calls_do_not_pile_up_tokens` проверяет 5 вызовов подряд → один pk, один активный токен. Мутация «всегда create» ловится (см. выше).
- **Дневной лимит зарегистрированного.** `generator/access.py:336–348`: при `request.user.is_authenticated` считается `GigaChatTokenUsage.objects.filter(user=request_user, created_at__gte=_window_start()).count()`, порог — `settings.REGISTERED_DAILY_CALL_LIMIT` (dev 150, test 150, prod 150). Проверка идёт **до** `check_provider_ceiling`, но после `token.can_use_gigachat` (у `REGISTERED` там всегда True из-за `-1`). Тест `DailyLimitPersistenceTests.test_relogin_does_not_reset_daily_limit` создаёт 3 записи `GigaChatTokenUsage`, проверяет 429 с `MSG_DAILY_LIMIT_USER`, выход → вход → счётчик не обнулён (`filter(user=...).count() == 3`). `test_limit_restored_after_24h` сдвигает `created_at` на 25 часов назад — лимит восстанавливается (`check_text_access` возвращает `None`). `test_provider_ceiling_also_hits_registered_user` — провайдерский потолок (`GIGACHAT_DAILY_CALL_LIMIT=1`) бьёт и по залогиненому (один чужой `GigaChatTokenUsage` блокирует запрос).
- **IP-лимит регистраций.** `generator/views.py:982–1046`: `AccessEvent.objects.filter(created_at__lt=_tz.now()-ACCESS_WINDOW).delete()` чистит старые записи до счёта; `_register_attempts_count(ip_hash)` считает `event_type='REGISTER_ATTEMPT'` + `ip_hash` + `created_at__gte=now-24h`; порог `settings.REGISTER_PER_IP_PER_DAY` (5). При превышении — `render(request, 'generator/demo_limit.html', status=429)`. `AccessEvent.objects.create(event_type=AccessEvent.REGISTER_ATTEMPT, ip_hash=ip_hash)` пишется **до** `form.is_valid()`-ветки (`:1019–1022`), то есть считаются и успехи, и неуспехи (защита от слабых паролей как обхода). IP хэшируется через `hash_ip(get_client_ip(request))` — HMAC-SHA256 с `SECRET_KEY`; в открытом виде IP не хранится. Тесты `RegisterIPLimitTests.test_mix_of_success_and_failure_counts` (2 неудачи + 1 успех + 1 попытка = 429) и `test_old_events_dropped` (запись 25 ч назад не мешает). Мутация «писать AccessEvent только при `form.is_valid()`» ловится — счётчик при двух неудачах остаётся 0 вместо 2.
- **Аутентификация.** `generator/views.py:1033, 1066, 1083`: `login(request, user, backend='django.contrib.auth.backends.ModelBackend')` в обеих view (регистрация и вход) — `django.contrib.auth.login` сам вызывает `session.cycle_key()`, что видно по `RegistrationFlowTests.test_login_changes_session_key` (ключ до `login` отличается от ключа после). `logout_view` обёрнут `@require_POST` (`views.py:1082`) — GET даёт 405, тест `test_logout_requires_post` закрепляет. Слабый пароль отклоняется формой: `test_register_rejects_weak_password` с `@override_settings(AUTH_PASSWORD_VALIDATORS=[...NumericPasswordValidator, CommonPasswordValidator, MinimumLengthValidator, UserAttributeSimilarityValidator...])` на `password='12345678'` — ответ 200 (форма с ошибкой), User не создан. В `ghostwriter/settings.py:117–130` и `production_settings.py:83–96` стандартные четыре валидатора Django активны; в `test_settings.py:68` — `[]`, но тесты фазы 3, которым нужно проверить сам факт отклонения, подставляют валидаторы через `@override_settings` (решение владельца 3, зафиксировано в checkpoint).
- **Пароль не в сессии.** `generator/views.py:1033, 1066`: `User.objects.create_user(username=..., password=form.cleaned_data['password1'])` — Django хэширует внутри `set_password`, в сессию ничего не пишется. `agreement_view` удалена (спорное решение 1): старый код брал пароль открытым текстом из `session['password']` (замечание 3 ревью версии 3), удаление честнее, чем «оставить вид и не маршрутизировать». Тест `test_password_not_stored_in_session` перебирает `dict(client.session)` — пароль не находится ни под одним ключом.
- **`quick_login` снят.** `grep -rn "quick_login" generator/templates/` → пусто. `grep -rn "quick_login" generator/views.py generator/urls.py ghostwriter/urls.py` → только два комментария «снят». Тест `TemplatesHaveNoQuickLoginReference.test_grep` обходит `generator/templates/` и проверяет отсутствие `{% url 'quick_login' %}` (регекс `url\s+['\"]quick_login['\"]`).
- **Правило доступа в middleware.** `generator/middleware.py:66–84`: `if request.user.is_authenticated: token = issue_or_get_registered_token(request.user); if token.is_expired(): token.is_active=False + save + заново issue`; `request.token = token`; принудительная запись `access_token`/`token_type`/`gigachat_tokens_*`/`openai_tokens_*`/`is_demo=False` в сессию (спорное решение 6 — нужно декораторам и view, которые читают из сессии; контракт демо-посетителя не ломается, он идёт в ветку `:86+`). `session.flush()` для залогиненого **не** вызывается (строка 84 возвращается сразу). `/login/`, `/register/`, `/logout/` в `exact_exempt_urls` (`middleware.py:47–53`) — middleware пропускает их до проверки `is_authenticated`, что правильно: без этого залогиненный после выхода (который сбросил сессию) не смог бы повторно зайти через `/login/`.
- **`/auth/token/<uuid>/` при залогиненом.** `generator/views.py:1366–1367`: первая проверка `if request.user.is_authenticated: return redirect('profile')`. Демо-токен в сессии не подменяется. `/auth/token/` в `exempt_urls` middleware (префикс), поэтому middleware **не** ставит REGISTERED-токен до вызова view — но и демо-токен из URL в сессию не кладётся. Тест `test_token_auth_view_blocked_for_authenticated` закрепляет (302 на `/profile/`; затем `/profile/` возвращает 200 и `session['access_token']` равен токену REGISTERED, не демо).
- **Деактивированный REGISTERED-токен заменяется без выхода.** `generator/middleware.py:70–73` и `generator/decorators.py:54–59, 125–128`: при `is_expired()` токен деактивируется (`save(update_fields=['is_active'])`), затем `issue_or_get_registered_token` создаёт новый. Тест `RegisteredTokenTests.test_deactivated_token_replaced_without_logout` закрепляет: `prev.is_active=False; save(); client.get('/profile/')` → 200, `SESSION_KEY` в сессии, у user есть новый активный REGISTERED-токен с другим pk.
- **`start_token_session` — `update_fields`.** `generator/access.py:124–129`: `access_token.save(update_fields=['last_used', 'current_ip'])`. Замечание 2 ревью фазы 1 раунд 2 закрыто. Тест `StartTokenSessionUpdateFieldsTests.test_parallel_consume_not_lost`: первый экземпляр токена в памяти; второй `consume_gigachat_tokens(42)` в БД; `start_token_session` над первым не затирает (в БД 42, не 0).
- **Свои данные.** `generator/views.py:1184–1220`: `user_wall_view`, `generation_detail_view`, `delete_generation_view` — все с `if not request.user.is_authenticated: return _anon_sees_registration_offer(request)` + `get_object_or_404(Generation, id=gen_id, user=request.user)` (404, не 403 — спорное решение исполнителя не разглашать существование чужого объекта, совпадает с подходом из промпта). Тесты `OwnDataIsolationTests.test_user_b_cannot_view_a_generation` (404), `test_user_b_cannot_delete_a_generation` (404, объект A не удалён), `test_user_b_wall_shows_only_own` (на `/wall/` нет тем A, после создания B — есть «B-тема»). Шаблоны (`save_template_view`/`load_template_view`/`delete_template_view`/`rename_template_view`/`set_default_template_view`, `views.py:1226–1341`) — все проверяют `request.user.is_authenticated` и фильтруют по `user=request.user`. Демо — `_anon_sees_registration_offer` возвращает 200 с приглашением «Зарегистрируйтесь», не 500 (тесты `AnonymousOffersRegistrationTests`).
- **XSS в именах шаблонов настроек.** `generator/templates/generator/gigagenerator.html:845–917`: `renderTemplateDropdown` переписан — `list.innerHTML = ''` только для очистки контейнера; имя шаблона собирается `const nameSpan = document.createElement('span'); nameSpan.textContent = t.name;` (`:863–866`); звёздочка «по умолчанию» — `document.createElement('i'); star.className = 'bi bi-star-fill text-warning'`; кнопки «переименовать/удалить/сделать по умолчанию» строятся через `createElement('button')` + `addEventListener` + `createElement('i')` (`:878–912`) — ни одной строки-шаблона с интерполяцией имени. Тест `MarkupTests.test_render_template_dropdown_uses_textContent` закрепляет: ищет `nameSpan.textContent = t.name` и `createElement('i')`, удаляет комментарии и проверяет отсутствие `${t.name}` и `innerHTML` (кроме строки `list.innerHTML = ''`). Атакующее имя `<img src=x onerror=alert(1)>` попадёт в DOM как текстовый узел.
- **Публичные страницы при `DEBUG=False`.** `PublicPagesWhenDebugFalse.test_login_page_renders` и `test_register_page_renders` — обе возвращают 200 и содержат слова «Вход» / «Регистрация». `test_settings.py:18` — `DEBUG=False`.
- **`makemigrations --check --dry-run`.** После миграции `0022_...` — `No changes detected`. Тест `MakemigrationsClean.test_dry_run_clean` запускает в subprocess с `ghostwriter.settings`, проверяет `returncode == 0`.
- **Границы.** `git diff HEAD --stat --name-only` показал 21 изменённый файл и 2 новых (`0022_*.py`, `tests/test_phase_3.py`); все в границах. `tests/runner.py`, лендинг (`landing.html`, `landing_view`), `idea/`, `.env`, `.dev_token`, `ssl/` не тронуты. `requirements.txt` не изменился (grep `git diff HEAD -- requirements.txt` пусто). `plans/2026-10-06-zapusk-demo.md` — только Checkpoint-запись исполнителя и команда тестов (`tests.test_phase_3` добавлен).
- **Мутации (5/5 ловятся).** Запустил в памяти через `unittest.mock.patch` + `DiscoverRunner`:
  1. `generation_detail_view` без фильтра `user=request.user` (`get_object_or_404(Generation, id=gen_id)`) → `OwnDataIsolationTests.test_user_b_cannot_view_a_generation` падает (ожидал 404, получает 200).
  2. `logout_view` без `@require_POST` → `RegistrationFlowTests.test_logout_requires_post` падает (GET возвращает 302 вместо 405, пользователь выходит GET-ссылкой).
  3. `register_view` пишет `AccessEvent` только при `form.is_valid()` → `RegisterIPLimitTests.test_mix_of_success_and_failure_counts` падает (`_attempts()` возвращает 0 после двух неудач вместо 2; четвёртая попытка проходит).
  4. `login_view` без `login(request, user)` (ручная `session['_auth_user_id'] = str(user.pk)`) → `RegistrationFlowTests.test_login_changes_session_key` падает (ключ сессии не меняется: `before == after`).
  5. `issue_or_get_registered_token` всегда `create(...)` без fast-path и без ловушки `IntegrityError` → `RegisteredTokenTests.test_repeat_calls_do_not_pile_up_tokens` падает с `IntegrityError: UNIQUE constraint failed` (partial UniqueConstraint не позволяет второй `create`).

## Приложения

### A. Команда тестов и итог

```
DJANGO_SETTINGS_MODULE=ghostwriter.test_settings PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test tests.test_django_models tests.test_django_isolated tests.test_demo_access tests.test_post_quality tests.test_network_guard tests.test_phase_2a_2 tests.test_phase_2a_3 tests.test_phase_3
Ran 299 tests in 9.391s
OK
```

Было 272 (после 2а.3) → стало 299 (+27 новых тестов, старые не удалены). Все модули в команде плана; `tests.test_phase_3` добавлен исполнителем в команду тестов плана.

### B. Проверки окружения

```
.venv/Scripts/python.exe manage.py check --settings=ghostwriter.settings
System check identified no issues (0 silenced).

.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=ghostwriter.settings
.../makemigrations.py:158: RuntimeWarning: Got an error checking a consistent migration history performed for database connection 'default': could not translate host name "db" to address: Name or service not known
No changes detected
```

RuntimeWarning — из-за `DB_HOST=db` в `.env` (контейнер PostgreSQL недоступен локально); сама проверка на drift отрабатывает — `No changes detected`.

### C. Мутационный скрипт

Путь: `C:\Users\lavro\AppData\Local\Temp\claude\c--Users-lavro-OneDrive-----------GitHub-Ghostwriter\9c671af9-0317-4a1a-a6b1-e29ca7afb24b\scratchpad\mutations.py`.

Итог (stdout):

```
Мутация 1 (detail_view без user-фильтра): прошёл=False (ожидаем False)
  OK: тест упал — мутация поймана
Мутация 2 (logout без require_POST): прошёл=False (ожидаем False)
  OK: тест упал — мутация поймана
Мутация 3 (register пишет AccessEvent только при успехе): прошёл=False (ожидаем False)
  OK: тест упал — мутация поймана
Мутация 4 (login_view без login()): прошёл=False (ожидаем False)
  OK: тест упал — мутация поймана
Мутация 5 (issue всегда создаёт новый): прошёл=False (ожидаем False)
  OK: тест упал — мутация поймана
```

### D. Состояние рабочего дерева

`git status` до и после ревью совпал: модифицированы 21 файл из границ фазы (`generator/access.py`, `generator/decorators.py`, `generator/forms.py`, `generator/middleware.py`, `generator/models.py`, `generator/tariffs.py`, `generator/templates/generator/{edit_profile,gigagenerator,index,login,profile,register}.html`, `generator/views.py`, `ghostwriter/{production_settings,settings,test_settings,urls}.py`, `plans/2026-10-06-zapusk-demo.md`, `tests/helpers.py`, `tests/test_django_isolated.py`), два новых файла (`generator/migrations/0022_user_profile_business_info_samples_and_registered_token.py`, `tests/test_phase_3.py`), `.claude/` как untracked (ревьюерская директория). Коммитов нет (`git log origin/dev..HEAD` пусто). Запрещённые файлы (`tests/runner.py`, `generator/templates/generator/landing.html`, `idea/`, `.env`, `.dev_token`, `ssl/`, `requirements.txt`) не тронуты.
