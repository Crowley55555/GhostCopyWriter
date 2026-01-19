
"""
Flask Generator API - Микросервис для генерации контента

Предоставляет API для генерации текста и изображений через OpenAI:
- Генерация текста: GPT-3.5-turbo
- Генерация промптов: GPT-3.5-turbo  
- Генерация изображений: DALL-E 3/2

Все данные передаются в зашифрованном виде (Fernet encryption)
"""

# =============================================================================
# IMPORTS
# =============================================================================
import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Импортируем модули генерации
from text_gen import generate_text
from image_gen import generate_image_prompt_from_text, generate_image_dalle
from crypto_utils import encrypt_data, decrypt_data

# =============================================================================
# FLASK APP INITIALIZATION
# =============================================================================
app = Flask(__name__)

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint для проверки статуса API
    
    Returns:
        JSON: Статус сервера и список доступных endpoints
    """
    return jsonify({
        'status': 'ok',
        'message': 'Flask Generator API is running',
        'endpoints': ['/generate-text', '/generate-image', '/health']
    })

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """
    Тестовый endpoint для проверки работоспособности API
    
    Returns:
        JSON: Информация о запросе (без шифрования)
    """
    return jsonify({
        'status': 'success',
        'message': 'Flask API работает',
        'method': request.method,
        'data': request.get_json() if request.method == 'POST' else None
    })

@app.route('/generate-text', methods=['POST'])
def generate_text_route():
    """
    Endpoint для генерации текста и промпта изображения
    
    Принимает зашифрованные параметры генерации от Django приложения,
    генерирует текст через OpenAI GPT и промпт для изображения,
    возвращает зашифрованный результат.
    
    Request format:
        POST /generate-text
        Content-Type: application/json
        Body: {"data": "encrypted_form_parameters"}
    
    Response format:
        {"data": "encrypted_result_with_text_and_image_prompt"}
    
    Returns:
        JSON: Зашифрованный результат с текстом и промптом для изображения
    """
    try:
        print("=== Flask API: generate-text вызван ===")
        request_data = request.get_json()
        print(f"Request data: {request_data}")
        
        # Проверяем наличие зашифрованных данных
        encrypted = request_data.get('data')
        if not encrypted:
            return jsonify({'error': 'No encrypted data provided'}), 400
            
        print(f"Encrypted data length: {len(encrypted)}")
        
        # Расшифровываем параметры генерации
        try:
            decrypted = decrypt_data(encrypted)
            print(f"Decrypted type: {type(decrypted)}")
            
            # Парсим JSON из расшифрованных данных
            if isinstance(decrypted, bytes):
                payload = json.loads(decrypted.decode())
            else:
                payload = json.loads(decrypted)
            print(f"Parsed payload: {payload}")
        except Exception as decrypt_error:
            print(f"ERROR: Ошибка расшифровки: {decrypt_error}")
            # Fallback на тестовые данные
            payload = {'topic': 'Тестовая тема', 'platform_specific': ['VK']}
            print(f"Используем fallback payload: {payload}")
        
        # Генерируем текст через OpenAI или mock
        text = generate_text(payload)
        print(f"Generated text: {text[:100]}...")
        
        # Генерируем промпт для изображения
        image_prompt = generate_image_prompt_from_text(text, payload) if text else None
        print(f"Generated image prompt: {image_prompt}")
        
        # Подготавливаем результат
        result = {
            'text': text,
            'image_prompt': image_prompt
        }
        
        # Шифруем и возвращаем результат
        encrypted_result = encrypt_data(json.dumps(result).encode())
        print(f"OK: Результат зашифрован, длина: {len(encrypted_result)}")
        return jsonify({'data': encrypted_result})
        
    except Exception as e:
        print(f"ERROR: Error in generate_text_route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/generate-image', methods=['POST'])
def generate_image_route():
    """
    Endpoint для генерации изображений через DALL-E
    
    Принимает зашифрованный промпт от Django приложения,
    генерирует изображение через OpenAI DALL-E 3/2,
    возвращает зашифрованный URL изображения.
    
    Request format:
        POST /generate-image
        Content-Type: application/json
        Body: {"data": "encrypted_image_prompt"}
    
    Response format:
        {"data": "encrypted_image_url"}
    
    Returns:
        JSON: Зашифрованный URL сгенерированного изображения
    """
    try:
        print("=== Flask API: generate-image вызван ===")
        request_data = request.get_json()
        print(f"Request data: {request_data}")
        
        # Проверяем наличие зашифрованных данных
        encrypted = request_data.get('data')
        if not encrypted:
            return jsonify({'error': 'No encrypted data provided'}), 400
            
        # Расшифровываем промпт изображения
        decrypted = decrypt_data(encrypted)
        if isinstance(decrypted, bytes):
            payload = json.loads(decrypted.decode())
        else:
            payload = json.loads(decrypted)
            
        print(f"Decrypted payload: {payload}")
        
        # Извлекаем промпт для изображения
        image_prompt = payload.get('image_prompt') or payload.get('prompt')
        print(f"Image prompt: {image_prompt}")
        
        # Генерируем изображение через DALL-E
        image_url = generate_image_dalle(image_prompt)
        print(f"Generated image URL: {image_url}")
        
        # Шифруем и возвращаем результат
        encrypted_result = encrypt_data(json.dumps({'image_url': image_url}).encode())
        return jsonify({'data': encrypted_result})
        
    except Exception as e:
        print(f"ERROR: Error in generate_image_route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == '__main__':
    print("INFO: Запуск Flask Generator API...")
    print("INFO: Доступные endpoints:")
    print("   GET  / - health check")
    print("   POST /test - тестовый endpoint")
    print("   POST /generate-text - генерация текста и промпта")
    print("   POST /generate-image - генерация изображения")
    print("INFO: Сервер запускается на http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True) 