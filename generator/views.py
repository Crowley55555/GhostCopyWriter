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

    def get_first_sentence(text):
        match = re.match(r'(.+?[.!?])(\
|\s|$)', text.strip(), re.DOTALL)
        return match.group(1) if match else text[:200]

    if request.method == 'POST' and form.is_valid():
        # count = request.session['generated_count']
        # if count >= 3:
        #     limit_reached = True
        #     result = "⚠️ Достигнут лимит бесплатных генераций. Зарегистрируйтесь, чтобы продолжить."
        # else:
        # Генерация текста поста
        result = generate_text(form.cleaned_data)
        # Генерация описания для картинки через GigaChat
        image_prompt = generate_image_gigachat(form.cleaned_data['topic'])
        print('GigaChat image prompt:', image_prompt)
        # Используем только первое предложение для Яндекс
        short_prompt = get_first_sentence(image_prompt)
        print('Short prompt for Yandex:', short_prompt)
        # Генерация картинки через Яндекс по короткому описанию
        raw_image = generate_image_yandex(short_prompt)
        print('Yandex image url:', raw_image)

        # Сохраняем в базу
        Generation.objects.create(
            platform=form.cleaned_data['platform'],
            template_type=form.cleaned_data['template_type'],
            tone=form.cleaned_data['tone'],
            topic=form.cleaned_data['topic'],
            result=result,
        )

        # Сохраняем изображение, если есть
        if raw_image:
            if raw_image.startswith("http"):
                image_url = raw_image
            else:
                filename = f"{request.session.session_key[:8]}_{form.cleaned_data['topic'][:20].replace(' ', '_')}.png"
                full_path = os.path.join(settings.MEDIA_ROOT, filename)
                match = re.search(r'base64,(.*)', raw_image)
                image_bytes = base64.b64decode(match.group(1)) if match else raw_image.encode()
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(image_bytes)
                image_url = settings.MEDIA_URL + filename

        # Увеличиваем счетчик
        # request.session['generated_count'] = count + 1

    return render(request, 'generator/index.html', {
        'form': form,
        'result': result,
        'image_url': image_url,
        'limit_reached': limit_reached,
    })
