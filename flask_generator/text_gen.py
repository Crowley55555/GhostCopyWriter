import openai
from .prompt_utils import assemble_prompt_from_criteria

def generate_text(data):
    system_prompt = assemble_prompt_from_criteria(data)
    user_prompt = f"Напиши пост для {data.get('platform', '')}. Тема: {data.get('topic', '')}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        text = response.choices[0].message['content']
        return text
    except Exception as e:
        return f"⚠️ Ошибка при генерации текста: {str(e)[:100]}" 