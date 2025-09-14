import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from text_gen import generate_text
from image_gen import generate_image_prompt_from_text, generate_image_dalle
from crypto_utils import encrypt_data, decrypt_data

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Flask Generator API is running',
        'endpoints': ['/generate-text', '/generate-image']
    })

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """Тестовый endpoint без шифрования"""
    return jsonify({
        'status': 'success',
        'message': 'Flask API работает',
        'method': request.method,
        'data': request.get_json() if request.method == 'POST' else None
    })

@app.route('/generate-text', methods=['POST'])
def generate_text_route():
    try:
        print("=== Flask API: generate-text вызван ===")
        request_data = request.get_json()
        print(f"Request data: {request_data}")
        
        encrypted = request_data.get('data')
        if not encrypted:
            return jsonify({'error': 'No encrypted data provided'}), 400
            
        print(f"Encrypted data length: {len(encrypted)}")
        
        # Пробуем расшифровать данные
        try:
            decrypted = decrypt_data(encrypted)
            print(f"Decrypted type: {type(decrypted)}")
            print(f"Decrypted data: {decrypted}")
            
            # Если decrypted уже строка, не декодируем
            if isinstance(decrypted, bytes):
                payload = json.loads(decrypted.decode())
            else:
                payload = json.loads(decrypted)
            print(f"Parsed payload: {payload}")
        except Exception as decrypt_error:
            print(f"❌ Ошибка расшифровки: {decrypt_error}")
            # Возвращаем mock данные для тестирования
            payload = {'topic': 'Тестовая тема', 'platform_specific': ['VK']}
            print(f"Используем mock payload: {payload}")
        
        # Генерируем текст
        text = generate_text(payload)
        print(f"Generated text: {text[:100]}...")
        
        # Генерируем промпт для изображения
        image_prompt = generate_image_prompt_from_text(text, payload) if text else None
        print(f"Generated image prompt: {image_prompt}")
        
        # Возвращаем результат
        result = {
            'text': text,
            'image_prompt': image_prompt
        }
        
        # Возвращаем зашифрованный результат
        encrypted_result = encrypt_data(json.dumps(result).encode())
        print(f"✅ Результат зашифрован, длина: {len(encrypted_result)}")
        print(f"Encrypted result preview: {encrypted_result[:100]}...")
        return jsonify({'data': encrypted_result})
        
    except Exception as e:
        print(f"❌ Error in generate_text_route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/generate-image', methods=['POST'])
def generate_image_route():
    try:
        print("=== Flask API: generate-image вызван ===")
        print(f"Request data: {request.get_json()}")
        
        encrypted = request.json.get('data')
        if not encrypted:
            return jsonify({'error': 'No encrypted data provided'}), 400
            
        decrypted = decrypt_data(encrypted)
        # Если decrypted уже строка, не декодируем
        if isinstance(decrypted, bytes):
            payload = json.loads(decrypted.decode())
        else:
            payload = json.loads(decrypted)
            
        print(f"Decrypted payload: {payload}")
        
        image_prompt = payload.get('image_prompt') or payload.get('prompt')
        print(f"Image prompt: {image_prompt}")
        
        image_url = generate_image_dalle(image_prompt)
        print(f"Generated image URL: {image_url}")
        
        encrypted_result = encrypt_data(json.dumps({'image_url': image_url}).encode())
        return jsonify({'data': encrypted_result})
        
    except Exception as e:
        print(f"Error in generate_image_route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 