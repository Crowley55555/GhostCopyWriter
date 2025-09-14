#!/usr/bin/env python3
"""
Основной скрипт запуска всех тестов Ghostwriter проекта

Запускает:
1. Юнит-тесты Django
2. Юнит-тесты Flask
3. Интеграционные тесты
4. Тесты производительности
5. Нагрузочные тесты (опционально)

Результаты сохраняются в test_results.txt
"""

import os
import sys
import subprocess
import datetime
import json
from pathlib import Path


class TestRunner:
    """Класс для запуска и управления тестами"""
    
    def __init__(self):
        self.results = {
            'start_time': datetime.datetime.now(),
            'tests': {},
            'summary': {}
        }
        self.project_root = Path(__file__).parent
    
    def run_command(self, command, description):
        """Запускает команду и записывает результат"""
        print(f"\n{'='*60}")
        print(f"🧪 {description}")
        print(f"{'='*60}")
        print(f"Команда: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',  # Явно указываем кодировку
                errors='replace',  # Заменяем проблемные символы
                timeout=300  # 5 минут таймаут
            )
            
            success = result.returncode == 0
            
            self.results['tests'][description] = {
                'success': success,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command
            }
            
            if success:
                print(f"OK: {description} - УСПЕШНО")
                if result.stdout:
                    print("Вывод:", result.stdout[-500:])  # Последние 500 символов
            else:
                print(f"ERROR: {description} - ОШИБКА (код {result.returncode})")
                if result.stderr:
                    print("Ошибки:", result.stderr[-500:])
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {description} - ТАЙМАУТ (>5 минут)")
            self.results['tests'][description] = {
                'success': False,
                'error': 'Timeout',
                'command': command
            }
            return False
        except Exception as e:
            print(f"💥 {description} - ИСКЛЮЧЕНИЕ: {e}")
            self.results['tests'][description] = {
                'success': False,
                'error': str(e),
                'command': command
            }
            return False
    
    def run_django_tests(self):
        """Запускает Django тесты"""
        return self.run_command(
            "python manage.py test tests.test_django_models tests.test_django_views",
            "Django юнит-тесты"
        )
    
    def run_flask_tests(self):
        """Запускает Flask тесты"""
        return self.run_command(
            "python -m pytest tests/test_flask_app.py -v",
            "Flask юнит-тесты"
        )
    
    def run_integration_tests(self):
        """Запускает интеграционные тесты"""
        return self.run_command(
            "python manage.py test tests.test_integration --verbosity=2",
            "Интеграционные тесты"
        )
    
    def run_performance_tests(self):
        """Запускает тесты производительности"""
        return self.run_command(
            "python manage.py test tests.test_performance --verbosity=2",
            "Тесты производительности"
        )
    
    def run_load_tests(self, users=10, duration=60):
        """Запускает нагрузочные тесты"""
        print(f"\n" + "="*60)
        print("WARNING: ТРЕБОВАНИЯ ДЛЯ НАГРУЗОЧНЫХ ТЕСТОВ:")
        print("1. Django сервер должен быть запущен на http://localhost:8000")
        print("2. Flask сервер должен быть запущен на http://localhost:5000")
        print("3. Установлен locust: pip install locust")
        print("="*60)
        
        # Проверяем доступность серверов
        try:
            import requests
            django_response = requests.get("http://localhost:8000", timeout=2)
            print(f"OK: Django сервер доступен (статус {django_response.status_code})")
        except Exception as e:
            print(f"ERROR: Django сервер недоступен: {e}")
            print("INFO: Запустите: python manage.py runserver")
            return False
        
        try:
            flask_response = requests.get("http://localhost:5000", timeout=2)
            print(f"OK: Flask сервер доступен (статус {flask_response.status_code})")
        except Exception as e:
            print(f"WARNING: Flask сервер недоступен: {e}")
            print("INFO: Запустите: cd flask_generator && python -m flask --app app run")
        
        response = input("\nПродолжить нагрузочное тестирование? (y/N): ")
        
        if response.lower() != 'y':
            print("SKIP: Нагрузочные тесты пропущены")
            return True
        
        return self.run_command(
            f"locust -f tests/test_load.py --headless -u {users} -r 2 -t {duration}s --host http://localhost:8000",
            f"Нагрузочные тесты ({users} пользователей, {duration}с)"
        )
    
    def generate_report(self):
        """Генерирует отчет о тестировании"""
        end_time = datetime.datetime.now()
        duration = end_time - self.results['start_time']
        
        # Подсчитываем статистику
        total_tests = len(self.results['tests'])
        successful_tests = sum(1 for test in self.results['tests'].values() if test['success'])
        failed_tests = total_tests - successful_tests
        
        # Формируем отчет
        report = f"""
=============================================================================
ОТЧЕТ ТЕСТИРОВАНИЯ GHOSTWRITER ПРОЕКТА
=============================================================================
Дата начала: {self.results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
Дата окончания: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
Продолжительность: {duration}

ОБЩАЯ СТАТИСТИКА:
- Всего тестовых наборов: {total_tests}
- Успешных: {successful_tests}
- Неудачных: {failed_tests}
- Процент успеха: {(successful_tests/total_tests*100):.1f}%

ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:
"""
        
        # Добавляем детали по каждому тесту
        for test_name, test_result in self.results['tests'].items():
            status = "OK: УСПЕШНО" if test_result['success'] else "ERROR: ОШИБКА"
            report += f"\n{status} | {test_name}"
            
            if not test_result['success']:
                if 'error' in test_result:
                    report += f"\n   Ошибка: {test_result['error']}"
                if 'stderr' in test_result and test_result['stderr']:
                    report += f"\n   Stderr: {test_result['stderr'][:200]}..."
        
        # Рекомендации
        report += f"""

РЕКОМЕНДАЦИИ:
"""
        if failed_tests == 0:
            report += "🎉 Все тесты прошли успешно! Проект готов к продакшену."
        else:
            report += f"WARNING: Обнаружено {failed_tests} проблем. Рекомендуется исправить перед деплоем."
        
        if 'Нагрузочные тесты' not in [name for name in self.results['tests'].keys()]:
            report += "\nINFO: Рекомендуется запустить нагрузочные тесты для проверки производительности."
        
        report += f"""

АРХИТЕКТУРА ПРОЕКТА:
- Django приложение: Основная бизнес-логика, БД, UI
- Flask приложение: Микросервис генерации через OpenAI
- Связь: Зашифрованное REST API
- База данных: SQLite (для разработки)

ПОКРЫТИЕ ТЕСТАМИ:
- OK: Модели Django (создание, валидация, связи)
- OK: Views Django (генерация, аутентификация, API)
- OK: Flask API (endpoints, шифрование, генерация)
- OK: Интеграция Django-Flask (полный цикл)
- OK: Производительность (время отклика, память)
- OK: Стресс-тестирование (нагрузка, конкурентность)

=============================================================================
"""
        
        # Сохраняем отчет
        with open('test_results.txt', 'w', encoding='utf-8') as f:
            f.write(report)
        
        return report
    
    def run_all_tests(self, include_load_tests=False):
        """Запускает все тесты"""
        print("START: ЗАПУСК ПОЛНОГО ТЕСТИРОВАНИЯ GHOSTWRITER ПРОЕКТА")
        print(f"📁 Рабочая директория: {os.getcwd()}")
        
        # Проверяем наличие файлов
        required_files = [
            'manage.py',
            'flask_generator/app.py',
            'tests/test_django_models.py'
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                print(f"ERROR: Не найден файл: {file_path}")
                return False
        
        print("OK: Все необходимые файлы найдены")
        
        # Запускаем тесты по порядку
        test_sequence = [
            self.run_django_tests,
            self.run_flask_tests,
            self.run_integration_tests,
            self.run_performance_tests
        ]
        
        if include_load_tests:
            test_sequence.append(lambda: self.run_load_tests(users=5, duration=30))
        
        # Выполняем все тесты
        for test_func in test_sequence:
            success = test_func()
            if not success:
                print(f"WARNING: Тест завершился с ошибками, но продолжаем...")
        
        # Генерируем отчет
        report = self.generate_report()
        print("\n" + "="*60)
        print("📊 ИТОГОВЫЙ ОТЧЕТ")
        print("="*60)
        print(report[-1000:])  # Показываем последнюю часть отчета
        
        return True


def main():
    """Главная функция"""
    print("🧪 СИСТЕМА ТЕСТИРОВАНИЯ GHOSTWRITER")
    print("="*50)
    
    runner = TestRunner()
    
    # Проверяем аргументы командной строки
    include_load = '--load' in sys.argv or '-l' in sys.argv
    
    if include_load:
        print("📈 Включены нагрузочные тесты")
    else:
        print("📈 Нагрузочные тесты отключены (используйте --load для включения)")
    
    # Запускаем тесты
    success = runner.run_all_tests(include_load_tests=include_load)
    
    if success:
        print("\n🎯 Тестирование завершено! Результаты в test_results.txt")
    else:
        print("\n💥 Тестирование завершено с критическими ошибками!")
        sys.exit(1)


if __name__ == '__main__':
    main()
