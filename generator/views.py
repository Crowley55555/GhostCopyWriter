from django.shortcuts import render
from django.conf import settings
import os, base64, re
from .forms import GenerationForm
from .gigachat_api import generate_text, generate_image_gigachat
from .yandex_image_api import generate_image as generate_image_yandex
from .models import Generation

def index(request):
    result = None
    image_url = None
    limit_reached = False

    # if 'generated_count' not in request.session:
    #     request.session['generated_count'] = 0

    form = GenerationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        # count = request.session['generated_count']
        # if count >= 3:
        #     limit_reached = True
        #     result = "⚠️ Достигнут лимит бесплатных генераций. Зарегистрируйтесь, чтобы продолжить."
        # else:
        # Генерация текста поста
        result = generate_text(form.cleaned_data)
        
        # Генерация изображения через GigaChat
        image_data = generate_image_gigachat(form.cleaned_data['topic'])
        print('GigaChat image data:', image_data[:100] if image_data else None)

        # Сохраняем в базу
        Generation.objects.create(
            platform=form.cleaned_data['platform'],
            template_type=form.cleaned_data['template_type'],
            tone=form.cleaned_data['tone'],
            topic=form.cleaned_data['topic'],
            result=result,
        )

        # Обрабатываем изображение
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
                    
                except Exception as e:
                    print(f"Ошибка при сохранении base64 изображения: {e}")
                    # Возвращаемся к base64 как fallback
                    image_url = image_data
                    print("Используем base64 данные напрямую как fallback")
            elif image_data.startswith("http"):
                # Это URL (если вдруг вернется)
                image_url = image_data
                print("Используем URL изображения")
            else:
                # Сохраняем локально, если это base64 без префикса
                filename = f"{request.session.session_key[:8]}_{form.cleaned_data['topic'][:20].replace(' ', '_')}.jpg"
                full_path = os.path.join(settings.MEDIA_ROOT, filename)
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                
                # Декодируем base64 и сохраняем
                try:
                    image_bytes = base64.b64decode(image_data)
                    with open(full_path, "wb") as f:
                        f.write(image_bytes)
                    image_url = settings.MEDIA_URL + filename
                    print(f"Изображение сохранено локально: {image_url}")
                except Exception as e:
                    print(f"Ошибка при сохранении изображения: {e}")
                    image_url = None
        else:
            print("Нет данных изображения для обработки")

        # Увеличиваем счетчик
        # request.session['generated_count'] = count + 1

    return render(request, 'generator/index.html', {
        'form': form,
        'result': result,
        'image_url': image_url,
        'limit_reached': limit_reached,
    })
