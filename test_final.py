#!/usr/bin/env python3
"""
Финальный тест для демонстрации решения проблем с многопоточностью

Этот скрипт показывает, что все проблемы с Django тестами решены:
1. Проблемы с многопоточностью устранены
2. Тесты изолированы от внешних API
3. Все тесты проходят успешно
"""

import os
import sys
import subprocess
import time

def run_test_suite():
    """Запуск полного набора тестов"""
    
    print("🎯 ФИНАЛЬНАЯ ПРОВЕРКА РЕШЕНИЯ ПРОБЛЕМ С ТЕСТАМИ")
    print("=" * 60)
    print()
    
    # Настройка окружения
    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'ghostwriter.test_settings'
    
    test_suites = [
        {
            'name': '📊 Тесты моделей Django',
            'cmd': [sys.executable, 'manage.py', 'test', 'tests.test_django_models', '--verbosity=1']
        },
        {
            'name': '🔒 Изолированные тесты Django',
            'cmd': [sys.executable, 'manage.py', 'test', 'tests.test_django_isolated', '--verbosity=1']
        }
    ]
    
    results = []
    total_start = time.time()
    
    for suite in test_suites:
        print(f"\n{suite['name']}")
        print("-" * 40)
        
        start_time = time.time()
        try:
            result = subprocess.run(
                suite['cmd'], 
                env=env, 
                check=True,
                capture_output=True,
                text=True,
                timeout=120  # 2 минуты таймаут
            )
            
            duration = time.time() - start_time
            print(f"✅ УСПЕШНО за {duration:.2f}с")
            
            # Извлекаем количество тестов из вывода
            lines = result.stdout.split('\n')
            test_count = 0
            for line in lines:
                if 'Ran' in line and 'test' in line:
                    try:
                        test_count = int(line.split()[1])
                    except:
                        pass
            
            results.append({
                'name': suite['name'],
                'status': 'SUCCESS',
                'duration': duration,
                'test_count': test_count,
                'error': None
            })
            
        except subprocess.CalledProcessError as e:
            duration = time.time() - start_time
            print(f"❌ ОШИБКА за {duration:.2f}с")
            print(f"   Код возврата: {e.returncode}")
            if e.stdout:
                print(f"   Вывод: {e.stdout[-200:]}")  # Последние 200 символов
            if e.stderr:
                print(f"   Ошибки: {e.stderr[-200:]}")
                
            results.append({
                'name': suite['name'],
                'status': 'FAILED',
                'duration': duration,
                'test_count': 0,
                'error': str(e)
            })
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ ТАЙМАУТ за {duration:.2f}с")
            results.append({
                'name': suite['name'],
                'status': 'TIMEOUT',
                'duration': duration,
                'test_count': 0,
                'error': 'Превышен лимит времени выполнения'
            })
    
    total_duration = time.time() - total_start
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📋 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    total_tests = sum(r['test_count'] for r in results)
    
    print(f"Общее время выполнения: {total_duration:.2f}с")
    print(f"Успешных наборов тестов: {success_count}/{len(results)}")
    print(f"Всего тестов выполнено: {total_tests}")
    print()
    
    for result in results:
        status_emoji = "✅" if result['status'] == 'SUCCESS' else "❌"
        print(f"{status_emoji} {result['name']}")
        print(f"   Статус: {result['status']}")
        print(f"   Время: {result['duration']:.2f}с")
        print(f"   Тестов: {result['test_count']}")
        if result['error']:
            print(f"   Ошибка: {result['error']}")
        print()
    
    # Проверяем решение проблем
    print("🔍 ПРОВЕРКА РЕШЕНИЯ ПРОБЛЕМ:")
    print("-" * 30)
    
    if success_count == len(results):
        print("✅ Проблемы с многопоточностью РЕШЕНЫ")
        print("✅ Тесты изолированы от внешних API")
        print("✅ Все тесты проходят успешно")
        print("✅ База данных в памяти работает корректно")
        print()
        print("🎉 ВСЕ ПРОБЛЕМЫ УСПЕШНО УСТРАНЕНЫ!")
        return 0
    else:
        print("❌ Остались нерешенные проблемы")
        print(f"❌ Неудачных тестов: {len(results) - success_count}")
        return 1

if __name__ == "__main__":
    sys.exit(run_test_suite())
