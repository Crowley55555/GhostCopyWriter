#!/usr/bin/env python3
"""
Юнит-тесты для Flask приложения

Тестирует:
- API endpoints
- Шифрование/расшифровку данных
- Генерацию текста и изображений
- Обработку ошибок
- Mock ответы при отсутствии API ключей
"""

import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Добавляем путь к Flask приложению
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'flask_generator'))

from flask_generator.app import app
from flask_generator.crypto_utils import encrypt_data, decrypt_data
from flask_generator.text_gen import generate_text
from flask_generator.image_gen import generate_image_prompt_from_text, generate_image_dalle


class FlaskAppTest:
    """Базовый класс для тестов Flask приложения"""
    
    @pytest.fixture
    def client(self):
        """Создает тестовый клиент Flask"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client


class TestFlaskEndpoints(FlaskAppTest):
    """Тесты Flask endpoints"""
    
    def test_health_check(self, client):
        """Тест health check endpoint"""
        response = client.get('/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'Flask Generator API is running' in data['message']
        assert '/generate-text' in data['endpoints']
        assert '/generate-image' in data['endpoints']
    
    def test_test_endpoint(self, client):
        """Тест тестового endpoint"""
        # GET запрос
        response = client.get('/test')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['method'] == 'GET'
        
        # POST запрос
        test_data = {'test': 'data'}
        response = client.post('/test', json=test_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['method'] == 'POST'
        assert data['data'] == test_data
    
    def test_generate_text_endpoint_no_data(self, client):
        """Тест endpoint генерации текста без данных"""
        response = client.post('/generate-text', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'No encrypted data provided' in data['error']
    
    @patch.dict(os.environ, {'GENERATOR_ENCRYPTION_KEY': 'test_key_32_bytes_long_for_fernet!='})
    def test_generate_text_endpoint_with_mock_data(self, client):
        """Тест генерации текста с mock данными"""
        # Подготавливаем тестовые данные
        test_payload = {
            'topic': 'Тестовая тема',
            'platform_specific': ['VK'],
            'post_length': 'Короткий'
        }
        
        # Шифруем данные (используем временный ключ)
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        cipher = Fernet(key)
        encrypted = cipher.encrypt(json.dumps(test_payload).encode()).decode()
        
        # Мокаем функции шифрования
        with patch('flask_generator.app.decrypt_data') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(test_payload).encode()
            
            response = client.post('/generate-text', json={'data': encrypted})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'data' in data


class TestCryptoUtils:
    """Тесты функций шифрования"""
    
    @patch.dict(os.environ, {'GENERATOR_ENCRYPTION_KEY': 'test_key_32_bytes_long_for_fernet!='})
    def test_encrypt_decrypt_cycle(self):
        """Тест цикла шифрование-расшифровка"""
        # Перезагружаем модуль с новым ключом
        import importlib
        import flask_generator.crypto_utils as crypto
        importlib.reload(crypto)
        
        test_data = b'{"test": "data", "number": 123}'
        
        # Шифруем
        encrypted = crypto.encrypt_data(test_data)
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        
        # Расшифровываем
        decrypted = crypto.decrypt_data(encrypted)
        assert decrypted == test_data
    
    def test_encrypt_empty_data(self):
        """Тест шифрования пустых данных"""
        with patch.dict(os.environ, {'GENERATOR_ENCRYPTION_KEY': 'test_key_32_bytes_long_for_fernet!='}):
            import importlib
            import flask_generator.crypto_utils as crypto
            importlib.reload(crypto)
            
            encrypted = crypto.encrypt_data(b'')
            decrypted = crypto.decrypt_data(encrypted)
            assert decrypted == b''


class TestTextGeneration:
    """Тесты генерации текста"""
    
    @patch.dict(os.environ, {}, clear=True)  # Убираем OPENAI_API_KEY
    def test_generate_text_mock_mode(self):
        """Тест генерации текста в mock режиме"""
        # Перезагружаем модуль без API ключа
        import importlib
        import flask_generator.text_gen as text_gen
        importlib.reload(text_gen)
        
        test_data = {
            'topic': 'Искусственный интеллект',
            'platform_specific': ['VK'],
            'post_length': 'Короткий',
            'cta': 'Узнать больше'
        }
        
        result = text_gen.generate_text(test_data)
        
        assert isinstance(result, str)
        assert 'Искусственный интеллект' in result
        assert 'VK' in result
        assert 'Узнать больше' in result
        assert len(result) > 50  # Проверяем, что текст не пустой
    
    @patch('flask_generator.text_gen.openai_client')
    def test_generate_text_openai_mode(self, mock_client):
        """Тест генерации текста через OpenAI API"""
        # Настраиваем мок OpenAI клиента
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "OpenAI сгенерированный контент"
        mock_client.chat.completions.create.return_value = mock_response
        
        # Мокаем наличие клиента
        import flask_generator.text_gen as text_gen
        text_gen.openai_client = mock_client
        
        test_data = {'topic': 'Тест OpenAI'}
        result = text_gen.generate_text(test_data)
        
        assert result == "OpenAI сгенерированный контент"
        mock_client.chat.completions.create.assert_called_once()


class TestImageGeneration:
    """Тесты генерации изображений"""
    
    @patch.dict(os.environ, {}, clear=True)  # Убираем OPENAI_API_KEY
    def test_generate_image_prompt_mock_mode(self):
        """Тест генерации промпта в mock режиме"""
        import importlib
        import flask_generator.image_gen as image_gen
        importlib.reload(image_gen)
        
        result = image_gen.generate_image_prompt_from_text(
            "Тестовый текст поста",
            {'topic': 'Тестовая тема'}
        )
        
        assert isinstance(result, str)
        assert 'Тестовая тема' in result
        assert 'иллюстрация' in result
    
    @patch('flask_generator.image_gen.openai_client')
    def test_generate_image_dalle_mock_mode(self, mock_client):
        """Тест генерации изображения в mock режиме"""
        import flask_generator.image_gen as image_gen
        image_gen.openai_client = None  # Симулируем отсутствие клиента
        
        result = image_gen.generate_image_dalle("Тестовый промпт")
        
        assert isinstance(result, str)
        assert 'placeholder' in result or 'Mock' in result
    
    @patch('flask_generator.image_gen.openai_client')
    def test_generate_image_dalle_openai_mode(self, mock_client):
        """Тест генерации изображения через DALL-E"""
        # Настраиваем мок
        mock_response = MagicMock()
        mock_response.data[0].url = "https://example.com/generated_image.jpg"
        mock_client.images.generate.return_value = mock_response
        
        import flask_generator.image_gen as image_gen
        image_gen.openai_client = mock_client
        
        result = image_gen.generate_image_dalle("Красивая картинка")
        
        assert result == "https://example.com/generated_image.jpg"
        mock_client.images.generate.assert_called_once()
    
    @patch('flask_generator.image_gen.openai_client')
    def test_generate_image_dalle_fallback_to_dalle2(self, mock_client):
        """Тест fallback с DALL-E 3 на DALL-E 2"""
        # Настраиваем мок: DALL-E 3 падает, DALL-E 2 работает
        mock_client.images.generate.side_effect = [
            Exception("DALL-E 3 error"),  # Первый вызов падает
            MagicMock(data=[MagicMock(url="https://example.com/dalle2_image.jpg")])  # Второй работает
        ]
        
        import flask_generator.image_gen as image_gen
        image_gen.openai_client = mock_client
        
        result = image_gen.generate_image_dalle("Тест fallback")
        
        assert result == "https://example.com/dalle2_image.jpg"
        assert mock_client.images.generate.call_count == 2
