import os
import requests
from openai import OpenAI

# Инициализируем OpenAI клиента для генерации промптов
openai_client = None
if os.environ.get('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    print("✅ OpenAI клиент для промптов инициализирован")

# CometAPI настройки
COMETAPI_KEY = os.environ.get('COMETAPI_KEY')
COMETAPI_URL = os.environ.get('COMETAPI_URL', 'https://api.cometapi.com/v1')

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

def generate_image_cometapi(image_prompt):
    """Генерация изображения через CometAPI"""
    print(f"=== Flask: generate_image_cometapi вызван ===")
    print(f"Image prompt: {image_prompt}")
    
    # Проверяем наличие API ключа
    if not COMETAPI_KEY:
        print("⚠️ COMETAPI_KEY не установлен, используем mock изображение")
        # Возвращаем placeholder изображение
        mock_image_url = "https://via.placeholder.com/512x512/28a745/ffffff?text=CometAPI+Mock+Image"
        print(f"✅ Mock изображение: {mock_image_url}")
        return mock_image_url
    
    try:
        print("🎨 Генерируем изображение через CometAPI...")
        url = f"{COMETAPI_URL}/generate"
        headers = {
            'Authorization': f'Bearer {COMETAPI_KEY}',
            'Content-Type': 'application/json'
        }
        data = {
            'prompt': image_prompt,
            'style': 'artistic',  # Художественный стиль для соцсетей
        }
        
        print(f"Отправляем запрос к CometAPI: {url}")
        response = requests.post(url, json=data, headers=headers, timeout=60)
        print(f"CometAPI ответ: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            image_url = response_data.get('image_url')
            print(f"✅ Изображение получено от CometAPI: {image_url}")
            return image_url
        else:
            print(f"❌ Ошибка CometAPI: {response.status_code}")
            print(f"Response: {response.text}")
            # Возвращаем mock изображение при ошибке
            mock_image_url = "https://via.placeholder.com/512x512/dc3545/ffffff?text=CometAPI+Error"
            return mock_image_url
            
    except Exception as e:
        print(f"❌ Ошибка при генерации изображения через CometAPI: {e}")
        import traceback
        traceback.print_exc()
        # Возвращаем mock изображение при ошибке
        mock_image_url = "https://via.placeholder.com/512x512/ffc107/000000?text=CometAPI+Exception"
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