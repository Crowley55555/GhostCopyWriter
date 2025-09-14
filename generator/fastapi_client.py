import os
import json
import requests
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

FLASK_GEN_URL = os.environ.get('FLASK_GEN_URL', 'http://localhost:5000')
ENCRYPTION_KEY = os.environ.get('GENERATOR_ENCRYPTION_KEY')

if not ENCRYPTION_KEY:
    # Генерируем валидный ключ автоматически
    key = Fernet.generate_key()
    ENCRYPTION_KEY = key.decode()
    print(f"🔑 Django: Сгенерирован новый ключ: {ENCRYPTION_KEY}")
    print("💡 Добавьте этот ключ в ОБА .env файла:")
    print(f"GENERATOR_ENCRYPTION_KEY={ENCRYPTION_KEY}")
    print("🔄 Затем перезапустите приложения")

try:
    cipher = Fernet(ENCRYPTION_KEY.encode())
    print(f"✅ Django: Ключ шифрования инициализирован")
except ValueError as e:
    # Генерируем новый валидный ключ
    key = Fernet.generate_key()
    ENCRYPTION_KEY = key.decode()
    cipher = Fernet(key)
    print(f"🔑 Django: Сгенерирован исправленный ключ: {ENCRYPTION_KEY}")
    print("💡 Добавьте этот ключ в ОБА .env файла:")
    print(f"GENERATOR_ENCRYPTION_KEY={ENCRYPTION_KEY}")
    print("🔄 Затем перезапустите приложения")

def encrypt_data(data: dict) -> str:
    return cipher.encrypt(json.dumps(data).encode()).decode()

def decrypt_data(token: str) -> dict:
    return json.loads(cipher.decrypt(token.encode()).decode())

def generate_text_and_prompt(payload: dict) -> dict:
    url = f'{FLASK_GEN_URL}/generate-text'
    print(f"Отправка запроса к Flask API: {url}")
    print(f"Payload: {payload}")
    
    try:
        encrypted = encrypt_data(payload)
        print(f"Данные зашифрованы, длина: {len(encrypted)}")
        
        resp = requests.post(url, json={'data': encrypted}, timeout=30)
        print(f"Ответ Flask API: статус {resp.status_code}")
        
        resp.raise_for_status()
        response_data = resp.json()
        print(f"Response JSON: {response_data}")
        
        data = response_data['data']
        
        # Пробуем расшифровать данные
        try:
            result = decrypt_data(data)
            print(f"Данные расшифрованы: {result}")
            return result
        except Exception as decrypt_error:
            print(f"❌ Ошибка расшифровки ответа: {decrypt_error}")
            # Если не удалось расшифровать, пробуем как обычный JSON
            try:
                result = json.loads(data)
                print(f"Данные обработаны как JSON: {result}")
                return result
            except Exception as json_error:
                print(f"❌ Ошибка парсинга JSON: {json_error}")
                raise Exception(f"Не удалось обработать ответ от Flask: {data}")
    except requests.exceptions.ConnectionError as e:
        print(f"Ошибка подключения к Flask API: {e}")
        raise Exception("Flask Generator не запущен или недоступен")
    except requests.exceptions.Timeout as e:
        print(f"Таймаут при обращении к Flask API: {e}")
        raise Exception("Flask Generator не отвечает")
    except Exception as e:
        print(f"Ошибка при обращении к Flask API: {e}")
        raise

def generate_image(image_prompt: str) -> str:
    url = f'{FLASK_GEN_URL}/generate-image'
    print(f"Отправка запроса на генерацию изображения: {url}")
    print(f"Image prompt: {image_prompt}")
    
    try:
        encrypted = encrypt_data({'image_prompt': image_prompt})
        resp = requests.post(url, json={'data': encrypted}, timeout=60)
        print(f"Ответ Flask API для изображения: статус {resp.status_code}")
        
        resp.raise_for_status()
        data = resp.json()['data']
        result = decrypt_data(data)
        print(f"Изображение получено: {result}")
        return result['image_url']
    except Exception as e:
        print(f"Ошибка при генерации изображения через Flask API: {e}")
        return None 