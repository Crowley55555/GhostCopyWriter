import os
import base64
import re
import time
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage
from gigachat import GigaChat as GigaChatDirect
from gigachat.models import Chat, Messages, MessagesRole

load_dotenv()

CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

# Отладочный вывод для диагностики проблем с переменными окружения
print("CLIENT_ID:", repr(CLIENT_ID))
print("CLIENT_SECRET:", repr(CLIENT_SECRET))
print("SCOPE:", repr(SCOPE))

# Проверяем, что все переменные заданы
if not CLIENT_ID or not CLIENT_SECRET:
    print("⚠️ ВНИМАНИЕ: CLIENT_ID или CLIENT_SECRET не заданы!")
    print("Убедитесь, что в .env файле есть переменные:")
    print("GIGACHAT_CLIENT_ID=ваш_client_id")
    print("GIGACHAT_CLIENT_SECRET=ваш_client_secret")
else:
    print("✅ Переменные окружения настроены корректно")

def _get_base64_credentials():
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    return base64.b64encode(creds).decode()

def _init_client():
    return GigaChat(
        credentials=_get_base64_credentials(),
        scope=SCOPE,
        verify_ssl_certs=False
    )

def _init_direct_client():
    """Инициализация прямого клиента GigaChat для генерации изображений"""
    return GigaChatDirect(
        credentials=_get_base64_credentials(),
        verify_ssl_certs=False
    )

def generate_text(data):
    try:
        print("Инициализация клиента GigaChat для генерации текста...")
        giga = _init_client()
        print("Клиент успешно инициализирован")
        
        messages = [
            SystemMessage(content="Ты — опытный SMM‑копирайтер."),
            HumanMessage(content=(
                f"Напиши {data['template_type']} пост в тоне {data['tone']} "
                f"для {data['platform']}. Тема: {data['topic']}"
            ))
        ]
        print("Отправка запроса на генерацию текста...")
        resp = giga.invoke(messages)
        print("Текст успешно сгенерирован")
        return resp.content
    except Exception as e:
        print(f"Ошибка при генерации текста: {e}")
        print(f"Тип ошибки: {type(e)}")
        if "429" in str(e) or "Too Many Requests" in str(e):
            return "⚠️ Превышен лимит запросов к GigaChat. Попробуйте позже."
        elif "401" in str(e) or "Unauthorized" in str(e):
            return "⚠️ Ошибка аутентификации. Проверьте настройки GigaChat."
        elif "403" in str(e) or "Forbidden" in str(e):
            return "⚠️ Доступ запрещен. Проверьте права доступа к GigaChat."
        else:
            return f"⚠️ Ошибка при генерации текста: {str(e)[:100]}"

def generate_image_gigachat(topic):
    """Генерация изображения через GigaChat API"""
    try:
        print("Инициализация клиента GigaChat для генерации изображения...")
        giga = _init_direct_client()
        print("Клиент для изображений успешно инициализирован")
        
        # Добавляем задержку между запросами
        time.sleep(1)
        
        # Создаем промпт для генерации изображения
        image_prompt = f"Создай иллюстрацию для SMM-поста на тему: {topic}. Стиль: современный, привлекательный, подходящий для социальных сетей."
        
        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content="Ты — талантливый художник, специализирующийся на создании иллюстраций для социальных сетей"),
                Messages(role=MessagesRole.USER, content=image_prompt)
            ],
            function_call="auto",
        )
        
        print("Отправка запроса на генерацию изображения...")
        response = giga.chat(payload)
        response_content = response.choices[0].message.content
        
        print("GigaChat image response:", response_content)
        
        # Извлекаем ID изображения из HTML-тега
        file_id = extract_image_id(response_content)
        
        if file_id:
            # Скачиваем изображение
            image_data = download_image(giga, file_id)
            return image_data
        else:
            print("Не удалось извлечь ID изображения из ответа")
            return None
            
    except Exception as e:
        print(f"Ошибка при генерации изображения через GigaChat: {e}")
        print(f"Тип ошибки: {type(e)}")
        if "429" in str(e) or "Too Many Requests" in str(e):
            print("Превышен лимит запросов к GigaChat")
        elif "401" in str(e) or "Unauthorized" in str(e):
            print("Ошибка аутентификации GigaChat")
        elif "403" in str(e) or "Forbidden" in str(e):
            print("Доступ запрещен к GigaChat")
        return None

def extract_image_id(response_content):
    """Извлекает ID изображения из HTML-ответа GigaChat"""
    try:
        # Парсим HTML с помощью BeautifulSoup
        soup = BeautifulSoup(response_content, "html.parser")
        img_tag = soup.find('img')
        
        if img_tag and img_tag.get('src'):
            file_id = img_tag.get('src')
            print(f"Извлечен ID изображения: {file_id}")
            return file_id
        else:
            # Альтернативный способ через регулярные выражения
            match = re.search(r'<img[^>]*src="([^"]+)"', response_content)
            if match:
                file_id = match.group(1)
                print(f"Извлечен ID изображения (regex): {file_id}")
                return file_id
                
        print("Не найден тег img в ответе")
        return None
        
    except Exception as e:
        print(f"Ошибка при извлечении ID изображения: {e}")
        return None

def download_image(giga_client, file_id):
    """Скачивает изображение по ID и возвращает base64 данные"""
    try:
        print(f"Скачиваем изображение с ID: {file_id}")
        image_response = giga_client.get_image(file_id)
        
        print(f"Тип ответа: {type(image_response)}")
        print(f"Атрибуты ответа: {dir(image_response)}")
        
        if image_response and hasattr(image_response, 'content'):
            content = image_response.content
            print(f"Тип content: {type(content)}")
            print(f"Размер контента: {len(content)} байт/символов")
            print(f"Первые 100 символов content: {str(content)[:100]}")
            
            # Проверяем тип content и обрабатываем соответственно
            if isinstance(content, str):
                # Если content - строка, возможно это уже base64
                if content.startswith('data:image'):
                    print("Content уже в формате data:image")
                    return content
                else:
                    # Если это строка, но не data:image, то это уже base64 данные
                    try:
                        import base64
                        # Проверяем, что это валидный base64
                        if len(content) > 1000:  # Должно быть достаточно длинным для изображения
                            result = f"data:image/jpeg;base64,{content}"
                            print(f"Обрабатываем строку как base64, длина: {len(content)}")
                            print(f"Base64 результат (первые 100 символов): {result[:100]}...")
                            return result
                        else:
                            print(f"Строка слишком короткая для изображения: {len(content)}")
                            return None
                    except Exception as e:
                        print(f"Ошибка при обработке строки как base64: {e}")
                        return None
            elif isinstance(content, bytes):
                # Если content - байты, кодируем в base64
                import base64
                image_base64 = base64.b64encode(content).decode('utf-8')
                result = f"data:image/jpeg;base64,{image_base64}"
                print(f"Base64 результат (первые 100 символов): {result[:100]}...")
                print(f"Длина base64: {len(image_base64)}")
                return result
            else:
                print(f"Неизвестный тип content: {type(content)}")
                return None
        else:
            print("Пустой ответ при скачивании изображения")
            print(f"image_response: {image_response}")
            return None
            
    except Exception as e:
        print(f"Ошибка при скачивании изображения: {e}")
        import traceback
        traceback.print_exc()
        
        # Попробуем альтернативный способ через requests
        try:
            print("Пробуем альтернативный способ через requests...")
            import requests
            from gigachat.client import GigaChat
            
            # Получаем токен доступа
            auth_response = requests.post(
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                headers={
                    "Authorization": f"Bearer {_get_base64_credentials()}",
                    "RqUID": "123456789",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"scope": SCOPE},
                verify=False
            )
            
            if auth_response.status_code == 200:
                access_token = auth_response.json().get("access_token")
                
                # Скачиваем изображение напрямую
                image_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                img_response = requests.get(image_url, headers=headers, verify=False)
                
                if img_response.status_code == 200:
                    import base64
                    image_base64 = base64.b64encode(img_response.content).decode('utf-8')
                    result = f"data:image/jpeg;base64,{image_base64}"
                    print(f"Альтернативный способ успешен, длина: {len(image_base64)}")
                    return result
                else:
                    print(f"Ошибка при скачивании через requests: {img_response.status_code}")
                    return None
            else:
                print(f"Ошибка аутентификации: {auth_response.status_code}")
                return None
                
        except Exception as alt_e:
            print(f"Альтернативный способ также не сработал: {alt_e}")
            return None
