# =============================================================================
# DJANGO IMPORTS
# =============================================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
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
                            result = "❌ Flask Generator не запущен. Запустите Flask приложение на порту 5000."
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
                                result = f"❌ Ошибка Flask API: {str(e)}"
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
    return render(request, 'generator/gigagenerator.html', {'form': form, 'result': result, 'image_url': image_url, 'limit_reached': limit_reached})

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

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Сохраняем данные во временную сессию
            request.session['reg_data'] = form.cleaned_data
            return redirect('user_agreement')
    else:
        form = RegisterForm()
    return render(request, 'generator/register.html', {'form': form})

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

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Remember me logic
            if form.cleaned_data.get('remember_me'):
                request.session.set_expiry(1209600)  # 2 недели
            else:
                request.session.set_expiry(0)  # До закрытия браузера
            return redirect('profile')  # Перенаправление на профиль
    else:
        form = LoginForm()
    return render(request, 'generator/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

def home_view(request):
    return render(request, 'generator/home.html')

@login_required
def profile_view(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'generator/profile.html', {'user_profile': user_profile})

@login_required
def edit_profile_view(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if profile_form.is_valid():
            profile_form.save()
            return redirect('profile')
    else:
        profile_form = UserProfileForm(instance=user_profile)
    return render(request, 'generator/edit_profile.html', {'profile_form': profile_form})

@login_required
def user_wall_view(request):
    generations = Generation.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'generator/wall.html', {'generations': generations})

@login_required
def delete_generation_view(request, gen_id):
    gen = get_object_or_404(Generation, id=gen_id, user=request.user)
    if request.method == 'POST':
        gen.delete()
        messages.success(request, 'Контент успешно удалён.')
        return redirect('user_wall')
    return render(request, 'generator/delete_generation_confirm.html', {'gen': gen})

@login_required
def generation_detail_view(request, gen_id):
    gen = get_object_or_404(Generation, id=gen_id, user=request.user)
    return render(request, 'generator/generation_detail.html', {'gen': gen})

# --- API для шаблонов генератора ---
@login_required
@require_POST
def save_template_view(request):
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

@login_required
@require_GET
def get_templates_view(request):
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

@login_required
@require_GET
def load_template_view(request):
    template_id = request.GET.get('id')
    try:
        template = GenerationTemplate.objects.get(user=request.user, id=template_id)
        return JsonResponse({'success': True, 'settings': template.settings, 'name': template.name, 'is_default': template.is_default})
    except GenerationTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Шаблон не найден'})

@login_required
@require_POST
def delete_template_view(request):
    import json
    data = json.loads(request.body.decode('utf-8'))
    template_id = data.get('id')
    try:
        template = GenerationTemplate.objects.get(user=request.user, id=template_id)
        template.delete()
        return JsonResponse({'success': True})
    except GenerationTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Шаблон не найден'})

@login_required
@require_POST
def rename_template_view(request):
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

@login_required
@require_POST
def set_default_template_view(request):
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
