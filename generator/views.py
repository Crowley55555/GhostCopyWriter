from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
import os, base64, re
from .forms import GenerationForm
from .gigachat_api import generate_text, generate_image_gigachat
from .yandex_image_api import generate_image as generate_image_yandex
from .models import Generation
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from .forms import RegisterForm, LoginForm, UserProfileForm, UserEditForm
from .models import UserProfile, Generation
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

def generator_view(request):
    result = None
    image_url = None
    limit_reached = False
    form = GenerationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        try:
            # Получаем данные из формы
            platform = form.cleaned_data['platform']
            template_type = form.cleaned_data['template_type']
            tone = form.cleaned_data['tone']
            topic = form.cleaned_data['topic']
            form_data = {
                'platform': platform,
                'template_type': template_type,
                'tone': tone,
                'topic': topic
            }
            # Генерируем текст
            result = generate_text(form_data)
            # Генерируем изображение
            image_data = generate_image_gigachat(topic)
            # Обрабатываем изображение
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
                    filename = f"generated_{topic[:20].replace(' ', '_')}.jpg"
                    full_path = os.path.join(settings.MEDIA_ROOT, filename)
                    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                    try:
                        image_bytes = base64.b64decode(image_data)
                        with open(full_path, "wb") as f:
                            f.write(image_bytes)
                        image_url = settings.MEDIA_URL + filename
                    except Exception as e:
                        image_url = None
            # Сохраняем результат в базу с image_url
            gen = Generation.objects.create(
                user=request.user if request.user.is_authenticated else None,
                platform=platform,
                template_type=template_type,
                tone=tone,
                topic=topic,
                result=result,
                image_url=image_url or ""
            )
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'result': result,
                    'image_url': image_url,
                    'limit_reached': limit_reached
                })
        except Exception as e:
            print(f"Ошибка генерации: {e}")
            if is_ajax:
                return JsonResponse({'success': False, 'error': str(e)})
    return render(request, 'generator/gigagenerator.html', {'form': form, 'result': result, 'image_url': image_url, 'limit_reached': limit_reached})

def regenerate_text(request):
    """Перегенерация только текста"""
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            platform = request.POST.get('platform')
            template_type = request.POST.get('template_type')
            tone = request.POST.get('tone')
            topic = request.POST.get('topic')
            
            if not all([platform, template_type, tone, topic]):
                return JsonResponse({
                    'success': False,
                    'error': 'Не все необходимые данные предоставлены'
                })
            
            # Создаем словарь с данными для генерации
            form_data = {
                'platform': platform,
                'template_type': template_type,
                'tone': tone,
                'topic': topic
            }
            
            # Генерируем новый текст
            result = generate_text(form_data)
            
            # Сохраняем в базу
            Generation.objects.create(
                platform=platform,
                template_type=template_type,
                tone=tone,
                topic=topic,
                result=result,
            )
            
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

def regenerate_image(request):
    """Перегенерация только изображения"""
    if request.method == 'POST':
        try:
            topic = request.POST.get('topic')
            
            if not topic:
                return JsonResponse({
                    'success': False,
                    'error': 'Тема не предоставлена'
                })
            
            # Генерируем новое изображение
            image_data = generate_image_gigachat(topic)
            
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
                        
                        return JsonResponse({
                            'success': True,
                            'image_url': image_url,
                            'message': 'Изображение успешно перегенерировано'
                        })
                        
                    except Exception as e:
                        print(f"Ошибка при сохранении base64 изображения: {e}")
                        # Возвращаемся к base64 как fallback
                        return JsonResponse({
                            'success': True,
                            'image_url': image_data,
                            'message': 'Изображение перегенерировано (base64)'
                        })
                elif image_data.startswith("http"):
                    # Это URL (если вдруг вернется)
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
                    'error': 'Не удалось сгенерировать изображение'
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
                date_of_birth=reg_data.get('date_of_birth', None),
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
