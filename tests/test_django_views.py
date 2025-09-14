#!/usr/bin/env python3
"""
Юнит-тесты для Django views

Тестирует:
- Функции генерации контента
- Аутентификацию и авторизацию
- AJAX обработку
- Сохранение результатов
- Обработку ошибок
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from generator.models import UserProfile, Generation, GenerationTemplate
from generator.views import quick_login, generator_view, regenerate_text, regenerate_image


class QuickLoginViewTest(TestCase):
    """Тесты функции быстрого входа"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.factory = RequestFactory()
        self.client = Client()
    
    def test_quick_login_admin_creation(self):
        """Тест создания админа через quick_login"""
        response = self.client.post('/quick-login/admin/')
        
        # Проверяем, что админ был создан
        admin_user = User.objects.get(username='admin')
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.first_name, 'Администратор')
        
        # Проверяем редирект в админку
        self.assertRedirects(response, '/admin/')
    
    def test_quick_login_test_user_creation(self):
        """Тест создания тестового пользователя"""
        response = self.client.post('/quick-login/test_user_1/')
        
        # Проверяем, что пользователь был создан
        test_user = User.objects.get(username='test_user_1')
        self.assertEqual(test_user.first_name, 'Анна')
        self.assertEqual(test_user.last_name, 'Петрова')
        
        # Проверяем, что профиль был создан
        profile = UserProfile.objects.get(user=test_user)
        self.assertEqual(profile.city, 'Москва')
        self.assertIn('контент-маркетинг', profile.bio)
        
        # Проверяем редирект в профиль
        self.assertRedirects(response, '/profile/')
    
    def test_quick_login_invalid_user(self):
        """Тест попытки входа с недопустимым пользователем"""
        response = self.client.post('/quick-login/invalid_user/')
        
        # Проверяем редирект на страницу входа
        self.assertRedirects(response, '/login/')
        
        # Проверяем, что пользователь не был создан
        self.assertFalse(User.objects.filter(username='invalid_user').exists())
    
    def test_quick_login_get_method(self):
        """Тест GET запроса к quick_login"""
        response = self.client.get('/quick-login/admin/')
        
        # Должен редиректить на страницу входа
        self.assertRedirects(response, '/login/')


class GeneratorViewTest(TestCase):
    """Тесты основной функции генерации"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.factory = RequestFactory()
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_generator_view_get(self):
        """Тест GET запроса к генератору"""
        response = self.client.get('/generator/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Генератор постов')
        self.assertIn('form', response.context)
    
    def test_generator_gigachat_generation(self):
        """Тест генерации через GigaChat"""
        # Отправляем POST запрос
        response = self.client.post('/generator/', {
            'topic': 'Тестовая тема',
            'generator_type': 'gigachat',
            'voice_tone': ['Дружелюбный'],
            'post_length': 'Средний'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Если есть ошибка, выводим её для отладки
        if not data.get('success'):
            print(f"Ошибка в тесте: {data}")
        
        self.assertTrue(data.get('success', False))
        self.assertIsNotNone(data.get('result'))
        self.assertGreater(len(data.get('result', '')), 10)  # Проверяем, что результат не пустой
        
        # Проверяем, что генерация сохранена в БД
        generation = Generation.objects.get(topic='Тестовая тема')
        self.assertEqual(generation.user, self.user)
        self.assertIsNotNone(generation.result)
    
    @patch('generator.views.check_flask_api_status')
    @patch('generator.views.generate_text_and_prompt')
    def test_generator_openai_generation(self, mock_generate, mock_status):
        """Тест генерации через OpenAI Flask API"""
        # Настраиваем моки
        mock_status.return_value = True
        mock_generate.return_value = {
            'text': 'OpenAI сгенерированный текст',
            'image_prompt': 'Промпт для изображения'
        }
        
        # Отправляем POST запрос
        response = self.client.post('/generator/', {
            'topic': 'OpenAI тема',
            'generator_type': 'openai'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['result'], 'OpenAI сгенерированный текст')
    
    @patch('generator.views.check_flask_api_status')
    def test_generator_flask_api_unavailable(self, mock_status):
        """Тест обработки недоступности Flask API"""
        mock_status.return_value = False
        
        response = self.client.post('/generator/', {
            'topic': 'Тест',
            'generator_type': 'openai'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ошибку
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Flask Generator не запущен', data['error'])
    
    def test_generator_invalid_form(self):
        """Тест обработки невалидной формы"""
        response = self.client.post('/generator/', {
            # Пустая тема - должна вызвать ошибку валидации
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('form_errors', data)


class RegenerationViewsTest(TestCase):
    """Тесты функций перегенерации"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Создаем начальную генерацию
        self.generation = Generation.objects.create(
            user=self.user,
            topic='Тестовая тема',
            result='Первоначальный текст'
        )
    
    def test_regenerate_text(self):
        """Тест перегенерации текста"""
        # Устанавливаем ID генерации в сессии
        session = self.client.session
        session['current_generation_id'] = self.generation.id
        session.save()
        
        # Отправляем запрос на перегенерацию
        response = self.client.post('/regenerate-text/', {
            'topic': 'Тестовая тема'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Проверяем, что текст обновлен в БД
        self.generation.refresh_from_db()
        self.assertIn('--- Перегенерация 1 ---', self.generation.result)
        self.assertGreater(len(self.generation.result), len('Первоначальный текст'))
    
    @patch('generator.gigachat_api.generate_image_gigachat')
    def test_regenerate_image(self, mock_generate):
        """Тест перегенерации изображения"""
        mock_generate.return_value = "data:image/jpeg;base64,newimagedata"
        
        # Устанавливаем ID генерации в сессии
        session = self.client.session
        session['current_generation_id'] = self.generation.id
        session.save()
        
        # Отправляем запрос на перегенерацию
        response = self.client.post('/regenerate-image/', {
            'topic': 'Тестовая тема'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Проверяем, что изображение обновлено в БД
        self.generation.refresh_from_db()
        self.assertIsNotNone(self.generation.image_url)


class TemplateViewsTest(TestCase):
    """Тесты работы с шаблонами"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_save_template(self):
        """Тест сохранения шаблона"""
        template_data = {
            'name': 'Мой шаблон',
            'settings': {'voice_tone': ['Дружелюбный']},
            'is_default': True
        }
        
        response = self.client.post(
            '/api/save-template/',
            data=json.dumps(template_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Проверяем, что шаблон сохранен
        template = GenerationTemplate.objects.get(name='Мой шаблон')
        self.assertEqual(template.user, self.user)
        self.assertTrue(template.is_default)
    
    def test_load_template(self):
        """Тест загрузки шаблона"""
        template = GenerationTemplate.objects.create(
            user=self.user,
            name='Тестовый шаблон',
            settings={'voice_tone': ['Профессиональный']}
        )
        
        response = self.client.get(f'/api/load-template/?id={template.id}')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['settings']['voice_tone'], ['Профессиональный'])
