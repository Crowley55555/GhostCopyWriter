import os
import json
import requests
from cryptography.fernet import Fernet

FLASK_GEN_URL = os.environ.get('FLASK_GEN_URL', 'http://localhost:5000')
ENCRYPTION_KEY = os.environ.get('GENERATOR_ENCRYPTION_KEY', 'test-key')
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_data(data: dict) -> str:
    return cipher.encrypt(json.dumps(data).encode()).decode()

def decrypt_data(token: str) -> dict:
    return json.loads(cipher.decrypt(token.encode()).decode())

def generate_text_and_prompt(payload: dict) -> dict:
    url = f'{FLASK_GEN_URL}/generate-text'
    encrypted = encrypt_data(payload)
    resp = requests.post(url, json={'data': encrypted})
    resp.raise_for_status()
    data = resp.json()['data']
    return decrypt_data(data)

def generate_image(image_prompt: str) -> str:
    url = f'{FLASK_GEN_URL}/generate-image'
    encrypted = encrypt_data({'image_prompt': image_prompt})
    resp = requests.post(url, json={'data': encrypted})
    resp.raise_for_status()
    data = resp.json()['data']
    return decrypt_data(data)['image_url'] 