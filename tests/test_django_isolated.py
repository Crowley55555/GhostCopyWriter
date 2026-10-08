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
from django.contrib.messages import get_messages
from generator.models import UserProfile, Generation, GenerationTemplate
from tests.helpers import TokenAuthMixin

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
class IsolatedDjangoTests(TokenAuthMixin, TestCase):
    """Изолированные тесты Django функциональности"""
    
    def setUp(self):
        """Подготовка тестовых данных: вход по токену пользователя Telegram"""
        self.client = Client()
        self.token, self.user = self.login_by_token(telegram_user_id=100001)
    
    def test_models_creation(self):
        """Тест создания всех моделей"""
        # Создаем профиль
        profile = UserProfile.objects.create(
            user=self.user,
            terms_accepted=True
        )
        self.assertEqual(profile.user, self.user)
        self.assertTrue(profile.terms_accepted)
        
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
            'platform': 'VK',
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
        
        # Устанавливаем ID в сессии и данные последней генерации:
        # перегенерация берёт тему и площадку из last_form_data
        session = self.client.session
        session['current_generation_id'] = generation.id
        session['last_form_data'] = {'topic': 'Тема для перегенерации', 'platform': 'VK'}
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
        mock_generate.assert_called_once()
        self.assertEqual(mock_generate.call_args.args[0]['platform'], 'VK')
        self.assertEqual(mock_generate.call_args.args[0]['topic'], 'Тема для перегенерации')
        
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
        
        # Редактирование профиля отключено: возврат на профиль с пояснением
        response = self.client.get('/profile/edit/')
        self.assertRedirects(response, '/profile/')
        notices = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('Редактирование профиля недоступно' in m for m in notices))
    
    @patch('generator.views.generate_text')
    def test_form_validation(self, mock_text):
        """Тест валидации форм: тема и площадка обязательны"""
        mock_text.return_value = 'Мокированный текст поста'

        # Тест с пустыми данными: generator_view строит форму из
        # `request.POST or None`, пустой POST даёт несвязанную форму
        response = self.client.post('/generator/', {},
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Некорректно заполнена форма')

        # Без темы или без площадки форма не проходит
        for payload, missing in (({'platform': 'VK'}, 'topic'),
                                 ({'topic': 'Тема без площадки'}, 'platform'),
                                 ({'topic': 'Тема', 'platform': 'Instagram'}, 'platform')):
            with self.subTest(payload=payload):
                response = self.client.post('/generator/', payload,
                                          HTTP_X_REQUESTED_WITH='XMLHttpRequest')

                self.assertEqual(response.status_code, 400)
                data = json.loads(response.content)
                self.assertFalse(data['success'])
                self.assertEqual(data['error'], 'Некорректно заполнена форма')
                self.assertEqual(list(data['form_errors']), [missing])
        mock_text.assert_not_called()

        # Тема и площадка — достаточно: остальные поля необязательные
        response = self.client.post('/generator/', {'topic': 'Тема без критериев', 'platform': 'VK'},
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'], data)
        mock_text.assert_called_once()
    
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
