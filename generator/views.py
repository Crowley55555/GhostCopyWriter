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
from datetime import datetime
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from .models import GenerationTemplate
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict

def generator_view(request):
    result = None
    image_url = None
    limit_reached = False
    form = GenerationForm(request.POST or None)
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if form.is_valid():
            try:
                # Получаем все данные из формы
                form_data = form.cleaned_data.copy()
                # Генерируем текст
                result = generate_text(form_data)
                # Новый пайплайн: генерируем промпт для изображения на основе текста
                from .gigachat_api import generate_image_prompt_from_text
                image_prompt = generate_image_prompt_from_text(result, form_data) if result else None
                # Генерируем изображение по новому промпту, если он есть, иначе по теме
                if image_prompt:
                    image_data = generate_image_gigachat(image_prompt)
                else:
                    image_data = generate_image_gigachat(form_data.get('topic', ''))
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
                # Сохраняем результат в базу с image_url
                gen = Generation.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    topic=form_data.get('topic', ''),
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
        else:
            if is_ajax:
                # Собираем ошибки формы для фронта
                errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
                return JsonResponse({'success': False, 'error': 'Некорректно заполнена форма', 'form_errors': errors})
    return render(request, 'generator/gigagenerator.html', {'form': form, 'result': result, 'image_url': image_url, 'limit_reached': limit_reached})

@csrf_exempt
def regenerate_text(request):
    """Перегенерация только текста"""
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
            # Сохраняем в базу
            Generation.objects.create(
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

@csrf_exempt
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
