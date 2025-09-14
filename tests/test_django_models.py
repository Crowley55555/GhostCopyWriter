#!/usr/bin/env python3
"""
Юнит-тесты для Django моделей

Тестирует:
- Создание и валидацию моделей
- Связи между моделями
- Методы моделей
- Ограничения и валидацию данных
"""

import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from generator.models import UserProfile, Generation, GenerationTemplate


class UserProfileModelTest(TestCase):
    """Тесты модели UserProfile"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_user_profile(self):
        """Тест создания профиля пользователя"""
        profile = UserProfile.objects.create(
            user=self.user,
            city='Москва',
            bio='Тестовый пользователь',
            terms_accepted=True
        )
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.city, 'Москва')
        self.assertEqual(profile.bio, 'Тестовый пользователь')
        self.assertTrue(profile.terms_accepted)
        self.assertEqual(str(profile), 'Профиль: testuser')
    
    def test_user_profile_optional_fields(self):
        """Тест необязательных полей профиля"""
        profile = UserProfile.objects.create(user=self.user)
        
        self.assertEqual(profile.first_name, '')
        self.assertEqual(profile.last_name, '')
        self.assertEqual(profile.city, '')
        self.assertEqual(profile.phone, '')
        self.assertIsNone(profile.date_of_birth)
        self.assertEqual(profile.bio, '')
        self.assertFalse(profile.terms_accepted)


class GenerationModelTest(TestCase):
    """Тесты модели Generation"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_generation(self):
        """Тест создания генерации"""
        generation = Generation.objects.create(
            user=self.user,
            topic='Тестовая тема',
            result='Тестовый результат',
            image_url='http://example.com/image.jpg'
        )
        
        self.assertEqual(generation.user, self.user)
        self.assertEqual(generation.topic, 'Тестовая тема')
        self.assertEqual(generation.result, 'Тестовый результат')
        self.assertEqual(generation.image_url, 'http://example.com/image.jpg')
        self.assertIsNotNone(generation.created_at)
    
    def test_generation_multiple_images(self):
        """Тест множественных изображений в генерации"""
        generation = Generation.objects.create(
            user=self.user,
            topic='Тест',
            result='Результат',
            image_url='image1.jpg|image2.jpg|image3.jpg'
        )
        
        # Проверяем разделение изображений
        images = generation.image_url.split('|')
        self.assertEqual(len(images), 3)
        self.assertIn('image1.jpg', images)
        self.assertIn('image2.jpg', images)
        self.assertIn('image3.jpg', images)
    
    def test_generation_multiple_text_versions(self):
        """Тест множественных версий текста"""
        text_with_versions = """Первая версия

--- Перегенерация 1 ---

Вторая версия

--- Перегенерация 2 ---

Третья версия"""
        
        generation = Generation.objects.create(
            user=self.user,
            topic='Тест',
            result=text_with_versions
        )
        
        # Проверяем количество версий
        version_count = generation.result.count('--- Перегенерация') + 1
        self.assertEqual(version_count, 3)
    
    def test_generation_str_method(self):
        """Тест строкового представления генерации"""
        generation = Generation.objects.create(
            user=self.user,
            topic='Очень длинная тема для тестирования обрезки',
            result='Результат'
        )
        
        expected = 'testuser: Очень длинная тема для тестиро...'
        self.assertEqual(str(generation), expected)
    
    def test_generation_anonymous_user(self):
        """Тест генерации для анонимного пользователя"""
        generation = Generation.objects.create(
            user=None,
            topic='Анонимная тема',
            result='Анонимный результат'
        )
        
        self.assertIsNone(generation.user)
        self.assertEqual(str(generation), 'Аноним: Анонимная тема...')


class GenerationTemplateModelTest(TestCase):
    """Тесты модели GenerationTemplate"""
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_template(self):
        """Тест создания шаблона"""
        template = GenerationTemplate.objects.create(
            user=self.user,
            name='Тестовый шаблон',
            settings={'voice_tone': ['Дружелюбный'], 'post_length': 'Средний'},
            is_default=True
        )
        
        self.assertEqual(template.user, self.user)
        self.assertEqual(template.name, 'Тестовый шаблон')
        self.assertEqual(template.settings['voice_tone'], ['Дружелюбный'])
        self.assertTrue(template.is_default)
        self.assertIsNotNone(template.created_at)
        self.assertIsNotNone(template.updated_at)
    
    def test_template_unique_constraint(self):
        """Тест уникальности имени шаблона для пользователя"""
        GenerationTemplate.objects.create(
            user=self.user,
            name='Уникальный шаблон',
            settings={}
        )
        
        # Попытка создать шаблон с тем же именем должна вызвать ошибку
        with self.assertRaises(Exception):
            GenerationTemplate.objects.create(
                user=self.user,
                name='Уникальный шаблон',
                settings={}
            )
    
    def test_template_str_method(self):
        """Тест строкового представления шаблона"""
        template = GenerationTemplate.objects.create(
            user=self.user,
            name='Мой шаблон',
            settings={}
        )
        
        self.assertEqual(str(template), 'testuser: Мой шаблон')
