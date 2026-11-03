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

# `load_dotenv()` отсюда убран (раунд исправлений 2а.2, замечание 1):
# `.env` загружается ровно один раз в `ghostwriter/settings.py`.
# `FLASK_GEN_URL` и ключ шифрования читаются ленивыми функциями —
# при импорте модуля побочных эффектов нет: ни чтения env, ни печати
# ключей в stdout, ни генерации Fernet-ключей. Flask-клиент снят с
# пути запроса (решение владельца 2026-10-07), эти функции сейчас
# не вызываются из `views.py`, но файл остаётся на будущее.

_cipher_cache = None


def _get_flask_url():
    """Ленивое чтение URL Flask-сервиса. Default совпадает с прежним модульным"""
    return os.environ.get('FLASK_GEN_URL', 'http://localhost:5000')


def _get_cipher():
    """
    Ленивая инициализация Fernet. Прежние побочные эффекты (генерация
    ключа и `print` в stdout при пустом env) убраны: модуль импортируется
    из `views.py` при старте Django — лишние print смешивались бы с
    текстом поста. Если ключа нет, функция сгенерирует валидный ключ
    в памяти, но не выведет его: клиенту Flask нужен тот же ключ в
    обеих средах, и настоящий ключ ставится в env.
    """
    global _cipher_cache
    if _cipher_cache is not None:
        return _cipher_cache
    encryption_key = os.environ.get('GENERATOR_ENCRYPTION_KEY')
    if not encryption_key:
        encryption_key = Fernet.generate_key().decode()
    try:
        _cipher_cache = Fernet(encryption_key.encode())
    except ValueError:
        _cipher_cache = Fernet(Fernet.generate_key())
    return _cipher_cache

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
    return _get_cipher().encrypt(json.dumps(data).encode()).decode()

def decrypt_data(token: str) -> dict:
    """
    Расшифровывает данные, полученные от Flask API
    
    Args:
        token (str): Зашифрованная строка
    
    Returns:
        dict: Расшифрованные данные
    """
    return json.loads(_get_cipher().decrypt(token.encode()).decode())

# =============================================================================
# API CLIENT FUNCTIONS
# =============================================================================

def generate_text_and_prompt(payload: dict, token=None) -> dict:
    """
    Генерирует текст и промпт для изображения через Flask API
    
    Отправляет зашифрованные параметры генерации в Flask приложение,
    получает сгенерированный текст и промпт для изображения.
    
    Args:
        payload (dict): Параметры генерации из Django формы
        token: TemporaryAccessToken для учёта токенов OpenAI (опционально)
    
    Returns:
        dict: {'text': str, 'image_prompt': str, 'tokens_used': int}
    
    Raises:
        Exception: При ошибках подключения или обработки данных
    """
    url = f'{_get_flask_url()}/generate-text'
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
            
            # Учитываем токены OpenAI (если Flask API вернул информацию о токенах)
            tokens_used = result.get('tokens_used', 0)
            if token and tokens_used > 0:
                try:
                    if not token.consume_openai_tokens(tokens_used):
                        # Лимит исчерпан
                        return {
                            'text': 'WARNING: Лимит токенов OpenAI исчерпан. Пожалуйста, обновите подписку или выберите другой тариф.',
                            'image_prompt': None,
                            'tokens_used': 0
                        }
                except Exception as e:
                    print(f"Ошибка при учёте токенов OpenAI: {e}")
            
            return result
        except Exception as decrypt_error:
            print(f"ERROR: Ошибка расшифровки ответа: {decrypt_error}")
            # Fallback: пробуем парсить как обычный JSON
            try:
                result = json.loads(data)
                print(f"Данные обработаны как JSON: {result}")
                return result
            except Exception as json_error:
                print(f"ERROR: Ошибка парсинга JSON: {json_error}")
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
    url = f'{_get_flask_url()}/generate-image'
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
        
        # Учитываем токены OpenAI для DALL-E (примерная оценка: ~1000 токенов на изображение)
        tokens_used = result.get('tokens_used', 1000)
        if token:
            try:
                if not token.consume_openai_tokens(tokens_used):
                    # Лимит исчерпан
                    return None
            except Exception as e:
                print(f"Ошибка при учёте токенов OpenAI: {e}")
        
        return result.get('image_url')
        
    except Exception as e:
        print(f"Ошибка при генерации изображения через Flask API: {e}")
        return None 