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
from .forms import GenerationForm, LoginForm
from .models import Generation, UserProfile, GenerationTemplate, SupportTicket, Review, SupportChat
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
import time
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
                            password='admin123'
                        )
                    elif username == 'test_user_1':
                        user = User.objects.create_user(
                            username='test_user_1',
                            email='test1@example.com',
                            password='test123'
                        )
                        # Создаем профиль пользователя
                        UserProfile.objects.get_or_create(user=user)
                    elif username == 'test_user_2':
                        user = User.objects.create_user(
                            username='test_user_2',
                            email='test2@example.com',
                            password='test123'
                        )
                        # Создаем профиль пользователя
                        UserProfile.objects.get_or_create(user=user)
                
                # Выполняем вход
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.username}!')
                
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
    generate_image_flag = request.POST.get('generate_image', 'off') == 'on'  # Чекбокс генерации изображения
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
                            # Получаем токен для учёта OpenAI токенов
                            token = getattr(request, 'token', None)
                            
                            # Генератор через Flask API
                            gen_result = generate_text_and_prompt(form_data, token=token)
                            result = gen_result.get('text')
                            image_prompt = gen_result.get('image_prompt')
                            image_url = generate_image(image_prompt, token=token) if image_prompt else None
                            
                            # Обновляем информацию о токенах в сессии после использования
                            if token and is_ajax:
                                request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                                request.session['openai_tokens_used'] = token.openai_tokens_used
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
                    # Получаем данные для логирования токенов
                    user = request.user if request.user.is_authenticated else None
                    token = getattr(request, 'token', None)
                    
                    # Генерируем текст
                    result = generate_text(form_data, user=user, token=token)
                    
                    # Создаем запись генерации для связи с токенами
                    gen = Generation.objects.create(
                        user=user,
                        topic=form_data.get('topic', ''),
                        result=result or "",
                        image_url=""
                    )
                    generation_id = gen.id
                    
                    # Генерируем изображение только если чекбокс выбран
                    image_data = None
                    image_url = None
                    if generate_image_flag and result:
                        from .gigachat_api import generate_image_prompt_from_text
                        image_prompt = generate_image_prompt_from_text(result, form_data, user=user, token=token, generation_id=generation_id) if result else None
                        if image_prompt:
                            image_data = generate_image_gigachat(image_prompt, user=user, token=token, generation_id=generation_id)
                        else:
                            image_data = generate_image_gigachat(form_data.get('topic', ''), user=user, token=token, generation_id=generation_id)
                    
                    # Обновляем информацию о токенах в сессии после использования GigaChat
                    if token and is_ajax:
                        request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                        request.session['openai_tokens_used'] = token.openai_tokens_used
                    
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
                            image_url = request.build_absolute_uri(settings.MEDIA_URL + filename)
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
                                image_url = request.build_absolute_uri(settings.MEDIA_URL + filename)
                            except Exception as e:
                                image_url = None
                # Обновляем запись генерации с изображением (если она уже создана)
                if 'generation_id' not in locals():
                    gen = Generation.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        topic=form_data.get('topic', ''),
                        result=result,
                        image_url=image_url or ""
                    )
                else:
                    # Обновляем существующую запись
                    gen.image_url = image_url or ""
                    gen.save()
                
                # Сохраняем ID генерации в сессии для последующих перегенераций
                request.session['current_generation_id'] = gen.id
                # Сохраняем form_data для последующей генерации изображения
                request.session['last_form_data'] = form_data
                if is_ajax:
                    # Обновляем информацию о токенах из сессии перед отправкой ответа
                    token = getattr(request, 'token', None)
                    if token:
                        # Обновляем данные в сессии из актуального токена
                        request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                        request.session['openai_tokens_used'] = token.openai_tokens_used
                    
                    return JsonResponse({
                        'success': True,
                        'result': result,
                        'image_url': image_url,
                        'limit_reached': limit_reached,
                        'generation_id': gen.id,
                        'generate_image_flag': generate_image_flag,
                        'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                        'openai_tokens_used': request.session.get('openai_tokens_used', 0)
                    })
            except Exception as e:
                print(f"Ошибка генерации: {e}")
                if is_ajax:
                    return JsonResponse({'success': False, 'error': str(e)})
        else:
            if is_ajax:
                errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
                return JsonResponse({'success': False, 'error': 'Некорректно заполнена форма', 'form_errors': errors})
    # Получаем информацию о токене для отображения лимитов
    token = getattr(request, 'token', None)
    is_demo = request.session.get('is_demo', False)
    token_type = request.session.get('token_type', 'DEMO_FREE')
    gigachat_tokens_limit = request.session.get('gigachat_tokens_limit', -1)
    gigachat_tokens_used = request.session.get('gigachat_tokens_used', 0)
    openai_tokens_limit = request.session.get('openai_tokens_limit', 0)
    openai_tokens_used = request.session.get('openai_tokens_used', 0)
    # Список URL изображений (поддержка нескольких при перегенерации)
    image_urls = [u.strip() for u in (image_url or '').split('|') if u and u.strip()] if image_url else []
    
    return render(request, 'generator/gigagenerator.html', {
        'form': form, 
        'result': result, 
        'image_url': image_url, 
        'image_urls': image_urls,
        'limit_reached': limit_reached,
        'is_demo': is_demo,
        'token': token,
        'token_type': token_type,
        'gigachat_tokens_limit': gigachat_tokens_limit,
        'gigachat_tokens_used': gigachat_tokens_used,
        'openai_tokens_limit': openai_tokens_limit,
        'openai_tokens_used': openai_tokens_used
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
            # Получаем токен для учёта токенов
            user = request.user if request.user.is_authenticated else None
            token = getattr(request, 'token', None)
            
            # Создаем словарь с данными для генерации
            form_data = {
                'topic': topic
                # Добавить новые критерии, если нужно
            }
            # Генерируем новый текст
            result = generate_text(form_data, user=user, token=token)
            
            # Обновляем информацию о токенах в сессии
            if token:
                request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                request.session['openai_tokens_used'] = token.openai_tokens_used
            
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
                        user=user,
                        topic=topic,
                        result=result,
                        image_url=""
                    )
                    request.session['current_generation_id'] = gen.id
            else:
                # Создаем новую запись, если нет ID в сессии
                gen = Generation.objects.create(
                    user=user,
                    topic=topic,
                    result=result,
                    image_url=""
                )
                request.session['current_generation_id'] = gen.id
            return JsonResponse({
                'success': True,
                'result': result,
                'message': 'Текст успешно перегенерирован',
                'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                'openai_tokens_used': request.session.get('openai_tokens_used', 0)
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
@token_required
def generate_image_from_text(request):
    """
    Генерация изображения на основе уже сгенерированного текста
    
    Генерирует промпт для изображения на основе текста и создает изображение.
    Используется когда пользователь не выбрал генерацию изображения сразу.
    
    Args:
        request: AJAX POST запрос с topic и result_text
    
    Returns:
        JsonResponse: URL изображения или ошибка
    """
    if request.method == 'POST':
        try:
            topic = request.POST.get('topic')
            result_text = request.POST.get('result_text')
            
            if not result_text:
                return JsonResponse({
                    'success': False,
                    'error': 'Текст не предоставлен'
                })
            
            # Получаем данные для логирования токенов
            user = request.user if request.user.is_authenticated else None
            token = getattr(request, 'token', None)
            generation_id = request.session.get('current_generation_id')
            
            # Получаем form_data из сессии или создаем минимальный набор
            form_data = request.session.get('last_form_data', {})
            if not form_data:
                form_data = {'topic': topic} if topic else {}
            
            try:
                from .gigachat_api import generate_image_prompt_from_text
                # Генерируем промпт на основе сгенерированного текста
                image_prompt = generate_image_prompt_from_text(result_text, form_data, user=user, token=token, generation_id=generation_id)
            except Exception as e:
                print(f"Ошибка при генерации промпта: {e}")
                image_prompt = None
            
            # Если не удалось сгенерировать промпт, используем простое описание
            if not image_prompt:
                image_prompt = f"Сделай яркую иллюстрацию для социальной сети на тему: '{topic or result_text[:100]}'. Стиль: цифровая живопись, яркие цвета."
            
            # Пауза между запросом промпта и запросом изображения, чтобы не упираться в 429 GigaChat
            time.sleep(5)
            
            # Запускаем генерацию изображения
            from .gigachat_api import generate_image_gigachat
            image_data = generate_image_gigachat(image_prompt, user=user, token=token, generation_id=generation_id)
            
            if image_data:
                if image_data.startswith("data:image"):
                    # Это base64 данные от GigaChat - сохраняем локально
                    try:
                        import uuid
                        filename = f"generated_{uuid.uuid4().hex[:8]}.jpg"
                        full_path = os.path.join(settings.MEDIA_ROOT, filename)
                        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                        
                        base64_data = image_data.split(',')[1]
                        image_bytes = base64.b64decode(base64_data)
                        
                        with open(full_path, "wb") as f:
                            f.write(image_bytes)
                        
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + filename)
                        print(f"Изображение сохранено: {filename}, URL: {image_url[:80]}...")
                        
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic or result_text[:50], image_url)
                        
                        # Обновляем информацию о токенах в сессии
                        if token:
                            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                            request.session['openai_tokens_used'] = token.openai_tokens_used
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_url,
                            'message': 'Изображение успешно сгенерировано',
                            'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                            'openai_tokens_used': request.session.get('openai_tokens_used', 0)
                        })
                    except Exception as e:
                        print(f"Ошибка при сохранении base64 изображения: {e}")
                        return JsonResponse({
                            'success': False,
                            'error': f'Ошибка при сохранении изображения: {str(e)}'
                        })
                elif image_data.startswith("http"):
                    # Это URL
                    update_generation_image(request, topic or result_text[:50], image_data)
                    
                    if token:
                        request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                        request.session['openai_tokens_used'] = token.openai_tokens_used
                    
                    return JsonResponse({
                        'success': True,
                        'image_url': image_data,
                        'message': 'Изображение успешно сгенерировано',
                        'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                        'openai_tokens_used': request.session.get('openai_tokens_used', 0)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Неизвестный формат данных изображения'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Не удалось сгенерировать изображение'
                })
        except Exception as e:
            print(f"Ошибка при генерации изображения из текста: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    return JsonResponse({
        'success': False,
        'error': 'Метод не поддерживается'
    })

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
            
            # Получаем данные для логирования токенов
            user = request.user if request.user.is_authenticated else None
            token = getattr(request, 'token', None)
            generation_id = request.session.get('current_generation_id')
            
            try:
                from .gigachat_api import generate_image_prompt_from_text
                # Создаём промпт на основе темы. В качестве "текста" передаём тему, а form_data пустой
                image_prompt = generate_image_prompt_from_text(topic, {}, user=user, token=token, generation_id=generation_id) if callable(generate_image_prompt_from_text) else None
            except Exception:
                image_prompt = None

            # Если не удалось сгенерировать промпт, используем простое описание
            if not image_prompt:
                image_prompt = f"Сделай яркую иллюстрацию для социальной сети на тему: '{topic}'. Стиль: цифровая живопись, яркие цвета."

            # Запускаем генерацию изображения
            image_data = generate_image_gigachat(image_prompt, user=user, token=token, generation_id=generation_id)
            
            if image_data:
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
                        
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + filename)
                        print(f"Изображение сохранено локально: {image_url}")
                        print(f"Размер файла: {len(image_bytes)} байт")
                        
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic, image_url)
                        
                        # Обновляем информацию о токенах в сессии
                        if token:
                            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                            request.session['openai_tokens_used'] = token.openai_tokens_used
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_url,
                            'message': 'Изображение успешно перегенерировано',
                            'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                            'openai_tokens_used': request.session.get('openai_tokens_used', 0)
                        })
                        
                    except Exception as e:
                        print(f"Ошибка при сохранении base64 изображения: {e}")
                        # Возвращаемся к base64 как fallback
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic, image_data)
                        
                        # Обновляем информацию о токенах в сессии
                        if token:
                            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                            request.session['openai_tokens_used'] = token.openai_tokens_used
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_data,
                            'message': 'Изображение перегенерировано (base64)',
                            'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                            'openai_tokens_used': request.session.get('openai_tokens_used', 0)
                        })
                elif image_data.startswith("http"):
                    # Это URL (если вдруг вернется)
                    # Обновляем изображение в существующей записи
                    update_generation_image(request, topic, image_data)
                    
                    # Обновляем информацию о токенах в сессии
                    if token:
                        request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                        request.session['openai_tokens_used'] = token.openai_tokens_used
                    
                    return JsonResponse({
                        'success': True,
                        'image_url': image_data,
                        'message': 'Изображение перегенерировано (URL)',
                        'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                        'openai_tokens_used': request.session.get('openai_tokens_used', 0)
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
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + filename)
                        print(f"Изображение сохранено локально: {image_url}")
                        
                        # Обновляем изображение в существующей записи
                        update_generation_image(request, topic, image_url)
                        
                        # Обновляем информацию о токенах в сессии
                        if token:
                            request.session['gigachat_tokens_used'] = token.gigachat_tokens_used
                            request.session['openai_tokens_used'] = token.openai_tokens_used
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_url,
                            'message': 'Изображение успешно перегенерировано',
                            'gigachat_tokens_used': request.session.get('gigachat_tokens_used', 0),
                            'openai_tokens_used': request.session.get('openai_tokens_used', 0)
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

def landing_view(request):
    """
    Публичная главная страница (landing page)
    Доступна всем без токена
    """
    return render(request, 'generator/landing.html')


def home_view(request):
    """
    Устаревшая страница home - редирект на landing
    """
    return redirect('landing')

@token_required
def profile_view(request):
    # Получаем информацию о токене
    token = getattr(request, 'token', None)
    token_type = request.session.get('token_type', 'DEMO_FREE')
    token_type_display = token.get_token_type_display() if token else token_type
    is_demo = request.session.get('is_demo', False)
    
    # Получаем информацию о лимитах токенов
    gigachat_tokens_limit = request.session.get('gigachat_tokens_limit', -1)
    gigachat_tokens_used = request.session.get('gigachat_tokens_used', 0)
    openai_tokens_limit = request.session.get('openai_tokens_limit', 0)
    openai_tokens_used = request.session.get('openai_tokens_used', 0)
    
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
        'gigachat_tokens_limit': gigachat_tokens_limit,
        'gigachat_tokens_used': gigachat_tokens_used,
        'openai_tokens_limit': openai_tokens_limit,
        'openai_tokens_used': openai_tokens_used
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
    Поддерживает все типы токенов с лимитами GigaChat и OpenAI токенов.
    
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
        from django.db.models import Q
        access_token = TemporaryAccessToken.objects.filter(
            token=token,
            is_active=True
        ).filter(
            Q(expires_at__gt=timezone.now()) | Q(expires_at__isnull=True)
        ).first()
        
        if not access_token:
            return render(request, 'generator/invalid_token.html', {
                'token': token
            })
        
        # Создаём анонимную сессию
        request.session['access_token'] = str(token)
        request.session['token_type'] = access_token.token_type
        request.session['is_demo'] = (access_token.token_type == 'DEMO_FREE' or access_token.token_type.startswith('HIDDEN'))
        request.session['gigachat_tokens_limit'] = access_token.gigachat_tokens_limit
        request.session['gigachat_tokens_used'] = access_token.gigachat_tokens_used
        request.session['openai_tokens_limit'] = access_token.openai_tokens_limit
        request.session['openai_tokens_used'] = access_token.openai_tokens_used
        if access_token.expires_at:
            request.session['expires_at'] = access_token.expires_at.isoformat()
        else:
            request.session['expires_at'] = None
        # Для обратной совместимости
        request.session['daily_generations_left'] = -1
        
        # Обновляем информацию о последнем использовании
        access_token.last_used = timezone.now()
        access_token.current_ip = request.META.get('REMOTE_ADDR')
        access_token.save()
        
        # Привязка к пользователю Django по telegram_user_id (для сохранения истории)
        # Демо-токены из manual_token_generator (без telegram_user_id) остаются без привязки
        if access_token.telegram_user_id and not request.user.is_authenticated:
            from django.contrib.auth.models import User
            from django.contrib.auth import login
            import hashlib
            
            # Создаём уникальное имя пользователя на основе telegram_user_id
            username = f"tg_{access_token.telegram_user_id}"
            
            # Ищем или создаём пользователя Django
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f"tg{access_token.telegram_user_id}@ghostwriter.local",  # Фиктивный email
                    'is_active': True,
                    'is_staff': False,
                    'is_superuser': False,
                }
            )
            
            # Если пользователь только что создан, устанавливаем случайный пароль
            # (вход только по токену, пароль не используется)
            if created:
                user.set_unusable_password()
                user.save()
            
            # Авторизуем пользователя в Django (для привязки генераций)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
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
    Страница превышения лимита токенов
    
    Отображается когда исчерпаны лимиты токенов GigaChat и/или OpenAI.
    """
    token_type = request.session.get('token_type', 'DEMO_FREE')
    gigachat_tokens_limit = request.session.get('gigachat_tokens_limit', -1)
    gigachat_tokens_used = request.session.get('gigachat_tokens_used', 0)
    openai_tokens_limit = request.session.get('openai_tokens_limit', 0)
    openai_tokens_used = request.session.get('openai_tokens_used', 0)
    
    return render(request, 'generator/limit_exceeded.html', {
        'token_type': token_type,
        'gigachat_tokens_limit': gigachat_tokens_limit,
        'gigachat_tokens_used': gigachat_tokens_used,
        'openai_tokens_limit': openai_tokens_limit,
        'openai_tokens_used': openai_tokens_used
    })


def disclaimer_page(request):
    """
    Страница с полным текстом отказа от ответственности
    """
    return render(request, 'generator/disclaimer.html')

def openai_limit_exceeded_page(request):
    """
    Страница превышения лимита OpenAI токенов
    
    Отображается когда исчерпан только лимит OpenAI, но GigaChat доступен.
    """
    token_type = request.session.get('token_type', 'UNLIMITED')
    gigachat_tokens_limit = request.session.get('gigachat_tokens_limit', -1)
    gigachat_tokens_used = request.session.get('gigachat_tokens_used', 0)
    openai_tokens_limit = request.session.get('openai_tokens_limit', 0)
    openai_tokens_used = request.session.get('openai_tokens_used', 0)
    
    return render(request, 'generator/openai_limit_exceeded.html', {
        'token_type': token_type,
        'gigachat_tokens_limit': gigachat_tokens_limit,
        'gigachat_tokens_used': gigachat_tokens_used,
        'openai_tokens_limit': openai_tokens_limit,
        'openai_tokens_used': openai_tokens_used
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
                # Создаём бесплатный токен (бессрочный)
                from .models import TemporaryAccessToken
                from .tariffs import get_tariff_config
                
                tariff = get_tariff_config('DEMO_FREE')
                token = TemporaryAccessToken.objects.create(
                    token_type='DEMO_FREE',
                    expires_at=None,  # Бессрочный
                    gigachat_tokens_limit=tariff['gigachat_tokens'],
                    gigachat_tokens_used=0,
                    openai_tokens_limit=tariff['openai_tokens'],
                    openai_tokens_used=0,
                    is_active=True
                )
                
                # Формируем ссылку
                site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                token_url = f"{site_url}/auth/token/{token.token}/"
                
                # Отправляем ссылку пользователю
                message = (
                    f"🎁 Ваша ссылка (бесплатный старт):\n\n"
                    f"{token_url}\n\n"
                    f"📝 Тариф: Бесплатный старт\n"
                    f"⚡ GigaChat: {tariff['gigachat_tokens']:,} токенов\n"
                    f"🤖 OpenAI: {tariff['openai_tokens']:,} токенов\n"
                    f"📅 Срок: бессрочно"
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
                {'text': '🆓 Бесплатный старт', 'callback_data': 'demo_free'}
            ],
            [
                {'text': '📊 Базовый - 500₽/мес', 'callback_data': 'buy_basic'}
            ],
            [
                {'text': '⭐ Про - 1500₽/мес', 'callback_data': 'buy_pro'}
            ],
            [
                {'text': '🚀 Безлимит - 3500₽/мес', 'callback_data': 'buy_unlimited'}
            ]
        ]
    }
    
    text = (
        "👋 Добро пожаловать в Ghostwriter!\n\n"
        "Выберите тариф для доступа к генератору контента:\n\n"
        "🆓 <b>Бесплатный старт</b> - 10 000 GigaChat + 500 OpenAI (бессрочно, бесплатно)\n"
        "📊 <b>Базовый</b> - 50 000 GigaChat + 3 000 OpenAI (500₽/мес)\n"
        "⭐ <b>Про</b> - 200 000 GigaChat + 15 000 OpenAI (1 500₽/мес)\n"
        "🚀 <b>Безлимит</b> - ∞ GigaChat + 50 000 OpenAI (3 500₽/мес)\n\n"
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
        "token_type": "DEMO_FREE",  # или "BASIC", "PRO", "UNLIMITED", "HIDDEN_14D", "HIDDEN_30D", "DEVELOPER"
        "telegram_user_id": 123456789  # опционально, для защиты от мультиаккаунтов
    }
    
    Returns:
        JSON с данными токена:
        {
            "token": "uuid",
            "token_type": "DEMO_FREE",
            "expires_at": "2024-01-20T12:00:00Z" или null,
            "url": "http://site.com/auth/token/uuid/"
        }
    """
    import json
    from django.utils import timezone
    from datetime import timedelta
    from .models import TemporaryAccessToken
    from .tariffs import get_tariff_config
    
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
        data = json.loads(request.body) if request.body else {}
        
        token_type = data.get('token_type', 'DEMO_FREE')
        telegram_user_id = data.get('telegram_user_id')
        
        # Получаем конфигурацию тарифа
        tariff = get_tariff_config(token_type)
        if not tariff:
            return JsonResponse({
                'error': 'Invalid token type',
                'message': f'Unknown token type: {token_type}'
            }, status=400)
        
        # ЗАЩИТА ОТ МУЛЬТИАККАУНТОВ
        tariff_changed = False  # Флаг смены тарифа
        if telegram_user_id:
            from django.db.models import Q
            # Проверяем существующие активные токены для этого пользователя
            existing_tokens = TemporaryAccessToken.objects.filter(
                telegram_user_id=telegram_user_id,
                is_active=True
            )
            
            # Для DEMO_FREE - разрешаем только один активный токен
            if token_type == 'DEMO_FREE':
                demo_tokens = existing_tokens.filter(token_type='DEMO_FREE')
                # Проверяем, не истек ли токен (бессрочные или не истекшие)
                now_check = timezone.now()
                active_demo = demo_tokens.filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gte=now_check)
                )
                
                if active_demo.exists():
                    # Находим самый свежий токен
                    latest_token = active_demo.order_by('-created_at').first()
                    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                    existing_url = f"{site_url}/auth/token/{latest_token.token}/"
                    
                    return JsonResponse({
                        'error': 'Demo token already exists',
                        'message': 'У вас уже есть активный бесплатный токен. Один пользователь может иметь только один бесплатный токен.',
                        'existing_token_url': existing_url,
                        'existing_token_created': latest_token.created_at.isoformat()
                    }, status=409)
            
            # Для платных тарифов - проверяем активные подписки
            if token_type in ['BASIC', 'PRO', 'UNLIMITED']:
                # Если покупается платный тариф, а есть активный DEMO_FREE - деактивируем демо
                now_check = timezone.now()
                active_demo = existing_tokens.filter(
                    token_type='DEMO_FREE'
                ).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gte=now_check)
                )
                if active_demo.exists():
                    # Деактивируем все активные демо-токены при покупке платного тарифа
                    active_demo.update(is_active=False)
                
                # Проверяем активные платные подписки
                paid_tokens = existing_tokens.filter(
                    token_type__in=['BASIC', 'PRO', 'UNLIMITED'],
                    subscription_start__isnull=False
                )
                # Проверяем, не истекла ли подписка
                now_check = timezone.now()
                active_subscriptions = paid_tokens.filter(
                    next_renewal__gte=now_check
                )
                
                if active_subscriptions.exists():
                    # Находим активную подписку
                    active_sub = active_subscriptions.order_by('-created_at').first()
                    
                    # Если запрашивается тот же тариф - продлеваем существующий токен
                    if active_sub.token_type == token_type:
                        now = timezone.now()
                        # Продлеваем подписку
                        if tariff.get('is_subscription'):
                            active_sub.next_renewal = now + timedelta(days=tariff['duration_days'])
                            if not active_sub.subscription_start:
                                active_sub.subscription_start = now
                        # Обновляем лимиты (на случай если тариф изменился)
                        active_sub.gigachat_tokens_limit = tariff['gigachat_tokens']
                        active_sub.openai_tokens_limit = tariff['openai_tokens']
                        # Обновляем expires_at если не бессрочный
                        if tariff['duration_days'] is not None:
                            active_sub.expires_at = now + timedelta(days=tariff['duration_days'])
                        active_sub.is_active = True
                        active_sub.save()
                        
                        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                        token_url = f"{site_url}/auth/token/{active_sub.token}/"
                        
                        return JsonResponse({
                            'token': str(active_sub.token),
                            'token_type': active_sub.token_type,
                            'expires_at': active_sub.expires_at.isoformat() if active_sub.expires_at else None,
                            'url': token_url,
                            'created_at': active_sub.created_at.isoformat(),
                            'is_active': active_sub.is_active,
                            'gigachat_tokens_limit': active_sub.gigachat_tokens_limit,
                            'openai_tokens_limit': active_sub.openai_tokens_limit,
                            'renewed': True  # Флаг что токен был продлён
                        }, status=200)
                    else:
                        # Другой тариф - деактивируем старый и создаём новый (смена тарифа)
                        # История сохранится, так как telegram_user_id тот же и пользователь Django тот же
                        active_sub.is_active = False
                        active_sub.save(update_fields=['is_active'])
                        tariff_changed = True  # Отмечаем что произошла смена тарифа
                        # Продолжаем создание нового токена ниже (с тем же telegram_user_id)
        
        # Создаем новый токен
        now = timezone.now()
        
        # Определяем expires_at
        if tariff['duration_days'] is None:
            expires_at = None  # Бессрочный
        else:
            expires_at = now + timedelta(days=tariff['duration_days'])
        
        # Определяем subscription_start и next_renewal для подписок
        subscription_start = None
        next_renewal = None
        if tariff.get('is_subscription'):
            subscription_start = now
            next_renewal = now + timedelta(days=tariff['duration_days'])
        
        token = TemporaryAccessToken.objects.create(
            token_type=token_type,
            expires_at=expires_at,
            gigachat_tokens_limit=tariff['gigachat_tokens'],
            gigachat_tokens_used=0,
            openai_tokens_limit=tariff['openai_tokens'],
            openai_tokens_used=0,
            subscription_start=subscription_start,
            next_renewal=next_renewal,
            is_active=True,
            total_used=0,
            telegram_user_id=telegram_user_id  # Сохраняем для защиты от мультиаккаунтов
        )
        
        # Формируем URL токена
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        token_url = f"{site_url}/auth/token/{token.token}/"
        
        # Возвращаем данные токена
        response_data = {
            'token': str(token.token),
            'token_type': token.token_type,
            'expires_at': token.expires_at.isoformat() if token.expires_at else None,
            'url': token_url,
            'created_at': token.created_at.isoformat(),
            'is_active': token.is_active,
            'gigachat_tokens_limit': token.gigachat_tokens_limit,
            'openai_tokens_limit': token.openai_tokens_limit
        }
        
        # Добавляем флаг смены тарифа если была смена
        if tariff_changed:
            response_data['tariff_changed'] = True
        
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
            'expires_at': token_obj.expires_at.isoformat() if token_obj.expires_at else None,
            'created_at': token_obj.created_at.isoformat(),
            'gigachat_tokens_limit': token_obj.gigachat_tokens_limit,
            'gigachat_tokens_used': token_obj.gigachat_tokens_used,
            'openai_tokens_limit': token_obj.openai_tokens_limit,
            'openai_tokens_used': token_obj.openai_tokens_used,
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


@csrf_exempt
@require_POST
def api_track_subscription_click(request):
    """
    API endpoint для отслеживания кликов по кнопке "Купить доступ"
    
    POST /api/track-subscription-click/
    
    Body:
        {
            "page_url": "https://example.com/profile/",
            "page_name": "profile"
        }
    
    Returns:
        JsonResponse: Статус успешного логирования
    """
    try:
        from .models import SubscriptionButtonClick
        
        # Получаем данные из запроса
        import json
        data = json.loads(request.body) if request.body else {}
        
        page_url = data.get('page_url', request.META.get('HTTP_REFERER', ''))
        page_name = data.get('page_name', '')
        
        # Получаем пользователя или токен
        user = request.user if request.user.is_authenticated else None
        token = getattr(request, 'token', None)
        
        # Получаем техническую информацию
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referer = request.META.get('HTTP_REFERER', '')
        
        # Создаем запись о клике
        SubscriptionButtonClick.objects.create(
            user=user,
            token=token,
            page_url=page_url,
            page_name=page_name,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Click tracked successfully'
        })
    
    except Exception as e:
        print(f"Ошибка при логировании клика: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# PAYMENT API ENDPOINTS
# =============================================================================

@csrf_exempt
@require_POST
def api_create_payment(request):
    """
    API endpoint для создания записи о платеже
    
    POST /api/payments/create/
    {
        "external_id": "yookassa_payment_id",
        "telegram_user_id": 123456789,
        "telegram_username": "username",
        "amount": 299.00,
        "payment_system": "yookassa",
        "description": "30 дней подписки",
        "payment_url": "https://yookassa.ru/..."
    }
    """
    import json
    from .models import Payment
    from decimal import Decimal
    
    # Проверка API ключа
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(settings, 'DJANGO_API_KEY', None)
    
    if expected_key and api_key != expected_key:
        return JsonResponse({
            'error': 'Unauthorized',
            'message': 'Invalid API key'
        }, status=401)
    
    try:
        data = json.loads(request.body)
        
        external_id = data.get('external_id')
        telegram_user_id = data.get('telegram_user_id')
        amount = data.get('amount')
        
        if not external_id or not telegram_user_id or not amount:
            return JsonResponse({
                'error': 'Missing required fields',
                'message': 'external_id, telegram_user_id and amount are required'
            }, status=400)
        
        # Проверяем, не существует ли уже такой платёж
        if Payment.objects.filter(external_id=external_id).exists():
            return JsonResponse({
                'error': 'Payment already exists',
                'message': f'Payment with external_id {external_id} already exists'
            }, status=409)
        
        # Создаём запись о платеже
        payment = Payment.objects.create(
            external_id=external_id,
            telegram_user_id=telegram_user_id,
            telegram_username=data.get('telegram_username', ''),
            amount=Decimal(str(amount)),
            payment_system=data.get('payment_system', 'yookassa'),
            description=data.get('description', '30 дней подписки GhostCopywriter'),
            payment_url=data.get('payment_url', ''),
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'payment_id': str(payment.id),
            'external_id': payment.external_id,
            'status': payment.status
        }, status=201)
    
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
@require_POST
def api_yookassa_webhook(request):
    """
    Webhook endpoint для обработки уведомлений от ЮКасса
    
    POST /api/payments/yookassa/webhook/
    
    ЮКасса отправляет уведомления о событиях:
    - payment.succeeded: Платёж успешно завершён
    - payment.canceled: Платёж отменён
    - refund.succeeded: Возврат выполнен
    
    После успешного платежа автоматически создаётся токен
    и отправляется уведомление пользователю в Telegram.
    """
    import json
    import hmac
    import hashlib
    from django.utils import timezone
    from datetime import timedelta
    from .models import Payment, TemporaryAccessToken
    
    try:
        # Парсим данные от ЮКасса
        data = json.loads(request.body)
        event_type = data.get('event')
        payment_object = data.get('object', {})
        
        print(f"ЮКасса webhook: {event_type}")
        print(f"Payment object: {json.dumps(payment_object, indent=2)}")
        
        if event_type == 'payment.succeeded':
            # Платёж успешен
            external_id = payment_object.get('id')
            metadata = payment_object.get('metadata', {})
            
            # Ищем платёж в базе
            try:
                payment = Payment.objects.get(external_id=external_id)
            except Payment.DoesNotExist:
                # Создаём запись, если её нет (на случай если бот не сохранил)
                telegram_user_id = metadata.get('telegram_user_id')
                telegram_username = metadata.get('telegram_username', '')
                
                if not telegram_user_id:
                    print(f"WARNING: No telegram_user_id in metadata for payment {external_id}")
                    return JsonResponse({'status': 'ok'})
                
                payment = Payment.objects.create(
                    external_id=external_id,
                    telegram_user_id=telegram_user_id,
                    telegram_username=telegram_username,
                    amount=payment_object.get('amount', {}).get('value', 299),
                    payment_system='yookassa',
                    status='pending'
                )
            
            # Обновляем статус платежа
            payment.status = 'succeeded'
            payment.paid_at = timezone.now()
            payment.metadata = payment_object
            
            # Определяем тип тарифа из metadata
            tariff_type = metadata.get('tariff', 'BASIC')
            
            # Получаем конфигурацию тарифа
            from .tariffs import get_tariff_config
            tariff = get_tariff_config(tariff_type)
            
            if not tariff:
                print(f"WARNING: Unknown tariff type {tariff_type}, using BASIC")
                tariff = get_tariff_config('BASIC')
            
            # Создаём токен с правильными лимитами
            now = timezone.now()
            
            if tariff['duration_days'] is None:
                expires_at = None
            else:
                expires_at = now + timedelta(days=tariff['duration_days'])
            
            subscription_start = None
            next_renewal = None
            if tariff.get('is_subscription'):
                subscription_start = now
                next_renewal = now + timedelta(days=tariff['duration_days'])
            
            token = TemporaryAccessToken.objects.create(
                token_type=tariff_type,
                expires_at=expires_at,
                gigachat_tokens_limit=tariff['gigachat_tokens'],
                gigachat_tokens_used=0,
                openai_tokens_limit=tariff['openai_tokens'],
                openai_tokens_used=0,
                subscription_start=subscription_start,
                next_renewal=next_renewal,
                is_active=True,
                telegram_user_id=telegram_user_id  # Сохраняем для защиты от мультиаккаунтов
            )
            
            payment.token = token
            payment.save()
            
            # Формируем URL токена
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            token_url = f"{site_url}/auth/token/{token.token}/"
            
            # Отправляем уведомление в Telegram
            send_payment_success_notification(
                payment.telegram_user_id,
                token_url,
                token.expires_at,
                tariff_type
            )
            
            print(f"✅ Платёж {external_id} успешно обработан. Токен: {token.token}, тариф: {tariff_type}")
        
        elif event_type == 'payment.canceled':
            # Платёж отменён
            external_id = payment_object.get('id')
            
            try:
                payment = Payment.objects.get(external_id=external_id)
                payment.status = 'canceled'
                payment.metadata = payment_object
                payment.save()
                print(f"❌ Платёж {external_id} отменён")
            except Payment.DoesNotExist:
                print(f"WARNING: Payment {external_id} not found for cancellation")
        
        elif event_type == 'refund.succeeded':
            # Возврат выполнен
            payment_id = payment_object.get('payment_id')
            
            try:
                payment = Payment.objects.get(external_id=payment_id)
                payment.status = 'refunded'
                payment.save()
                
                # Деактивируем токен при возврате
                if payment.token:
                    payment.token.is_active = False
                    payment.token.save()
                
                print(f"💸 Возврат для платежа {payment_id} выполнен")
            except Payment.DoesNotExist:
                print(f"WARNING: Payment {payment_id} not found for refund")
        
        return JsonResponse({'status': 'ok'})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    except Exception as e:
        print(f"Ошибка в yookassa webhook: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_confirm_payment(request, payment_id):
    """
    API endpoint для подтверждения платежа и привязки токена
    
    POST /api/payments/{payment_id}/confirm/
    {
        "token_uuid": "uuid токена"
    }
    
    Используется ботом после проверки статуса платежа вручную.
    """
    import json
    from django.utils import timezone
    from .models import Payment, TemporaryAccessToken
    
    # Проверка API ключа
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(settings, 'DJANGO_API_KEY', None)
    
    if expected_key and api_key != expected_key:
        return JsonResponse({
            'error': 'Unauthorized'
        }, status=401)
    
    try:
        data = json.loads(request.body) if request.body else {}
        token_uuid = data.get('token_uuid')
        
        # Ищем платёж
        try:
            payment = Payment.objects.get(external_id=payment_id)
        except Payment.DoesNotExist:
            return JsonResponse({
                'error': 'Payment not found'
            }, status=404)
        
        # Обновляем статус
        payment.status = 'succeeded'
        payment.paid_at = timezone.now()
        
        # Привязываем токен, если указан
        if token_uuid:
            try:
                token = TemporaryAccessToken.objects.get(token=token_uuid)
                payment.token = token
            except TemporaryAccessToken.DoesNotExist:
                pass
        
        payment.save()
        
        return JsonResponse({
            'success': True,
            'payment_id': str(payment.id),
            'status': payment.status
        })
    
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


# =============================================================================
# SUPPORT & REVIEWS API
# =============================================================================

@csrf_exempt
@require_POST
def api_support_create(request):
    """
    Создание тикета техподдержки.
    POST /api/support/create/
    Body: { "telegram_user_id", "telegram_username?", "subject?", "message", "source?" }
    """
    import json
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(settings, 'DJANGO_API_KEY', None)
    if expected_key and api_key != expected_key:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        data = json.loads(request.body) if request.body else {}
        if not data.get('telegram_user_id') or not data.get('message'):
            return JsonResponse({'error': 'telegram_user_id and message are required'}, status=400)
        ticket = SupportTicket.objects.create(
            telegram_user_id=data['telegram_user_id'],
            telegram_username=data.get('telegram_username'),
            subject=data.get('subject', ''),
            message=data['message'],
            source=data.get('source', 'bot')
        )
        return JsonResponse({
            'id': ticket.id,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat()
        }, status=201)
    except (KeyError, TypeError) as e:
        return JsonResponse({'error': 'Invalid payload', 'detail': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_reviews_create(request):
    """
    Создание отзыва.
    POST /api/reviews/create/
    Body: { "telegram_user_id", "telegram_username?", "text", "rating?" }
    """
    import json
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(settings, 'DJANGO_API_KEY', None)
    if expected_key and api_key != expected_key:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        data = json.loads(request.body) if request.body else {}
        if not data.get('telegram_user_id'):
            return JsonResponse({'error': 'telegram_user_id is required'}, status=400)
        rating = data.get('rating')
        if rating is not None and (not isinstance(rating, int) or rating < 1 or rating > 5):
            return JsonResponse({'error': 'rating must be 1-5'}, status=400)
        review = Review.objects.create(
            telegram_user_id=data['telegram_user_id'],
            telegram_username=data.get('telegram_username'),
            text=data.get('text', ''),
            rating=rating
        )
        return JsonResponse({
            'id': review.id,
            'moderation_status': review.moderation_status,
            'created_at': review.created_at.isoformat()
        }, status=201)
    except (KeyError, TypeError) as e:
        return JsonResponse({'error': 'Invalid payload', 'detail': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_GET
def api_support_stats(request):
    """
    Статистика обращений для админов.
    GET /api/support/stats/?days=30
    Требует X-API-Key.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count
    api_key = request.headers.get('X-API-Key')
    expected_key = getattr(settings, 'DJANGO_API_KEY', None)
    if expected_key and api_key != expected_key:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        days = int(request.GET.get('days', 30))
        days = min(max(days, 1), 365)
        cutoff = timezone.now() - timedelta(days=days)
        tickets = SupportTicket.objects.filter(created_at__gte=cutoff)
        by_status = dict(tickets.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        reviews = Review.objects.filter(created_at__gte=cutoff)
        reviews_pending = reviews.filter(moderation_status='pending').count()
        return JsonResponse({
            'period_days': days,
            'tickets_total': tickets.count(),
            'tickets_by_status': by_status,
            'reviews_total': reviews.count(),
            'reviews_pending': reviews_pending,
            'support_chats_open': SupportChat.objects.filter(status='open').count()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def send_payment_success_notification(telegram_user_id, token_url, expires_at, tariff_type='BASIC'):
    """
    Отправляет уведомление об успешной оплате в Telegram
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        token_url: Ссылка с токеном доступа
        expires_at: Дата истечения токена (может быть None)
        tariff_type: Тип тарифа
    """
    from django.conf import settings
    import requests
    from .tariffs import get_tariff_config
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN не настроен")
        return False
    
    tariff = get_tariff_config(tariff_type)
    tariff_name = tariff['name'] if tariff else tariff_type
    
    if expires_at:
        expires_str = expires_at.strftime('%d.%m.%Y %H:%M')
    else:
        expires_str = "бессрочно"
    
    message = (
        "✅ <b>Оплата прошла успешно!</b>\n\n"
        "🎉 Спасибо за покупку подписки GhostCopywriter!\n\n"
        f"📝 <b>Ваш тариф:</b> {tariff_name}\n"
        f"📅 <b>Активен до:</b> {expires_str}\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n{token_url}\n\n"
        "💡 <i>Сохраните эту ссылку - она работает как логин!</i>"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': telegram_user_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Уведомление отправлено пользователю {telegram_user_id}")
            return True
        else:
            print(f"❌ Ошибка отправки уведомления: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Исключение при отправке уведомления: {e}")
        return False