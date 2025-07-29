import openai
import requests
import os

MIDJOURNEY_API_URL = os.environ.get('MIDJOURNEY_API_URL', 'https://api.midjourney.com/generate')
MIDJOURNEY_API_KEY = os.environ.get('MIDJOURNEY_API_KEY')

def generate_image_prompt_from_text(text, form_data):
    """
    Генерирует промпт для генератора изображения на основе текста поста и параметров формы (через OpenAI).
    """
    sys_prompt = (
        "Ты — креативный визуализатор. Проанализируй следующий текст поста для соцсетей и выдели ключевые визуальные образы, которые должны быть отражены на иллюстрации. Сформулируй короткий, ёмкий промпт для генерации изображения в стиле соцсетей. Учитывай платформу, аудиторию, стиль и цель поста."
    )
    user_prompt = f"""Текст поста: {text}\nПлатформа: {form_data.get('platform', '')}\nАудитория: {', '.join(form_data.get('audience', [])) if form_data.get('audience') else ''}\nСтиль: {', '.join(form_data.get('delivery_style', [])) if form_data.get('delivery_style') else ''}\nЦель: {', '.join(form_data.get('content_purpose', [])) if form_data.get('content_purpose') else ''}"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        prompt = response.choices[0].message['content']
        return prompt.strip()
    except Exception as e:
        return None

def generate_image_midjourney(image_prompt):
    headers = {'Authorization': f'Bearer {MIDJOURNEY_API_KEY}'}
    resp = requests.post(MIDJOURNEY_API_URL, json={'prompt': image_prompt}, headers=headers)
    if resp.status_code == 200:
        return resp.json().get('image_url')
    return None 