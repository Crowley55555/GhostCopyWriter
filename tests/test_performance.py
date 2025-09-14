#!/usr/bin/env python3
"""
Стресс-тесты и бенчмарки для Ghostwriter проекта

Тестирует:
- Производительность генерации контента
- Время отклика API
- Использование памяти
- Обработку одновременных запросов
- Деградацию производительности под нагрузкой
"""

import time
import threading
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth.models import User
from generator.models import Generation


class PerformanceTestCase(TestCase):
    """Базовый класс для тестов производительности"""
    
    def setUp(self):
        """Подготовка для тестов производительности"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='perfuser',
            email='perf@example.com',
            password='perfpass123'
        )
        self.client.login(username='perfuser', password='perfpass123')
    
    def measure_time(self, func, *args, **kwargs):
        """Измеряет время выполнения функции"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, (end_time - start_time) * 1000  # в миллисекундах


class DatabasePerformanceTest(PerformanceTestCase):
    """Тесты производительности базы данных"""
    
    def test_bulk_generation_creation(self):
        """Тест массового создания генераций"""
        start_time = time.time()
        
        # Создаем 100 генераций
        generations = []
        for i in range(100):
            generations.append(Generation(
                user=self.user,
                topic=f'Тест производительности {i}',
                result=f'Результат {i}' * 10,  # Длинный текст
                image_url=f'http://example.com/image{i}.jpg'
            ))
        
        Generation.objects.bulk_create(generations)
        
        creation_time = (time.time() - start_time) * 1000
        
        # Проверяем, что создание заняло разумное время
        self.assertLess(creation_time, 5000)  # Менее 5 секунд
        self.assertEqual(Generation.objects.filter(user=self.user).count(), 100)
    
    def test_generation_query_performance(self):
        """Тест производительности запросов к генерациям"""
        # Создаем тестовые данные
        for i in range(50):
            Generation.objects.create(
                user=self.user,
                topic=f'Тема {i}',
                result=f'Результат {i}' * 20
            )
        
        # Тестируем различные запросы
        start_time = time.time()
        
        # Запрос всех генераций пользователя
        generations = list(Generation.objects.filter(user=self.user).order_by('-created_at'))
        
        query_time = (time.time() - start_time) * 1000
        
        self.assertEqual(len(generations), 50)
        self.assertLess(query_time, 1000)  # Менее 1 секунды


class APIPerformanceTest(PerformanceTestCase):
    """Тесты производительности API"""
    
    @patch('generator.views.generate_text')
    def test_generation_response_time(self, mock_generate):
        """Тест времени отклика генерации"""
        mock_generate.return_value = "Быстрый ответ"
        
        response, response_time = self.measure_time(
            self.client.post,
            '/generator/',
            {
                'topic': 'Тест производительности',
                'generator_type': 'gigachat'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 2000)  # Менее 2 секунд
    
    def test_concurrent_requests(self):
        """Тест одновременных запросов"""
        def make_request(request_id):
            """Функция для одного запроса"""
            start_time = time.time()
            response = self.client.get('/generator/')
            end_time = time.time()
            return {
                'id': request_id,
                'status_code': response.status_code,
                'response_time': (end_time - start_time) * 1000
            }
        
        # Запускаем 20 одновременных запросов
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request, i) for i in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        # Анализируем результаты
        successful_requests = [r for r in results if r['status_code'] == 200]
        avg_response_time = sum(r['response_time'] for r in results) / len(results)
        
        self.assertGreaterEqual(len(successful_requests), 18)  # Минимум 90% успешных запросов
        self.assertLess(avg_response_time, 5000)  # Среднее время менее 5 секунд


class MemoryUsageTest(TestCase):
    """Тесты использования памяти"""
    
    def test_memory_usage_during_generation(self):
        """Тест использования памяти при генерации"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        client = Client()
        user = User.objects.create_user(
            username='memuser',
            email='mem@example.com',
            password='mempass123'
        )
        client.login(username='memuser', password='mempass123')
        
        # Выполняем множественные генерации
        with patch('generator.views.generate_text') as mock_generate:
            mock_generate.return_value = "Тест памяти" * 100  # Длинный текст
            
            for i in range(20):
                client.post('/generator/', {
                    'topic': f'Тест памяти {i}',
                    'generator_type': 'gigachat'
                }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Проверяем, что утечка памяти не критическая
        self.assertLess(memory_increase, 100)  # Менее 100 MB увеличения
        
        print(f"INFO: Использование памяти: {initial_memory:.2f} MB -> {final_memory:.2f} MB (+{memory_increase:.2f} MB)")


class StressTest(PerformanceTestCase):
    """Стресс-тесты системы"""
    
    def test_rapid_fire_requests(self):
        """Тест быстрых последовательных запросов"""
        results = []
        
        with patch('generator.views.generate_text') as mock_generate:
            mock_generate.return_value = "Стресс тест"
            
            # Отправляем 50 запросов подряд без пауз
            for i in range(50):
                start_time = time.time()
                response = self.client.post('/generator/', {
                    'topic': f'Стресс {i}',
                    'generator_type': 'gigachat'
                }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                end_time = time.time()
                
                results.append({
                    'status': response.status_code,
                    'time': (end_time - start_time) * 1000
                })
        
        # Анализируем результаты
        successful = [r for r in results if r['status'] == 200]
        avg_time = sum(r['time'] for r in results) / len(results)
        
        self.assertGreaterEqual(len(successful), 45)  # Минимум 90% успешных
        self.assertLess(avg_time, 1000)  # Среднее время менее 1 секунды
        
        print(f"INFO: Стресс тест: {len(successful)}/50 успешных, среднее время: {avg_time:.2f}мс")
    
    def test_database_stress(self):
        """Стресс-тест базы данных"""
        # Создаем много данных одновременно
        def create_generations(start_id, count):
            """Создает генерации в отдельном потоке"""
            for i in range(count):
                Generation.objects.create(
                    user=self.user,
                    topic=f'Стресс БД {start_id}-{i}',
                    result='Стресс тест' * 50
                )
        
        # Запускаем 5 потоков по 20 генераций
        threads = []
        start_time = time.time()
        
        for thread_id in range(5):
            thread = threading.Thread(
                target=create_generations,
                args=(thread_id, 20)
            )
            threads.append(thread)
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000
        
        # Проверяем результаты
        total_generations = Generation.objects.filter(user=self.user).count()
        self.assertEqual(total_generations, 100)
        self.assertLess(total_time, 10000)  # Менее 10 секунд
        
        print(f"INFO: Стресс БД: создано {total_generations} записей за {total_time:.2f}мс")
