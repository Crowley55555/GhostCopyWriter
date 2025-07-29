import os
import json
from flask import Flask, request, jsonify
from .text_gen import generate_text
from .image_gen import generate_image_prompt_from_text, generate_image_midjourney
from .crypto_utils import encrypt_data, decrypt_data

app = Flask(__name__)

@app.route('/generate-text', methods=['POST'])
def generate_text_route():
    encrypted = request.json.get('data')
    decrypted = decrypt_data(encrypted)
    payload = json.loads(decrypted.decode())
    # Генерируем текст
    text = generate_text(payload)
    # Генерируем промпт для изображения (по аналогии с gigachat_api.py)
    image_prompt = generate_image_prompt_from_text(text, payload) if text else None
    # Возвращаем текст и промпт для изображения (оба зашифрованы)
    result = {
        'text': text,
        'image_prompt': image_prompt
    }
    encrypted_result = encrypt_data(json.dumps(result).encode())
    return jsonify({'data': encrypted_result})

@app.route('/generate-image', methods=['POST'])
def generate_image_route():
    encrypted = request.json.get('data')
    decrypted = decrypt_data(encrypted)
    payload = json.loads(decrypted.decode())
    image_prompt = payload.get('image_prompt') or payload.get('prompt')
    image_url = generate_image_midjourney(image_prompt)
    encrypted_result = encrypt_data(json.dumps({'image_url': image_url}).encode())
    return jsonify({'data': encrypted_result})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 