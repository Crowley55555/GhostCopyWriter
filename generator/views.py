# =============================================================================
# DJANGO IMPORTS
# =============================================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
# from django.contrib.auth.decorators import login_required  # Не используется в системе токенов
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.forms.models import model_to_dict
from datetime import datetime

# =============================================================================
# PROJECT IMPORTS
# =============================================================================
from .forms import GenerationForm, RegisterForm, LoginForm, UserProfileForm, UserEditForm
from .models import Generation, UserProfile, GenerationTemplate
from .gigachat_api import generate_text, generate_image_gigachat
from .yandex_image_api import generate_image as generate_image_yandex
from .fastapi_client import generate_text_and_prompt, generate_image
from .decorators import consume_generation, token_required

# =============================================================================
# THIRD PARTY IMPORTS
# =============================================================================
import os
import base64
import re
import requests

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_flask_api_status():
    """
    Проверяет доступность Flask API сервера
    
    Returns:
        bool: True если Flask API доступен, False в противном случае
    """
    try:
        flask_url = os.environ.get('FLASK_GEN_URL', 'http://localhost:5000')
        response = requests.get(f"{flask_url}/", timeout=2)
        return True
    except Exception as e:
        print(f"Flask API недоступен: {e}")
        return False

# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

def quick_login(request, username):
    """
    Быстрый вход для тестовых пользователей (только для разработки)
    
    Автоматически создает тестовых пользователей при первом обращении:
    - admin: суперпользователь для админ панели
    - test_user_1: Анна Петрова (Москва, контент-маркетолог)
    - test_user_2: Михаил Сидоров (СПб, SMM-менеджер)
    
    Args:
        request: HTTP запрос
        username (str): Имя пользователя (admin/test_user_1/test_user_2)
    
    Returns:
        HttpResponse: Редирект на соответствующую страницу
    """
    if request.method == 'POST':
        try:
            # Проверяем, что это разрешенный тестовый пользователь
            if username in ['admin', 'test_user_1', 'test_user_2']:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    # Автоматическое создание тестовых пользователей
                    if username == 'admin':
                        user = User.objects.create_superuser(
                            username='admin',
                            email='admin@example.com',
                            password='admin123',
                            first_name='Администратор',
                            last_name='Системы'
                        )
                    elif username == 'test_user_1':
                        user = User.objects.create_user(
                            username='test_user_1',
                            email='test1@example.com',
                            password='test123',
                            first_name='Анна',
                            last_name='Петрова'
                        )
                        # Создаем профиль пользователя
                        UserProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                'city': 'Москва',
                                'bio': 'Тестовый пользователь для разработки. Специалист по контент-маркетингу.'
                            }
                        )
                    elif username == 'test_user_2':
                        user = User.objects.create_user(
                            username='test_user_2',
                            email='test2@example.com',
                            password='test123',
                            first_name='Михаил',
                            last_name='Сидоров'
                        )
                        # Создаем профиль пользователя
                        UserProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                'city': 'Санкт-Петербург',
                                'bio': 'Второй тестовый пользователь для разработки. SMM-менеджер.'
                            }
                        )
                
                # Выполняем вход
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.first_name or user.username}!')
                
                # Редирект в зависимости от типа пользователя
                if username == 'admin':
                    return redirect('/admin/')  # Админ панель Django
                else:
                    return redirect('profile')  # Личный кабинет пользователя
            else:
                messages.error(request, 'Неверный пользователь для быстрого входа')
        except Exception as e:
            messages.error(request, f'Ошибка входа: {str(e)}')
    
    return redirect('login')

# =============================================================================
# CONTENT GENERATION VIEWS
# =============================================================================

@consume_generation
def generator_view(request):
    """
    Основная функция генерации контента
    
    Поддерживает два типа генераторов:
    1. GigaChat (российский AI) - по умолчанию
    2. OpenAI + DALL-E (через Flask API)
    
    Обрабатывает AJAX запросы для динамической генерации
    Сохраняет результаты в базу данных для отображения на стене пользователя
    
    Args:
        request: HTTP запрос с параметрами генерации
    
    Returns:
        JsonResponse: Для AJAX запросов
        HttpResponse: Для обычных запросов с рендером шаблона
    """
    # Инициализация переменных
    result = None
    image_url = None
    limit_reached = False
    form = GenerationForm(request.POST or None)
    generator_type = request.POST.get('generator_type', 'gigachat')  # Новый параметр
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if form.is_valid():
            try:
                form_data = form.cleaned_data.copy()
                if generator_type == 'openai':
                    # Проверяем доступность Flask API
                    if not check_flask_api_status():
                        if is_ajax:
                            return JsonResponse({
                                'success': False, 
                                'error': 'Flask Generator не запущен. Запустите Flask приложение на порту 5000.'
                            })
                        else:
                            result = "ERROR: Flask Generator не запущен. Запустите Flask приложение на порту 5000."
                            image_url = None
                    else:
                        try:
                            # Генератор через Flask API
                            gen_result = generate_text_and_prompt(form_data)
                            result = gen_result.get('text')
                            image_prompt = gen_result.get('image_prompt')
                            image_url = generate_image(image_prompt) if image_prompt else None
                        except Exception as e:
                            print(f"Ошибка Flask API: {e}")
                            if is_ajax:
                                return JsonResponse({
                                    'success': False, 
                                    'error': f'Ошибка Flask API: {str(e)}'
                                })
                            else:
                                result = f"ERROR: Ошибка Flask API: {str(e)}"
                                image_url = None
                else:
                    # Старый генератор Gigachat
                    result = generate_text(form_data)
                    from .gigachat_api import generate_image_prompt_from_text
                    image_prompt = generate_image_prompt_from_text(result, form_data) if result else None
                    if image_prompt:
                        image_data = generate_image_gigachat(image_prompt)
                    else:
                        image_data = generate_image_gigachat(form_data.get('topic', ''))
                    if image_data:
                        if image_data.startswith("data:image"):
                            import uuid
                            filename = f"generated_{uuid.uuid4().hex[:8]}.jpg"
                            full_path = os.path.join(settings.MEDIA_ROOT, filename)
                            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                            base64_data = image_data.split(',')[1]
                            image_bytes = base64.b64decode(base64_data)
                            with open(full_path, "wb") as f:
                                f.write(image_bytes)
                            image_url = settings.MEDIA_URL + filename
                        elif image_data.startswith("http"):
                            image_url = image_data
                        else:
                            filename = f"generated_{form_data.get('topic', '')[:20].replace(' ', '_')}.jpg"
                            full_path = os.path.join(settings.MEDIA_ROOT, filename)
                            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                            try:
                                image_bytes = base64.b64decode(image_data)
                                with open(full_path, "wb") as f:
                                    f.write(image_bytes)
                                image_url = settings.MEDIA_URL + filename
                            except Exception as e:
                                image_url = None
                gen = Generation.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    topic=form_data.get('topic', ''),
                    result=result,
                    image_url=image_url or ""
                )
                # Сохраняем ID генерации в сессии для последующих перегенераций
                request.session['current_generation_id'] = gen.id
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'result': result,
                        'image_url': image_url,
                        'limit_reached': limit_reached,
                        'generation_id': gen.id
                    })
            except Exception as e:
                print(f"Ошибка генерации: {e}")
                if is_ajax:
                    return JsonResponse({'success': False, 'error': str(e)})
        else:
            if is_ajax:
                errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
                return JsonResponse({'success': False, 'error': 'Некорректно заполнена форма', 'form_errors': errors})
    # Проверяем, является ли токен DEMO
    is_demo = request.session.get('is_demo', False)
    
    return render(request, 'generator/gigagenerator.html', {
        'form': form, 
        'result': result, 
        'image_url': image_url, 
        'limit_reached': limit_reached,
        'is_demo': is_demo
    })

# =============================================================================
# REGENERATION FUNCTIONS
# =============================================================================

@csrf_exempt
def regenerate_text(request):
    """
    Перегенерация только текста для существующей записи
    
    Обновляет существующую запись Generation, добавляя новую версию текста
    с разделителем. Использует ID генерации из сессии для обновления.
    
    Args:
        request: AJAX POST запрос с темой
    
    Returns:
        JsonResponse: Результат перегенерации или ошибка
    """
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            topic = request.POST.get('topic')
            # Здесь можно добавить обработку новых критериев, если нужно
            if not topic:
                return JsonResponse({
                    'success': False,
                    'error': 'Не все необходимые данные предоставлены'
                })
            # Создаем словарь с данными для генерации
            form_data = {
                'topic': topic
                # Добавить новые критерии, если нужно
            }
            # Генерируем новый текст
            result = generate_text(form_data)
            
            # Обновляем существующую запись или создаем новую
            generation_id = request.session.get('current_generation_id')
            if generation_id:
                try:
                    gen = Generation.objects.get(id=generation_id)
                    # Добавляем разделитель и новый текст
                    gen.result += f"\n\n--- Перегенерация {gen.result.count('--- Перегенерация') + 1} ---\n\n{result}"
                    gen.save()
                except Generation.DoesNotExist:
                    # Если запись не найдена, создаем новую
                    gen = Generation.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        topic=topic,
                        result=result,
                        image_url=""
                    )
                    request.session['current_generation_id'] = gen.id
            else:
                # Создаем новую запись, если нет ID в сессии
                gen = Generation.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    topic=topic,
                    result=result,
                    image_url=""
                )
                request.session['current_generation_id'] = gen.id
            return JsonResponse({
                'success': True,
                'result': result,
                'message': 'Текст успешно перегенерирован'
            })
        except Exception as e:
            print(f"Ошибка при перегенерации текста: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    return JsonResponse({
        'success': False,
        'error': 'Метод не поддерживается'
    })

def update_generation_image(request, topic, image_url):
    """
    Вспомогательная функция для обновления изображения в существующей генерации
    
    Добавляет новое изображение к существующей записи Generation, используя
    символ '|' как разделитель между URL изображений. Если записи нет,
    создает новую.
    
    Args:
        request: HTTP запрос (для доступа к сессии)
        topic (str): Тема генерации
        image_url (str): URL нового изображения
    """
    generation_id = request.session.get('current_generation_id')
    
    if generation_id:
        try:
            gen = Generation.objects.get(id=generation_id)
            # Добавляем новое изображение к существующим
            if gen.image_url:
                gen.image_url += f"|{image_url}"
            else:
                gen.image_url = image_url
            gen.save()
        except Generation.DoesNotExist:
            # Создаем новую запись, если старая не найдена
            gen = Generation.objects.create(
                user=request.user if request.user.is_authenticated else None,
                topic=topic,
                result="",
                image_url=image_url
            )
            request.session['current_generation_id'] = gen.id
    else:
        # Создаем новую запись, если нет ID в сессии
        gen = Generation.objects.create(
            user=request.user if request.user.is_authenticated else None,
            topic=topic,
            result="",
            image_url=image_url
        )
        request.session['current_generation_id'] = gen.id

@csrf_exempt
def regenerate_image(request):
    """
    Перегенерация только изображения для существующей записи
    
    Генерирует новое изображение на основе темы и добавляет его к существующей
    записи Generation. Поддерживает несколько форматов изображений (base64, URL).
    
    Args:
        request: AJAX POST запрос с темой
    
    Returns:
        JsonResponse: URL нового изображения или ошибка
    """
    if request.method == 'POST':
        try:
            topic = request.POST.get('topic')
            
            if not topic:
                return JsonResponse({
                    'success': False,
                    'error': 'Тема не предоставлена'
                })
            
            try:
                from .gigachat_api import generate_image_prompt_from_text
                # Создаём промпт на основе темы. В качестве "текста" передаём тему, а form_data пустой
                image_prompt = generate_image_prompt_from_text(topic, {}) if callable(generate_image_prompt_from_text) else None
            except Exception:
                image_prompt = None

            # Если не удалось сгенерировать промпт, используем простое описание
            if not image_prompt:
                image_prompt = f"Сделай яркую иллюстрацию для социальной сети на тему: '{topic}'. Стиль: цифровая живопись, яркие цвета."

            # Запускаем генерацию изображения
            image_data = generate_image_gigachat(image_prompt)
            
            if image_data:
                print(f"Тип image_data: {type(image_data)}")
                print(f"Длина image_data: {len(image_data)}")
                print(f"Первые 100 символов image_data: {image_data[:100]}")
                
                if image_data.startswith("data:image"):
                    # Это base64 данные от GigaChat - сохраняем локально
                    try:
                        # Создаем уникальное имя файла
                        import uuid
                        filename = f"generated_{uuid.uuid4().hex[:8]}.jpg"
                        full_path = os.path.join(settings.MEDIA_ROOT, filename)
                        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                        
                        # Извлекаем base64 данные
                        base64_data = image_data.split(',')[1]
                        image_bytes = base64.b64decode(base64_data)
                        
                        with open(full_path, "wb") as f:
                            f.write(image_bytes)
                        
                        image_url = settings.MEDIA_URL + filename
                        print(f"Изображение сохранено локально: {image_url}")
                        print(f"Размер файла: {len(image_bytes)} байт")
                        
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic, image_url)
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_url,
                            'message': 'Изображение успешно перегенерировано'
                        })
                        
                    except Exception as e:
                        print(f"Ошибка при сохранении base64 изображения: {e}")
                        # Возвращаемся к base64 как fallback
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic, image_data)
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_data,
                            'message': 'Изображение перегенерировано (base64)'
                        })
                elif image_data.startswith("http"):
                    # Это URL (если вдруг вернется)
                    # Обновляем изображение в существующей записи
                    update_generation_image(request, topic, image_data)
                    
                    return JsonResponse({
                        'success': True,
                        'image_url': image_data,
                        'message': 'Изображение перегенерировано (URL)'
                    })
                else:
                    # Сохраняем локально, если это base64 без префикса
                    filename = f"regenerated_{topic[:20].replace(' ', '_')}.jpg"
                    full_path = os.path.join(settings.MEDIA_ROOT, filename)
                    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                    
                    # Декодируем base64 и сохраняем
                    try:
                        image_bytes = base64.b64decode(image_data)
                        with open(full_path, "wb") as f:
                            f.write(image_bytes)
                        image_url = settings.MEDIA_URL + filename
                        print(f"Изображение сохранено локально: {image_url}")
                        
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic, image_url)
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_url,
                            'message': 'Изображение успешно перегенерировано'
                        })
                    except Exception as e:
                        print(f"Ошибка при сохранении изображения: {e}")
                        return JsonResponse({
                            'success': False,
                            'error': 'Ошибка при сохранении изображения'
                        })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'GigaChat вернул текст без изображения. Попробуйте изменить тему или повторить позже.'
                })
            
        except Exception as e:
            print(f"Ошибка при перегенерации изображения: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Метод не поддерживается'
    })

def register_disabled_view(request):
    """
    DEPRECATED: Регистрация отключена.
    
    Теперь используется система временных токенов для доступа.
    Получите токен через Telegram Bot или используйте developer токен.
    """
    messages.info(
        request,
        'Регистрация больше не требуется! Получите токен доступа через Telegram Bot.'
    )
    return render(request, 'generator/token_required.html', {
        'title': 'Регистрация отключена',
        'message': 'Теперь вход через систему токенов',
        'show_telegram_info': True
    })


# DEPRECATED: Старая функция регистрации (сохранена для обратной совместимости)
def register_view(request):
    """Перенаправляет на новую систему токенов"""
    return register_disabled_view(request)

from django.views.decorators.csrf import csrf_exempt

def agreement_view(request):
    reg_data = request.session.get('reg_data')
    if not reg_data:
        return redirect('register')
    error = ''
    if request.method == 'POST':
        if request.POST.get('accept_terms') == 'on':
            # Преобразуем дату рождения в объект date
            date_of_birth = reg_data.get('date_of_birth', None)
            dob_obj = None
            if date_of_birth:
                try:
                    dob_obj = datetime.strptime(date_of_birth, '%d.%m.%Y').date()
                except Exception:
                    error = 'Дата рождения указана в неверном формате.'
                    return render(request, 'generator/user_agreement.html', {'error': error})
            # Создаём пользователя и профиль
            user = User.objects.create_user(
                username=reg_data['username'],
                email=reg_data['email'],
                password=reg_data['password'],
            )
            user_profile = UserProfile.objects.create(
                user=user,
                first_name=reg_data.get('first_name', ''),
                last_name=reg_data.get('last_name', ''),
                city=reg_data.get('city', ''),
                phone=reg_data.get('phone', ''),
                date_of_birth=dob_obj,
                terms_accepted=True,
            )
            login(request, user)
            request.session.pop('reg_data', None)
            return redirect('profile')
        else:
            error = 'Необходимо принять пользовательское соглашение.'
    return render(request, 'generator/user_agreement.html', {'error': error})

def login_disabled_view(request):
    """
    DEPRECATED: Вход через логин/пароль отключен.
    
    Теперь используется система временных токенов для доступа.
    Получите токен через Telegram Bot или используйте developer токен.
    """
    messages.info(
        request,
        'Вход через логин/пароль отключен! Используйте токен-ссылку для доступа.'
    )
    return render(request, 'generator/token_required.html', {
        'title': 'Вход через токены',
        'message': 'Используйте токен-ссылку для доступа',
        'show_telegram_info': True
    })


# DEPRECATED: Старая функция входа (сохранена для обратной совместимости)
def login_view(request):
    """Перенаправляет на новую систему токенов"""
    return login_disabled_view(request)

def logout_view(request):
    """
    Выход из системы
    
    Очищает сессию и перенаправляет на страницу получения токена.
    """
    # Очищаем сессию
    logout(request)
    
    # Очищаем данные токена из сессии
    request.session.pop('access_token', None)
    request.session.pop('token_type', None)
    request.session.pop('is_demo', None)
    request.session.pop('daily_generations_left', None)
    
    messages.success(request, 'Вы успешно вышли из системы.')
    return redirect('token_required_page')

def home_view(request):
    return render(request, 'generator/home.html')

@token_required
def profile_view(request):
    # Получаем информацию о токене
    token = request.token
    token_type = request.session.get('token_type', 'DEMO')
    token_type_display = token.get_token_type_display() if token else token_type
    is_demo = request.session.get('is_demo', False)
    daily_left = request.session.get('daily_generations_left', 0)
    
    # Для совместимости создаем фиктивный user_profile
    # В системе токенов профиль пользователя не используется
    user_profile = None
    if request.user.is_authenticated:
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    return render(request, 'generator/profile.html', {
        'user_profile': user_profile,
        'token': token,
        'token_type': token_type,
        'token_type_display': token_type_display,
        'is_demo': is_demo,
        'daily_left': daily_left
    })

@token_required
def edit_profile_view(request):
    # В системе токенов редактирование профиля недоступно
    # Профиль привязан к User, а токены работают без пользователей
    messages.info(request, 'Редактирование профиля недоступно в системе токенов. Профиль привязан к пользователю Django.')
    return redirect('profile')

@token_required
def user_wall_view(request):
    # Показываем все генерации (в системе токенов user может быть null)
    # Можно фильтровать по токену, но в модели нет прямой связи
    # Показываем все генерации без пользователя или все, если пользователь авторизован
    if request.user.is_authenticated:
        generations = Generation.objects.filter(user=request.user).order_by('-created_at')
    else:
        # Показываем генерации без пользователя (анонимные)
        generations = Generation.objects.filter(user__isnull=True).order_by('-created_at')
    return render(request, 'generator/wall.html', {'generations': generations})

@token_required
def delete_generation_view(request, gen_id):
    # В системе токенов можно удалять генерации без привязки к пользователю
    if request.user.is_authenticated:
        gen = get_object_or_404(Generation, id=gen_id, user=request.user)
    else:
        gen = get_object_or_404(Generation, id=gen_id, user__isnull=True)
    if request.method == 'POST':
        gen.delete()
        messages.success(request, 'Контент успешно удалён.')
        return redirect('user_wall')
    return render(request, 'generator/delete_generation_confirm.html', {'gen': gen})

@token_required
def generation_detail_view(request, gen_id):
    # В системе токенов можно просматривать генерации без привязки к пользователю
    if request.user.is_authenticated:
        gen = get_object_or_404(Generation, id=gen_id, user=request.user)
    else:
        gen = get_object_or_404(Generation, id=gen_id, user__isnull=True)
    return render(request, 'generator/generation_detail.html', {'gen': gen})

# --- API для шаблонов генератора ---
# В системе токенов шаблоны недоступны (требуют User)
@token_required
@require_POST
def save_template_view(request):
    # Шаблоны требуют User, в системе токенов недоступны
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Шаблоны доступны только для авторизованных пользователей'})
    
    import json
    data = json.loads(request.body.decode('utf-8'))
    name = data.get('name', '').strip()
    settings = data.get('settings', {})
    is_default = data.get('is_default', False)
    if not name or not isinstance(settings, dict):
        return JsonResponse({'success': False, 'error': 'Некорректные данные'})
    # Проверка уникальности имени
    if GenerationTemplate.objects.filter(user=request.user, name=name).exists():
        return JsonResponse({'success': False, 'error': 'Шаблон с таким именем уже существует'})
    # Если is_default, сбросить другие шаблоны
    if is_default:
        GenerationTemplate.objects.filter(user=request.user, is_default=True).update(is_default=False)
    template = GenerationTemplate.objects.create(
        user=request.user,
        name=name,
        settings=settings,
        is_default=is_default
    )
    return JsonResponse({'success': True, 'template_id': template.id})

@token_required
@require_GET
def get_templates_view(request):
    # Шаблоны требуют User, в системе токенов недоступны
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Шаблоны доступны только для авторизованных пользователей', 'templates': []})
    
    templates = GenerationTemplate.objects.filter(user=request.user).order_by('-updated_at')
    result = [
        {
            'id': t.id,
            'name': t.name,
            'is_default': t.is_default,
            'updated_at': t.updated_at.strftime('%Y-%m-%d %H:%M'),
        } for t in templates
    ]
    return JsonResponse({'success': True, 'templates': result})

@token_required
@require_GET
def load_template_view(request):
    # Шаблоны требуют User, в системе токенов недоступны
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Шаблоны доступны только для авторизованных пользователей'})
    
    template_id = request.GET.get('id')
    try:
        template = GenerationTemplate.objects.get(user=request.user, id=template_id)
        return JsonResponse({'success': True, 'settings': template.settings, 'name': template.name, 'is_default': template.is_default})
    except GenerationTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Шаблон не найден'})

@token_required
@require_POST
def delete_template_view(request):
    # Шаблоны требуют User, в системе токенов недоступны
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Шаблоны доступны только для авторизованных пользователей'})
    
    import json
    data = json.loads(request.body.decode('utf-8'))
    template_id = data.get('id')
    try:
        template = GenerationTemplate.objects.get(user=request.user, id=template_id)
        template.delete()
        return JsonResponse({'success': True})
    except GenerationTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Шаблон не найден'})

@token_required
@require_POST
def rename_template_view(request):
    # Шаблоны требуют User, в системе токенов недоступны
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Шаблоны доступны только для авторизованных пользователей'})
    
    import json
    data = json.loads(request.body.decode('utf-8'))
    template_id = data.get('id')
    new_name = data.get('new_name', '').strip()
    if not new_name:
        return JsonResponse({'success': False, 'error': 'Новое имя не указано'})
    if GenerationTemplate.objects.filter(user=request.user, name=new_name).exclude(id=template_id).exists():
        return JsonResponse({'success': False, 'error': 'Шаблон с таким именем уже существует'})
    try:
        template = GenerationTemplate.objects.get(user=request.user, id=template_id)
        template.name = new_name
        template.save()
        return JsonResponse({'success': True})
    except GenerationTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Шаблон не найден'})

@token_required
@require_POST
def set_default_template_view(request):
    # Шаблоны требуют User, в системе токенов недоступны
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Шаблоны доступны только для авторизованных пользователей'})
    
    import json
    data = json.loads(request.body.decode('utf-8'))
    template_id = data.get('id')
    try:
        template = GenerationTemplate.objects.get(user=request.user, id=template_id)
        GenerationTemplate.objects.filter(user=request.user, is_default=True).update(is_default=False)
        template.is_default = True
        template.save()
        return JsonResponse({'success': True})
    except GenerationTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Шаблон не найден'})

# =============================================================================
# TOKEN ACCESS VIEWS
# =============================================================================

def token_auth_view(request, token):
    """
    Обработка входа по временному токену
    
    Проверяет валидность токена и создает анонимную сессию для пользователя.
    DEMO токены: 5 дней + 5 генераций в день
    Платные токены: только временное ограничение
    
    Args:
        request: HTTP запрос
        token (UUID): Токен доступа из URL
    
    Returns:
        HttpResponse: Редирект на dashboard или страницу ошибки
    """
    try:
        from .models import TemporaryAccessToken
        from django.utils import timezone
        
        # Пытаемся найти активный токен
        access_token = TemporaryAccessToken.objects.get(
            token=token,
            is_active=True,
            expires_at__gt=timezone.now()
        )
        
        # Проверка для DEMO токенов
        if access_token.token_type == 'DEMO':
            # Сброс счётчика если новый день
            if access_token.generations_reset_date != timezone.now().date():
                access_token.daily_generations_left = 5
                access_token.generations_reset_date = timezone.now().date()
                access_token.save()
            
            # Проверка лимита (показываем предупреждение, но разрешаем вход)
            if access_token.daily_generations_left <= 0:
                messages.warning(
                    request, 
                    'Лимит генераций на сегодня исчерпан. Вы можете просматривать существующий контент.'
                )
        
        # Создаём анонимную сессию
        request.session['access_token'] = str(token)
        request.session['token_type'] = access_token.token_type
        request.session['is_demo'] = (access_token.token_type == 'DEMO')
        request.session['daily_generations_left'] = access_token.daily_generations_left
        request.session['expires_at'] = access_token.expires_at.isoformat()
        
        # Обновляем информацию о последнем использовании
        access_token.last_used = timezone.now()
        access_token.current_ip = request.META.get('REMOTE_ADDR')
        access_token.save()
        
        messages.success(
            request,
            f'Добро пожаловать! Токен типа: {access_token.get_token_type_display()}'
        )
        
        return redirect('index')
    
    except TemporaryAccessToken.DoesNotExist:
        return render(request, 'generator/invalid_token.html', {
            'token': token
        })

def token_required_page(request):
    """
    Страница с требованием токена для доступа
    
    Отображается когда пользователь пытается получить доступ без токена.
    """
    return render(request, 'generator/token_required.html')

def invalid_token_page(request):
    """
    Страница неверного или просроченного токена
    
    Отображается когда токен недействителен или истек срок его действия.
    """
    return render(request, 'generator/invalid_token.html')

def limit_exceeded_page(request):
    """
    Страница превышения лимита генераций
    
    Отображается для DEMO токенов когда исчерпан дневной лимит генераций.
    """
    daily_left = request.session.get('daily_generations_left', 0)
    token_type = request.session.get('token_type', 'DEMO')
    
    return render(request, 'generator/limit_exceeded.html', {
        'daily_generations_left': daily_left,
        'token_type': token_type
    })

# =============================================================================
# TELEGRAM BOT WEBHOOK
# =============================================================================

@csrf_exempt
def telegram_webhook(request):
    """
    Webhook для обработки запросов от Telegram бота
    
    Обрабатывает команды и кнопки от пользователей Telegram,
    генерирует токены доступа и отправляет ссылки.
    
    Безопасность: Проверяет секретный токен в заголовках запроса.
    
    Args:
        request: POST запрос от Telegram API
    
    Returns:
        JsonResponse: Статус обработки
    """
    import json
    from django.conf import settings
    from datetime import timedelta
    from django.utils import timezone
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Простая верификация через секретный токен
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    expected_token = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', None)
    
    if not expected_token or secret_token != expected_token:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        
        # Обработка callback_query (нажатия кнопок)
        if 'callback_query' in data:
            callback = data['callback_query']
            chat_id = callback['message']['chat']['id']
            action = callback['data']
            
            if action == 'demo':
                # Создаём DEMO токен
                from .models import TemporaryAccessToken
                
                token = TemporaryAccessToken.objects.create(
                    token_type='DEMO',
                    expires_at=timezone.now() + timedelta(days=5),
                    daily_generations_left=5,
                    generations_reset_date=timezone.now().date()
                )
                
                # Формируем ссылку
                site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                token_url = f"{site_url}/auth/token/{token.token}/"
                
                # Отправляем ссылку пользователю
                message = (
                    f"🎁 Ваша демо-ссылка (5 дней, 5 генераций в день):\n\n"
                    f"{token_url}\n\n"
                    f"📅 Ссылка активна до: {token.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"⚡ Генераций доступно сегодня: {token.daily_generations_left}"
                )
                
                send_telegram_message(chat_id, message)
            
            elif action == 'buy_monthly':
                # Заглушка для месячной подписки
                send_telegram_message(
                    chat_id,
                    "⚠️ Платёжная система в разработке.\n"
                    "Мы учли ваш интерес к месячной подписке!"
                )
            
            elif action == 'buy_yearly':
                # Заглушка для годовой подписки
                send_telegram_message(
                    chat_id,
                    "⚠️ Платёжная система в разработке.\n"
                    "Мы учли ваш интерес к годовой подписке!"
                )
        
        # Обработка команды /start
        elif 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            if text.startswith('/start'):
                # Отправляем приветствие с кнопками выбора тарифа
                send_welcome_message(chat_id)
        
        return JsonResponse({'status': 'ok'})
    
    except Exception as e:
        print(f"Ошибка в telegram_webhook: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

def send_telegram_message(chat_id, text):
    """
    Отправляет сообщение пользователю через Telegram Bot API
    
    Args:
        chat_id (int): ID чата пользователя
        text (str): Текст сообщения
    
    Returns:
        bool: True если успешно, False при ошибке
    """
    from django.conf import settings
    import requests
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN не настроен")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки Telegram сообщения: {e}")
        return False

def send_welcome_message(chat_id):
    """
    Отправляет приветственное сообщение с кнопками выбора тарифа
    
    Args:
        chat_id (int): ID чата пользователя
    
    Returns:
        bool: True если успешно, False при ошибке
    """
    from django.conf import settings
    import requests
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Формируем клавиатуру с кнопками
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '🆓 Демо 5 дней', 'callback_data': 'demo'}
            ],
            [
                {'text': '📅 30 дней', 'callback_data': 'buy_monthly'}
            ],
            [
                {'text': '📆 1 год', 'callback_data': 'buy_yearly'}
            ]
        ]
    }
    
    text = (
        "👋 Добро пожаловать в Ghostwriter!\n\n"
        "Выберите тариф для доступа к генератору контента:\n\n"
        "🆓 <b>Демо</b> - 5 дней, 5 генераций в день (бесплатно)\n"
        "📅 <b>30 дней</b> - безлимитные генерации\n"
        "📆 <b>1 год</b> - безлимитные генерации\n\n"
        "Нажмите кнопку ниже для получения ссылки доступа:"
    )
    
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'reply_markup': keyboard
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки приветственного сообщения: {e}")
        return False


# =============================================================================
# API ENDPOINTS FOR TOKEN CREATION
# =============================================================================

@csrf_exempt
@require_POST
def api_create_token(request):
    """
    API endpoint для создания токенов через HTTP запросы
    
    Используется Telegram ботом для создания реальных токенов доступа.
    
    POST /api/tokens/create/
    {
        "token_type": "DEMO",  # или "MONTHLY", "YEARLY"
        "expires_days": 5,
        "daily_limit": 5  # -1 для безлимита
    }
    
    Returns:
        JSON с данными токена:
        {
            "token": "uuid",
            "token_type": "DEMO",
            "expires_at": "2024-01-20T12:00:00Z",
            "daily_limit": 5,
            "url": "http://site.com/auth/token/uuid/"
        }
    """
    import json
    from django.utils import timezone
    from datetime import timedelta
    from .models import TemporaryAccessToken
    
    # Проверка API ключа (опционально)
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(settings, 'DJANGO_API_KEY', None)
    
    if expected_key and api_key != expected_key:
        return JsonResponse({
            'error': 'Unauthorized',
            'message': 'Invalid API key'
        }, status=401)
    
    try:
        # Парсим данные запроса
        data = json.loads(request.body)
        
        token_type = data.get('token_type', 'DEMO')
        expires_days = data.get('expires_days', 5)
        daily_limit = data.get('daily_limit', 5)
        
        # Валидация типа токена
        valid_types = ['DEMO', 'MONTHLY', 'YEARLY', 'DEVELOPER']
        if token_type not in valid_types:
            return JsonResponse({
                'error': 'Invalid token type',
                'message': f'Token type must be one of: {", ".join(valid_types)}'
            }, status=400)
        
        # Создаем токен
        now = timezone.now()
        expires_at = now + timedelta(days=expires_days)
        
        token = TemporaryAccessToken.objects.create(
            token_type=token_type,
            expires_at=expires_at,
            daily_generations_left=daily_limit,
            generations_reset_date=now.date() if token_type == 'DEMO' else None,
            is_active=True,
            total_used=0
        )
        
        # Формируем URL токена
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        token_url = f"{site_url}/auth/token/{token.token}/"
        
        # Возвращаем данные токена
        response_data = {
            'token': str(token.token),
            'token_type': token.token_type,
            'expires_at': token.expires_at.isoformat(),
            'daily_limit': token.daily_generations_left,
            'url': token_url,
            'created_at': token.created_at.isoformat(),
            'is_active': token.is_active
        }
        
        return JsonResponse(response_data, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON',
            'message': 'Request body must be valid JSON'
        }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_GET
def api_token_info(request, token):
    """
    API endpoint для получения информации о токене
    
    GET /api/tokens/<uuid>/
    
    Returns:
        JSON с информацией о токене
    """
    from .models import TemporaryAccessToken
    
    try:
        token_obj = TemporaryAccessToken.objects.get(token=token)
        
        response_data = {
            'token': str(token_obj.token),
            'token_type': token_obj.token_type,
            'is_active': token_obj.is_active,
            'expires_at': token_obj.expires_at.isoformat(),
            'created_at': token_obj.created_at.isoformat(),
            'daily_generations_left': token_obj.daily_generations_left,
            'total_used': token_obj.total_used,
            'last_used': token_obj.last_used.isoformat() if token_obj.last_used else None,
            'is_expired': token_obj.is_expired()
        }
        
        return JsonResponse(response_data)
    
    except TemporaryAccessToken.DoesNotExist:
        return JsonResponse({
            'error': 'Token not found',
            'message': f'Token {token} does not exist'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'error': 'Internal server error',
            'message': str(e)
        }, status=500)