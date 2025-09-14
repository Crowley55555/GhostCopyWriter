import os
import requests
from openai import OpenAI

# Инициализируем OpenAI клиента для генерации промптов
openai_client = None
if os.environ.get('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    print("✅ OpenAI клиент для промптов инициализирован")

# OpenAI DALL-E настройки (используем тот же клиент)

def generate_image_prompt_from_text(text, form_data):
    """
    Генерирует промпт для генератора изображения на основе текста поста и параметров формы (через OpenAI).
    """
    print(f"=== Flask: generate_image_prompt_from_text вызван ===")
    print(f"Text: {text[:100]}...")
    print(f"Form data: {form_data}")
    
    # Проверяем наличие OpenAI клиента
    if not openai_client:
        print("⚠️ OpenAI API не настроен, используем mock промпт")
        topic = form_data.get('topic', 'неизвестная тема') if form_data else 'контент'
        mock_prompt = f"Яркая современная иллюстрация на тему '{topic}' для социальных сетей, цифровая живопись, яркие цвета, профессиональный дизайн"
        print(f"✅ Mock промпт: {mock_prompt}")
        return mock_prompt
    
    sys_prompt = (
        "Ты — креативный визуализатор. Проанализируй следующий текст поста для соцсетей и выдели ключевые визуальные образы, которые должны быть отражены на иллюстрации. Сформулируй короткий, ёмкий промпт для генерации изображения в стиле соцсетей. Учитывай платформу, аудиторию, стиль и цель поста."
    )
    user_prompt = f"""Текст поста: {text}\nПлатформа: {form_data.get('platform', '')}\nАудитория: {', '.join(form_data.get('audience', [])) if form_data.get('audience') else ''}\nСтиль: {', '.join(form_data.get('delivery_style', [])) if form_data.get('delivery_style') else ''}\nЦель: {', '.join(form_data.get('content_purpose', [])) if form_data.get('content_purpose') else ''}"""
    
    try:
        print("🤖 Генерируем промпт для изображения через OpenAI...")
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        prompt = response.choices[0].message.content
        print(f"✅ Промпт сгенерирован через OpenAI: {prompt}")
        return prompt.strip()
    except Exception as e:
        print(f"❌ Ошибка при генерации промпта через OpenAI: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_image_dalle(image_prompt):
    """Генерация изображения через OpenAI DALL-E"""
    print(f"=== Flask: generate_image_dalle вызван ===")
    print(f"Image prompt: {image_prompt}")
    
    # Проверяем наличие OpenAI клиента
    if not openai_client:
        print("⚠️ OpenAI API не настроен, используем mock изображение")
        # Возвращаем placeholder изображение
        mock_image_url = "https://via.placeholder.com/512x512/007bff/ffffff?text=DALL-E+Mock+Image"
        print(f"✅ Mock изображение: {mock_image_url}")
        return mock_image_url
    
    try:
        print("🎨 Генерируем изображение через OpenAI DALL-E...")
        
        # Ограничиваем длину промпта (DALL-E имеет лимит)
        if len(image_prompt) > 1000:
            image_prompt = image_prompt[:1000]
            print(f"⚠️ Промпт обрезан до 1000 символов")
        
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        print(f"✅ Изображение получено от DALL-E: {image_url}")
        return image_url
        
    except Exception as e:
        print(f"❌ Ошибка при генерации изображения через DALL-E: {e}")
        import traceback
        traceback.print_exc()
        
        # Пробуем DALL-E 2 как fallback
        try:
            print("🔄 Пробуем DALL-E 2 как fallback...")
            response = openai_client.images.generate(
                model="dall-e-2",
                prompt=image_prompt[:1000],  # DALL-E 2 имеет меньший лимит
                size="512x512",
                n=1,
            )
            image_url = response.data[0].url
            print(f"✅ Изображение получено от DALL-E 2: {image_url}")
            return image_url
        except Exception as e2:
            print(f"❌ DALL-E 2 тоже не сработал: {e2}")
            # Возвращаем mock изображение при ошибке
            mock_image_url = "https://via.placeholder.com/512x512/dc3545/ffffff?text=DALL-E+Error"
            return mock_image_url

def save_image_locally(image_url, save_path):
    """Сохранение изображения локально"""
    try:
        print(f"💾 Сохраняем изображение локально: {save_path}")
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            with open(save_path, 'wb') as file:
                file.write(response.content)
            print(f"✅ Изображение сохранено: {save_path}")
            return True
        else:
            print(f"❌ Не удалось скачать изображение. Статус: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка при сохранении изображения: {e}")
        return False 