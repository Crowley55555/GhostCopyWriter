#!/usr/bin/env python3
"""
Изолированные тесты Django без внешних API

Полностью изолированные от внешних зависимостей тесты
для проверки основной функциональности Django приложения
"""

import json
import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from generator.models import UserProfile, Generation, GenerationTemplate

# Переопределяем настройки для тестов
@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
            'OPTIONS': {'timeout': 20}
        }
    },
    MEDIA_ROOT=tempfile.mkdtemp(),
    USE_TZ=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
)
class IsolatedDjangoTests(TestCase):
    """Изолированные тесты Django функциональности"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_models_creation(self):
        """Тест создания всех моделей"""
        # Создаем профиль
        profile = UserProfile.objects.create(
            user=self.user,
            city='Москва',
            bio='Тестовый пользователь'
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.city, 'Москва')
        
        # Создаем генерацию
        generation = Generation.objects.create(
            user=self.user,
            topic='Тестовая тема',
            result='Тестовый результат'
        )
        self.assertEqual(generation.user, self.user)
        self.assertEqual(generation.topic, 'Тестовая тема')
        
        # Создаем шаблон
        template = GenerationTemplate.objects.create(
            user=self.user,
            name='Тестовый шаблон',
            settings={'voice_tone': ['Дружелюбный']}
        )
        self.assertEqual(template.user, self.user)
        self.assertEqual(template.name, 'Тестовый шаблон')
    
    def test_quick_login_functionality(self):
        """Тест функции быстрого входа"""
        # Тест создания админа
        response = self.client.post('/quick-login/admin/')
        self.assertRedirects(response, '/admin/')
        
        admin_user = User.objects.get(username='admin')
        self.assertTrue(admin_user.is_superuser)
        
        # Тест создания тестового пользователя
        response = self.client.post('/quick-login/test_user_1/')
        self.assertRedirects(response, '/profile/')
        
        test_user = User.objects.get(username='test_user_1')
        self.assertEqual(test_user.first_name, 'Анна')
    
    @patch('generator.views.generate_text')
    @patch('generator.views.generate_image_gigachat')
    def test_generator_completely_mocked(self, mock_image, mock_text):
        """Полностью изолированный тест генерации"""
        # Настраиваем моки
        mock_text.return_value = 'Мокированный текст поста'
        mock_image.return_value = 'data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='
        
        # Отправляем запрос
        response = self.client.post('/generator/', {
            'topic': 'Изолированная тема',
            'generator_type': 'gigachat',
            'voice_tone': ['Дружелюбный'],
            'post_length': 'Средний'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success', False))
        
        # Проверяем, что моки были вызваны
        mock_text.assert_called_once()
        
        # Проверяем сохранение в БД
        generation = Generation.objects.get(topic='Изолированная тема')
        self.assertEqual(generation.user, self.user)
    
    def test_template_management(self):
        """Тест управления шаблонами"""
        # Создание шаблона
        template_data = {
            'name': 'API шаблон',
            'settings': {'voice_tone': ['Профессиональный']},
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
        
        # Загрузка шаблона
        template = GenerationTemplate.objects.get(name='API шаблон')
        response = self.client.get(f'/api/load-template/?id={template.id}')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['settings']['voice_tone'], ['Профессиональный'])
    
    @patch('generator.views.generate_text')
    def test_regenerate_text_isolated(self, mock_generate):
        """Изолированный тест перегенерации текста"""
        # Создаем начальную генерацию
        generation = Generation.objects.create(
            user=self.user,
            topic='Тема для перегенерации',
            result='Исходный текст'
        )
        
        # Настраиваем мок
        mock_generate.return_value = 'Новый перегенерированный текст'
        
        # Устанавливаем ID в сессии
        session = self.client.session
        session['current_generation_id'] = generation.id
        session.save()
        
        # Отправляем запрос
        response = self.client.post('/regenerate-text/', {
            'topic': 'Тема для перегенерации'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Проверяем ответ
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['result'], 'Новый перегенерированный текст')
        
        # Проверяем обновление в БД
        generation.refresh_from_db()
        self.assertIn('--- Перегенерация 1 ---', generation.result)
        self.assertIn('Новый перегенерированный текст', generation.result)
    
    def test_user_wall(self):
        """Тест стены пользователя"""
        # Создаем несколько генераций
        for i in range(3):
            Generation.objects.create(
                user=self.user,
                topic=f'Тема {i}',
                result=f'Результат {i}'
            )
        
        # Проверяем отображение стены
        response = self.client.get('/wall/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тема 0')
        self.assertContains(response, 'Тема 1')
        self.assertContains(response, 'Тема 2')
    
    def test_profile_management(self):
        """Тест управления профилем"""
        # Создаем профиль
        profile = UserProfile.objects.create(user=self.user)
        
        # Тест просмотра профиля
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)
        
        # Тест редактирования профиля
        response = self.client.get('/profile/edit/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
    
    def test_form_validation(self):
        """Тест валидации форм"""
        # Тест с пустыми данными
        response = self.client.post('/generator/', {}, 
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Форма должна быть валидна, так как все поля необязательные
        self.assertEqual(response.status_code, 200)
    
    def test_generation_detail_view(self):
        """Тест детального просмотра генерации"""
        generation = Generation.objects.create(
            user=self.user,
            topic='Детальная тема',
            result='Детальный результат'
        )
        
        response = self.client.get(f'/generation/{generation.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Детальная тема')
        self.assertContains(response, 'Детальный результат')
    
    def test_generation_deletion(self):
        """Тест удаления генерации"""
        generation = Generation.objects.create(
            user=self.user,
            topic='Тема для удаления',
            result='Результат для удаления'
        )
        
        # POST запрос для удаления
        response = self.client.post(f'/delete-generation/{generation.id}/')
        self.assertRedirects(response, '/wall/')
        
        # Проверяем, что генерация удалена
        self.assertFalse(Generation.objects.filter(id=generation.id).exists())

    def test_authentication_required_views(self):
        """Тест представлений, требующих авторизации"""
        self.client.logout()
        
        # Эти представления должны требовать авторизации
        protected_urls = [
            '/profile/',
            '/profile/edit/',
            '/wall/',
            '/api/save-template/',
            '/api/get-templates/',
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            # Должен быть редирект на страницу входа или 403/401
            self.assertIn(response.status_code, [302, 401, 403])
