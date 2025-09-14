import os
from prompt_utils import assemble_prompt_from_criteria

# Подключаем OpenAI API
from openai import OpenAI

# Инициализируем клиента только если есть API ключ
openai_client = None
if os.environ.get('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    print("✅ OpenAI клиент инициализирован")

def generate_text(data):
    """Генерация текста через OpenAI API (или mock для тестирования)"""
    print(f"=== Flask: generate_text вызван ===")
    print(f"Data: {data}")
    
    # Проверяем наличие OpenAI API ключа и клиента
    if not openai_client:
        print("⚠️ OPENAI_API_KEY не установлен, используем mock ответ")
        topic = data.get('topic', 'неизвестная тема')
        platform_list = data.get('platform_specific', [])
        platform = platform_list[0] if platform_list else 'социальная сеть'
        cta = data.get('cta', '')
        post_length = data.get('post_length', 'Средний')
        
        # Создаем mock пост на основе параметров
        if post_length == 'Очень короткий':
            mock_text = f"🚀 {topic}\n\nКраткий пост для {platform}.\n\n#{topic.lower().replace(' ', '')}"
        elif post_length == 'Короткий':
            mock_text = f"""🚀 {topic}

Интересный контент для {platform}! 

✨ Ключевые моменты:
• Современные решения
• Эффективные подходы

💡 {cta if cta else 'Узнайте больше!'}

#контент #{platform.lower()}"""
        elif post_length == 'Длинный':
            mock_text = f"""🚀 {topic}

Подробный анализ темы для платформы {platform}.

✨ Основные аспекты:
• Детальное изучение вопроса
• Практические рекомендации
• Экспертные мнения
• Реальные примеры

🔍 Глубокое погружение в тему позволяет:
- Лучше понять суть вопроса
- Найти оптимальные решения
- Избежать типичных ошибок

💡 {cta if cta else 'Изучайте больше и развивайтесь!'}

#детально #{topic.lower().replace(' ', '')} #{platform.lower()} #экспертиза"""
        else:  # Средний
            mock_text = f"""🚀 {topic}

Качественный контент для {platform}, созданный через Flask API.

✨ Основные преимущества:
• Быстрая генерация контента
• Адаптация под разные платформы  
• Современные технологии
• Гибкие настройки

💡 {cta if cta else 'Попробуйте сами и убедитесь в эффективности!'}

#flask #api #генерация #{platform.lower()}"""
        
        print(f"✅ Mock текст сгенерирован: {mock_text[:100]}...")
        return mock_text
    
    # Используем реальный OpenAI API
    try:
        print("🤖 Генерируем текст через OpenAI API...")
        system_prompt = assemble_prompt_from_criteria(data)
        user_prompt = f"Напиши пост для {data.get('platform', '')}. Тема: {data.get('topic', '')}"
        
        print(f"System prompt: {system_prompt[:100]}...")
        print(f"User prompt: {user_prompt}")
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        text = response.choices[0].message.content
        print(f"✅ Текст сгенерирован через OpenAI: {text[:100]}...")
        return text
    except Exception as e:
        print(f"❌ Ошибка при генерации текста через OpenAI: {e}")
        import traceback
        traceback.print_exc()
        return f"⚠️ Ошибка при генерации текста: {str(e)[:100]}" 