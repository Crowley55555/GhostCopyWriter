#!/usr/bin/env python3
"""
Клиент для подключения Django к Flask Generator API

Обеспечивает безопасную связь между Django и Flask приложениями
через зашифрованные HTTP запросы.

Функции:
- generate_text_and_prompt(): Генерация текста и промпта для изображения
- generate_image(): Генерация изображения по промпту
- encrypt_data() / decrypt_data(): Шифрование/расшифровка данных
"""

# =============================================================================
# IMPORTS
# =============================================================================
import os
import json
import requests
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
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

# =============================================================================
# ENCRYPTION FUNCTIONS
# =============================================================================

def encrypt_data(data: dict) -> str:
    """
    Шифрует словарь данных для передачи в Flask API
    
    Args:
        data (dict): Данные для шифрования
    
    Returns:
        str: Зашифрованная строка
    """
    return cipher.encrypt(json.dumps(data).encode()).decode()

def decrypt_data(token: str) -> dict:
    """
    Расшифровывает данные, полученные от Flask API
    
    Args:
        token (str): Зашифрованная строка
    
    Returns:
        dict: Расшифрованные данные
    """
    return json.loads(cipher.decrypt(token.encode()).decode())

# =============================================================================
# API CLIENT FUNCTIONS
# =============================================================================

def generate_text_and_prompt(payload: dict) -> dict:
    """
    Генерирует текст и промпт для изображения через Flask API
    
    Отправляет зашифрованные параметры генерации в Flask приложение,
    получает сгенерированный текст и промпт для изображения.
    
    Args:
        payload (dict): Параметры генерации из Django формы
    
    Returns:
        dict: {'text': str, 'image_prompt': str}
    
    Raises:
        Exception: При ошибках подключения или обработки данных
    """
    url = f'{FLASK_GEN_URL}/generate-text'
    print(f"Отправка запроса к Flask API: {url}")
    print(f"Payload: {payload}")
    
    try:
        # Шифруем данные перед отправкой
        encrypted = encrypt_data(payload)
        print(f"Данные зашифрованы, длина: {len(encrypted)}")
        
        # Отправляем POST запрос к Flask API
        resp = requests.post(url, json={'data': encrypted}, timeout=30)
        print(f"Ответ Flask API: статус {resp.status_code}")
        
        resp.raise_for_status()
        response_data = resp.json()
        print(f"Response JSON: {response_data}")
        
        data = response_data['data']
        
        # Расшифровываем ответ от Flask
        try:
            result = decrypt_data(data)
            print(f"Данные расшифрованы: {result}")
            return result
        except Exception as decrypt_error:
            print(f"❌ Ошибка расшифровки ответа: {decrypt_error}")
            # Fallback: пробуем парсить как обычный JSON
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
    """
    Генерирует изображение через Flask API (DALL-E)
    
    Отправляет зашифрованный промпт в Flask приложение для генерации
    изображения через OpenAI DALL-E.
    
    Args:
        image_prompt (str): Промпт для генерации изображения
    
    Returns:
        str: URL сгенерированного изображения или None при ошибке
    """
    url = f'{FLASK_GEN_URL}/generate-image'
    print(f"Отправка запроса на генерацию изображения: {url}")
    print(f"Image prompt: {image_prompt}")
    
    try:
        # Шифруем промпт для отправки
        encrypted = encrypt_data({'image_prompt': image_prompt})
        
        # Отправляем запрос к Flask API
        resp = requests.post(url, json={'data': encrypted}, timeout=60)
        print(f"Ответ Flask API для изображения: статус {resp.status_code}")
        
        resp.raise_for_status()
        data = resp.json()['data']
        
        # Расшифровываем результат
        result = decrypt_data(data)
        print(f"Изображение получено: {result}")
        return result['image_url']
        
    except Exception as e:
        print(f"Ошибка при генерации изображения через Flask API: {e}")
        return None 