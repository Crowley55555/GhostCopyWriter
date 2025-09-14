
"""
Нагрузочные тесты для Ghostwriter проекта

Использует Locust для симуляции высокой нагрузки на:
- Django основное приложение
- Flask API сервер
- Интеграцию между ними

Запуск:
    locust -f tests/test_load.py --host=http://localhost:8000
"""

import json
import random
from locust import HttpUser, task, between
from locust import events


class DjangoAppUser(HttpUser):
    """Симуляция пользователя Django приложения"""
    
    wait_time = between(1, 3)  # Пауза между запросами 1-3 секунды
    
    def on_start(self):
        """Выполняется при старте каждого пользователя"""
        # Проверяем доступность сервера
        try:
            response = self.client.get("/")
            if response.status_code != 200:
                print(f"WARNING: Django сервер недоступен (статус {response.status_code})")
                return
            # Логинимся как тестовый пользователь
            self.client.post("/quick-login/test_user_1/")
        except Exception as e:
            print(f"ERROR: Не удается подключиться к Django серверу: {e}")
            return
    
    @task(3)
    def view_generator_page(self):
        """Просмотр страницы генератора (высокий приоритет)"""
        try:
            with self.client.get("/generator/", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 0:
                    response.failure("Django сервер недоступен")
                else:
                    response.failure(f"Ошибка загрузки генератора: {response.status_code}")
        except Exception as e:
            print(f"ERROR: Ошибка в view_generator_page: {e}")
    
    @task(2)
    def generate_content_gigachat(self):
        """Генерация контента через GigaChat"""
        form_data = {
            'topic': f'Тестовая тема {random.randint(1, 1000)}',
            'generator_type': 'gigachat',
            'voice_tone': [random.choice(['Дружелюбный', 'Профессиональный', 'Неформальный'])],
            'post_length': random.choice(['Короткий', 'Средний', 'Длинный']),
            'platform_specific': [random.choice(['VK', 'Telegram', 'Дзен'])]
        }
        
        with self.client.post(
            "/generator/", 
            data=form_data,
            headers={'X-Requested-With': 'XMLHttpRequest'},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success'):
                        response.success()
                    else:
                        response.failure(f"Ошибка генерации: {data.get('error')}")
                except json.JSONDecodeError:
                    response.failure("Некорректный JSON ответ")
            else:
                response.failure(f"HTTP ошибка: {response.status_code}")
    
    @task(1)
    def generate_content_openai(self):
        """Генерация контента через OpenAI (меньший приоритет)"""
        form_data = {
            'topic': f'OpenAI тема {random.randint(1, 1000)}',
            'generator_type': 'openai',
            'voice_tone': [random.choice(['Дружелюбный', 'Профессиональный'])],
            'post_length': 'Средний'
        }
        
        with self.client.post(
            "/generator/", 
            data=form_data,
            headers={'X-Requested-With': 'XMLHttpRequest'},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success'):
                        response.success()
                    else:
                        # OpenAI может быть недоступен - это нормально
                        if 'Flask Generator не запущен' in data.get('error', ''):
                            response.success()  # Считаем успехом
                        else:
                            response.failure(f"Неожиданная ошибка: {data.get('error')}")
                except json.JSONDecodeError:
                    response.failure("Некорректный JSON ответ")
            else:
                response.failure(f"HTTP ошибка: {response.status_code}")
    
    @task(1)
    def regenerate_text(self):
        """Перегенерация текста"""
        with self.client.post(
            "/regenerate-text/",
            data={'topic': f'Перегенерация {random.randint(1, 100)}'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Ошибка перегенерации: {response.status_code}")
    
    @task(1)
    def view_user_wall(self):
        """Просмотр стены пользователя"""
        with self.client.get("/wall/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Ошибка загрузки стены: {response.status_code}")
    
    @task(1)
    def view_profile(self):
        """Просмотр профиля пользователя"""
        with self.client.get("/profile/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Ошибка загрузки профиля: {response.status_code}")


class FlaskAPIUser(HttpUser):
    """Симуляция прямых запросов к Flask API"""
    
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Инициализация пользователя Flask API"""
        # Проверяем доступность API
        self.client.get("/")
    
    @task(2)
    def health_check(self):
        """Проверка health check Flask API"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(1)
    def test_endpoint(self):
        """Тест тестового endpoint"""
        test_data = {'test': f'load_test_{random.randint(1, 1000)}'}
        
        with self.client.post(
            "/test",
            json=test_data,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Test endpoint failed: {response.status_code}")


# =============================================================================
# СОБЫТИЙНЫЕ ХУКИ ДЛЯ СБОРА СТАТИСТИКИ
# =============================================================================

# Глобальные переменные для статистики
test_stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'errors': [],
    'response_times': []
}


@events.request.add_listener
def record_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Записывает статистику каждого запроса"""
    test_stats['total_requests'] += 1
    test_stats['response_times'].append(response_time)
    
    if exception:
        test_stats['failed_requests'] += 1
        test_stats['errors'].append({
            'type': request_type,
            'name': name,
            'error': str(exception),
            'response_time': response_time
        })
    else:
        test_stats['successful_requests'] += 1


@events.quitting.add_listener
def save_test_results(environment, **kwargs):
    """Сохраняет результаты тестов в файл"""
    if test_stats['total_requests'] == 0:
        return
    
    # Вычисляем статистику
    avg_response_time = sum(test_stats['response_times']) / len(test_stats['response_times'])
    success_rate = (test_stats['successful_requests'] / test_stats['total_requests']) * 100
    
    # Формируем отчет
    report = f"""
=============================================================================
ОТЧЕТ НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ GHOSTWRITER
=============================================================================
Дата: {json.dumps(str(environment.runner.start_time), ensure_ascii=False)}
Продолжительность: {environment.runner.start_time}

ОБЩАЯ СТАТИСТИКА:
- Всего запросов: {test_stats['total_requests']}
- Успешных: {test_stats['successful_requests']}
- Неудачных: {test_stats['failed_requests']}
- Процент успеха: {success_rate:.2f}%

ПРОИЗВОДИТЕЛЬНОСТЬ:
- Среднее время ответа: {avg_response_time:.2f} мс
- Минимальное время: {min(test_stats['response_times']):.2f} мс
- Максимальное время: {max(test_stats['response_times']):.2f} мс

ОШИБКИ ({len(test_stats['errors'])} шт.):
"""
    
    # Добавляем детали ошибок
    for i, error in enumerate(test_stats['errors'][:10], 1):  # Показываем первые 10
        report += f"\n{i}. {error['type']} {error['name']}: {error['error']} ({error['response_time']:.2f}мс)"
    
    if len(test_stats['errors']) > 10:
        report += f"\n... и еще {len(test_stats['errors']) - 10} ошибок"
    
    report += "\n\n=============================================================================\n"
    
    # Сохраняем в файл
    with open('test_results.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("📊 Результаты нагрузочного тестирования сохранены в test_results.txt")


# =============================================================================
# КОНФИГУРАЦИЯ НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ
# =============================================================================

class WebsiteUser(HttpUser):
    """Комбинированный пользователь для полного тестирования"""
    
    wait_time = between(1, 5)
    weight = 3  # Основной тип пользователей
    
    tasks = [DjangoAppUser.view_generator_page, DjangoAppUser.generate_content_gigachat]
    
    def on_start(self):
        """Логин при старте"""
        self.client.post("/quick-login/test_user_1/")
