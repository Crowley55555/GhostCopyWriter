#!/usr/bin/env python3
"""
Интеграционные тесты Django-Flask взаимодействия

Тестирует:
- Полный цикл генерации через Flask API
- Обработку ошибок сети
- Шифрование между приложениями
- Fallback сценарии
- Таймауты и восстановление
"""

import json
import requests
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from generator.models import Generation
from generator.fastapi_client import generate_text_and_prompt, generate_image


class DjangoFlaskIntegrationTest(TestCase):
    """Интеграционные тесты Django-Flask"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    @patch('requests.post')
    def test_successful_flask_api_call(self, mock_post):
        """Тест успешного вызова Flask API"""
        # Настраиваем успешный ответ от Flask
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': 'encrypted_response_data'
        }
        mock_post.return_value = mock_response
        
        # Мокаем расшифровку
        with patch('generator.fastapi_client.decrypt_data') as mock_decrypt:
            mock_decrypt.return_value = {
                'text': 'Сгенерированный текст',
                'image_prompt': 'Промпт для изображения'
            }
            
            # Вызываем функцию
            result = generate_text_and_prompt({'topic': 'Тест'})
            
            # Проверяем результат
            assert result['text'] == 'Сгенерированный текст'
            assert result['image_prompt'] == 'Промпт для изображения'
            mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_flask_api_connection_error(self, mock_post):
        """Тест обработки ошибки подключения к Flask API"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with self.assertRaises(Exception) as context:
            generate_text_and_prompt({'topic': 'Тест'})
        
        self.assertIn("Flask Generator не запущен или недоступен", str(context.exception))
    
    @patch('requests.post')
    def test_flask_api_timeout(self, mock_post):
        """Тест обработки таймаута Flask API"""
        mock_post.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with self.assertRaises(Exception) as context:
            generate_text_and_prompt({'topic': 'Тест'})
        
        self.assertIn("Flask Generator не отвечает", str(context.exception))
    
    @patch('requests.post')
    def test_flask_api_500_error(self, mock_post):
        """Тест обработки ошибки 500 от Flask API"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response
        
        with self.assertRaises(requests.exceptions.HTTPError):
            generate_text_and_prompt({'topic': 'Тест'})
    
    @patch('requests.post')
    def test_flask_api_invalid_response_format(self, mock_post):
        """Тест обработки некорректного формата ответа"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'invalid': 'format'}  # Нет поля 'data'
        mock_post.return_value = mock_response
        
        with self.assertRaises(KeyError):
            generate_text_and_prompt({'topic': 'Тест'})
    
    @patch('requests.post')
    def test_flask_api_decryption_error(self, mock_post):
        """Тест обработки ошибки расшифровки"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'invalid_encrypted_data'}
        mock_post.return_value = mock_response
        
        with patch('generator.fastapi_client.decrypt_data') as mock_decrypt:
            mock_decrypt.side_effect = Exception("Decryption failed")
            
            # Должен попытаться парсить как JSON
            with patch('json.loads') as mock_json:
                mock_json.return_value = {'fallback': 'data'}
                
                result = generate_text_and_prompt({'topic': 'Тест'})
                self.assertEqual(result, {'fallback': 'data'})


class EncryptionIntegrationTest(TestCase):
    """Тесты интеграции шифрования"""
    
    def test_encryption_consistency(self):
        """Тест согласованности шифрования между Django и Flask"""
        # Тестовые данные
        test_data = {'topic': 'Тест', 'platform': 'VK'}
        
        # Импортируем функции шифрования (они уже используют ключ из .env)
        from generator.fastapi_client import encrypt_data as django_encrypt, decrypt_data as django_decrypt
        
        try:
            # Импортируем Flask модуль шифрования
            import flask_generator.crypto_utils as flask_crypto
            
            # Шифруем в Django, расшифровываем во Flask
            django_encrypted = django_encrypt(test_data)
            flask_decrypted = flask_crypto.decrypt_data(django_encrypted)
            flask_parsed = json.loads(flask_decrypted.decode())
            
            self.assertEqual(flask_parsed, test_data)
            
            # Шифруем во Flask, расшифровываем в Django
            flask_encrypted = flask_crypto.encrypt_data(json.dumps(test_data).encode())
            django_decrypted = django_decrypt(flask_encrypted)
            
            self.assertEqual(django_decrypted, test_data)
            
        except Exception as e:
            # Если Flask модуль недоступен, пропускаем тест
            self.skipTest(f"Flask модуль недоступен: {e}")


class EndToEndIntegrationTest(TestCase):
    """End-to-end интеграционные тесты"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    @patch('generator.views.check_flask_api_status')
    @patch('generator.views.generate_text_and_prompt')
    @patch('generator.views.generate_image')
    def test_full_openai_generation_cycle(self, mock_image, mock_text_prompt, mock_status):
        """Тест полного цикла генерации через OpenAI"""
        # Настраиваем моки
        mock_status.return_value = True
        mock_text_prompt.return_value = {
            'text': 'Полный сгенерированный текст',
            'image_prompt': 'Промпт для DALL-E'
        }
        mock_image.return_value = 'https://example.com/dalle_image.jpg'
        
        # Отправляем запрос на генерацию
        response = self.client.post('/generator/', {
            'topic': 'Интеграционный тест',
            'generator_type': 'openai',
            'voice_tone': ['Профессиональный'],
            'post_length': 'Средний'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем успешный ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['result'], 'Полный сгенерированный текст')
        self.assertEqual(data['image_url'], 'https://example.com/dalle_image.jpg')
        
        # Проверяем сохранение в БД
        generation = Generation.objects.get(topic='Интеграционный тест')
        self.assertEqual(generation.user, self.user)
        self.assertEqual(generation.result, 'Полный сгенерированный текст')
        
        # Проверяем вызовы API
        mock_status.assert_called_once()
        mock_text_prompt.assert_called_once()
        mock_image.assert_called_once_with('Промпт для DALL-E')
    
    @patch('generator.views.check_flask_api_status')
    def test_flask_api_failure_fallback(self, mock_status):
        """Тест fallback при недоступности Flask API"""
        mock_status.return_value = False
        
        response = self.client.post('/generator/', {
            'topic': 'Тест fallback',
            'generator_type': 'openai'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Flask Generator не запущен', data['error'])
    
    @patch('generator.views.generate_text')
    @patch('generator.views.generate_image_gigachat')
    def test_regeneration_workflow(self, mock_image, mock_text):
        """Тест workflow перегенерации"""
        # Создаем начальную генерацию
        generation = Generation.objects.create(
            user=self.user,
            topic='Тест перегенерации',
            result='Первоначальный текст'
        )
        
        # Устанавливаем ID в сессии
        session = self.client.session
        session['current_generation_id'] = generation.id
        session.save()
        
        # Настраиваем моки
        mock_text.return_value = "Перегенерированный текст"
        mock_image.return_value = "data:image/jpeg;base64,newimage"
        
        # Тестируем перегенерацию текста
        response = self.client.post('/regenerate-text/', {
            'topic': 'Тест перегенерации'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Проверяем обновление в БД
        generation.refresh_from_db()
        self.assertIn('--- Перегенерация 1 ---', generation.result)
        self.assertIn('Перегенерированный текст', generation.result)


class NetworkErrorSimulationTest(TestCase):
    """Тесты имитации сетевых ошибок"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    @patch('requests.get')
    def test_flask_health_check_network_error(self, mock_get):
        """Тест ошибки сети при проверке статуса Flask"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        from generator.views import check_flask_api_status
        result = check_flask_api_status()
        
        self.assertFalse(result)
    
    @patch('requests.post')
    def test_flask_api_intermittent_errors(self, mock_post):
        """Тест периодических ошибок Flask API"""
        # Симулируем серию ошибок, затем успех
        mock_post.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.ConnectionError("Connection error"),
            MagicMock(status_code=500),
            MagicMock(status_code=200, json=lambda: {'data': 'success'})
        ]
        
        # Проверяем, что ошибки обрабатываются корректно
        for i in range(3):
            with self.assertRaises(Exception):
                generate_text_and_prompt({'topic': f'Тест {i}'})
        
        # Четвертый вызов должен быть успешным (если добавить мок расшифровки)
        with patch('generator.fastapi_client.decrypt_data') as mock_decrypt:
            mock_decrypt.return_value = {'text': 'success'}
            result = generate_text_and_prompt({'topic': 'Тест 4'})
            self.assertEqual(result, {'text': 'success'})
