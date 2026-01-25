#!/usr/bin/env python3
"""
Ручной генератор токенов для Ghostwriter

Запуск из PyCharm или терминала:
    python manual_token_generator.py

Возможности:
- Генерация всех типов токенов (публичные и скрытые)
- Настраиваемый срок действия и лимиты
- Массовая генерация токенов
- Список активных токенов
- Статистика по токенам
- Деактивация токенов

Доступные типы токенов:
- Публичные: DEMO_FREE, BASIC, PRO, UNLIMITED
- Скрытые: HIDDEN_14D, HIDDEN_30D, DEVELOPER

Использование:
1. Убедитесь что Django БД доступна
2. Запустите скрипт
3. Выберите действие из меню
4. Копируйте сгенерированные ссылки и отправляйте пользователям

Быстрая генерация из командной строки:
    python manual_token_generator.py --quick DEMO_FREE
    python manual_token_generator.py --quick DEVELOPER
"""

import os
import sys
import django
from datetime import timedelta
from pathlib import Path

# Настройка Django окружения
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ghostwriter.settings')
django.setup()

# Импорты Django после setup
from django.utils import timezone
from django.conf import settings
from generator.models import TemporaryAccessToken


class TokenGenerator:
    """Генератор токенов для ручной выдачи"""
    
    def __init__(self):
        self.site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        from generator.tariffs import TARIFFS
        self.available_tariffs = TARIFFS
    
    def generate_token(self, token_type, note=None):
        """
        Универсальный метод генерации токена любого типа
        
        Args:
            token_type (str): Тип токена (DEMO_FREE, BASIC, PRO, UNLIMITED, HIDDEN_14D, HIDDEN_30D, DEVELOPER)
            note (str): Заметка (например, имя пользователя)
        
        Returns:
            tuple: (token_object, url)
        """
        from generator.tariffs import get_tariff_config
        
        tariff = get_tariff_config(token_type)
        if not tariff:
            raise ValueError(f"Неизвестный тип токена: {token_type}")
        
        now = timezone.now()
        
        # Определяем expires_at
        if tariff['duration_days'] is None:
            expires_at = None  # Бессрочный
        else:
            expires_at = now + timedelta(days=tariff['duration_days'])
        
        # Определяем subscription_start и next_renewal для подписок
        subscription_start = None
        next_renewal = None
        if tariff.get('is_subscription'):
            subscription_start = now
            next_renewal = now + timedelta(days=tariff['duration_days'])
        
        # Создаем токен
        token = TemporaryAccessToken.objects.create(
            token_type=token_type,
            expires_at=expires_at,
            gigachat_tokens_limit=tariff['gigachat_tokens'],
            gigachat_tokens_used=0,
            openai_tokens_limit=tariff['openai_tokens'],
            openai_tokens_used=0,
            subscription_start=subscription_start,
            next_renewal=next_renewal,
            is_active=True,
            total_used=0
        )
        
        url = f"{self.site_url}/auth/token/{token.token}/"
        return token, url
    
    def generate_bulk_tokens(self, count=10, token_type='DEMO_FREE'):
        """
        Массовая генерация токенов
        
        Args:
            count (int): Количество токенов
            token_type (str): Тип токена (любой из доступных)
        
        Returns:
            list: Список кортежей (token, url)
        """
        tokens = []
        for i in range(count):
            try:
                token, url = self.generate_token(token_type)
                tokens.append((token, url))
            except Exception as e:
                print(f"Ошибка при создании токена {i+1}: {e}")
                continue
        
        return tokens
    
    def list_active_tokens(self, token_type=None, limit=20):
        """
        Список активных токенов
        
        Args:
            token_type (str): Фильтр по типу токена (опционально)
            limit (int): Максимальное количество токенов
        
        Returns:
            QuerySet: Активные токены
        """
        query = TemporaryAccessToken.objects.filter(
            is_active=True
        ).order_by('-created_at')
        
        # Фильтр по сроку действия (исключаем бессрочные)
        from django.db.models import Q
        query = query.filter(
            Q(expires_at__gt=timezone.now()) | Q(expires_at__isnull=True)
        )
        
        if token_type:
            query = query.filter(token_type=token_type)
        
        return query[:limit]
    
    def deactivate_token(self, token_uuid):
        """Деактивирует токен по UUID"""
        try:
            token = TemporaryAccessToken.objects.get(token=token_uuid)
            token.is_active = False
            token.save()
            return True
        except TemporaryAccessToken.DoesNotExist:
            return False
    
    def get_token_stats(self):
        """Статистика по токенам"""
        total = TemporaryAccessToken.objects.count()
        active = TemporaryAccessToken.objects.filter(is_active=True).count()
        
        by_type = {}
        for token_type, _ in TemporaryAccessToken.TOKEN_TYPES:
            count = TemporaryAccessToken.objects.filter(
                token_type=token_type,
                is_active=True
            ).count()
            by_type[token_type] = count
        
        return {
            'total': total,
            'active': active,
            'by_type': by_type
        }


def print_header():
    """Красивый заголовок"""
    print("\n" + "="*70)
    print("🎫 GHOSTWRITER - Генератор токенов".center(70))
    print("="*70 + "\n")


def print_menu():
    """Главное меню"""
    print("\n📋 Выберите действие:\n")
    print("  === ПУБЛИЧНЫЕ ТАРИФЫ ===")
    print("  1. 🆓 Бесплатный старт (10K GigaChat + 500 OpenAI, бессрочно)")
    print("  2. 📊 Базовый (50K GigaChat + 3K OpenAI, 30 дней)")
    print("  3. ⭐ Про (200K GigaChat + 15K OpenAI, 30 дней)")
    print("  4. 🚀 Безлимит (∞ GigaChat + 50K OpenAI, 30 дней)")
    print("\n  === СКРЫТЫЕ ТАРИФЫ ===")
    print("  5. 🔒 Скрытый 14 дней (безлимит GigaChat, без OpenAI)")
    print("  6. 🔒 Скрытый 30 дней (безлимит GigaChat, без OpenAI)")
    print("  7. 👨‍💻 DEVELOPER (бессрочный, безлимит всего)")
    print("\n  === УТИЛИТЫ ===")
    print("  8. 📦 Массовая генерация токенов")
    print("  9. 📊 Список активных токенов")
    print("  10. 📈 Статистика токенов")
    print("  11. ❌ Деактивировать токен")
    print("  0. 🚪 Выход")
    print()


def print_token_info(token, url):
    """Красивый вывод информации о токене"""
    print("\n" + "─"*70)
    print(f"✅ Токен успешно создан!")
    print("─"*70)
    print(f"📝 Тип: {token.get_token_type_display()}")
    print(f"🔑 UUID: {token.token}")
    print(f"📅 Создан: {token.created_at.strftime('%d.%m.%Y %H:%M')}")
    if token.expires_at:
        print(f"⏰ Истекает: {token.expires_at.strftime('%d.%m.%Y %H:%M')}")
    else:
        print(f"⏰ Истекает: бессрочно")
    
    # Лимиты токенов
    if token.gigachat_tokens_limit == -1:
        print(f"⚡ GigaChat: безлимит")
    else:
        print(f"⚡ GigaChat: {token.gigachat_tokens_limit:,} токенов")
    
    if token.openai_tokens_limit == -1:
        print(f"🤖 OpenAI: безлимит")
    elif token.openai_tokens_limit == 0:
        print(f"🤖 OpenAI: недоступен")
    else:
        print(f"🤖 OpenAI: {token.openai_tokens_limit:,} токенов")
    
    print(f"\n🔗 ССЫЛКА ДЛЯ ПОЛЬЗОВАТЕЛЯ:")
    print(f"   {url}")
    print("─"*70 + "\n")
    
    # Копируем в буфер обмена (опционально)
    try:
        import pyperclip
        pyperclip.copy(url)
        print("📋 Ссылка скопирована в буфер обмена!")
    except ImportError:
        print("💡 Установите pyperclip для автокопирования: pip install pyperclip")


def interactive_mode():
    """Интерактивный режим"""
    generator = TokenGenerator()
    
    # Маппинг выбора на тип токена
    token_type_map = {
        '1': 'DEMO_FREE',
        '2': 'BASIC',
        '3': 'PRO',
        '4': 'UNLIMITED',
        '5': 'HIDDEN_14D',
        '6': 'HIDDEN_30D',
        '7': 'DEVELOPER',
    }
    
    while True:
        print_header()
        print_menu()
        
        try:
            choice = input("Ваш выбор: ").strip()
            
            # Генерация токенов (1-7)
            if choice in token_type_map:
                token_type = token_type_map[choice]
                tariff = generator.available_tariffs.get(token_type)
                
                if tariff:
                    print(f"\n🔄 Создаю токен: {tariff['name']}...")
                    print(f"   {tariff['description']}\n")
                    
                    token, url = generator.generate_token(token_type)
                    print_token_info(token, url)
                    input("\nНажмите Enter для продолжения...")
                else:
                    print(f"\n❌ Ошибка: тариф {token_type} не найден")
                    input("\nНажмите Enter для продолжения...")
            
            elif choice == '8':
                # Массовая генерация
                print("\n📦 Массовая генерация токенов\n")
                
                count = int(input("Количество токенов (по умолчанию 10): ").strip() or "10")
                print("\nТип токена:")
                print("  1. HIDDEN_14D (14 дней)")
                print("  2. HIDDEN_30D (30 дней)")
                print("  3. DEVELOPER (бессрочный)")
                token_type_choice = input("Выбор (1-3, по умолчанию 1): ").strip() or "1"
                
                token_types = {'1': 'HIDDEN_14D', '2': 'HIDDEN_30D', '3': 'DEVELOPER'}
                token_type = token_types.get(token_type_choice, 'HIDDEN_14D')
                
                print(f"\nГенерация {count} токенов типа {token_type}...")
                tokens = generator.generate_bulk_tokens(
                    count=count,
                    token_type=token_type
                )
                
                print(f"\n✅ Создано {len(tokens)} токенов:\n")
                for i, (token, url) in enumerate(tokens, 1):
                    print(f"{i}. {url}")
                
                # Сохранить в файл
                save = input("\nСохранить ссылки в файл? (y/n): ").strip().lower()
                if save == 'y':
                    filename = f"tokens_{token_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"Ghostwriter - {token_type} токены\n")
                        f.write(f"Создано: {timezone.now().strftime('%d.%m.%Y %H:%M')}\n")
                        f.write(f"Количество: {len(tokens)}\n")
                        f.write("="*70 + "\n\n")
                        for i, (token, url) in enumerate(tokens, 1):
                            f.write(f"{i}. {url}\n")
                    print(f"\n✅ Сохранено в файл: {filename}")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '9':
                # Список активных токенов
                print("\n📊 Активные токены\n")
                
                print("Фильтр по типу:")
                print("  0. Все")
                print("  === ПУБЛИЧНЫЕ ===")
                print("  1. DEMO_FREE")
                print("  2. BASIC")
                print("  3. PRO")
                print("  4. UNLIMITED")
                print("\n  === СКРЫТЫЕ ===")
                print("  5. HIDDEN_14D")
                print("  6. HIDDEN_30D")
                print("  7. DEVELOPER")
                
                filter_choice = input("\nВыбор (0-7, по умолчанию 0): ").strip() or "0"
                
                filter_map = {
                    '0': None,
                    '1': 'DEMO_FREE',
                    '2': 'BASIC',
                    '3': 'PRO',
                    '4': 'UNLIMITED',
                    '5': 'HIDDEN_14D',
                    '6': 'HIDDEN_30D',
                    '7': 'DEVELOPER'
                }
                token_filter = filter_map.get(filter_choice)
                
                tokens = generator.list_active_tokens(token_type=token_filter)
                
                if not tokens:
                    print("\n⚠️ Активных токенов не найдено")
                else:
                    print(f"\nНайдено токенов: {len(tokens)}\n")
                    for token in tokens:
                        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        print(f"🔑 {token.token}")
                        print(f"📝 Тип: {token.get_token_type_display()}")
                        print(f"📅 Создан: {token.created_at.strftime('%d.%m.%Y %H:%M')}")
                        if token.expires_at:
                            print(f"⏰ Истекает: {token.expires_at.strftime('%d.%m.%Y %H:%M')}")
                        else:
                            print(f"⏰ Истекает: бессрочно")
                        print(f"📊 Использован: {token.total_used} раз")
                        if token.gigachat_tokens_limit == -1:
                            print(f"⚡ GigaChat: безлимит (использовано: {token.gigachat_tokens_used:,})")
                        else:
                            print(f"⚡ GigaChat: {token.gigachat_tokens_used:,}/{token.gigachat_tokens_limit:,}")
                        if token.openai_tokens_limit == -1:
                            print(f"🤖 OpenAI: безлимит (использовано: {token.openai_tokens_used:,})")
                        elif token.openai_tokens_limit == 0:
                            print(f"🤖 OpenAI: недоступен")
                        else:
                            print(f"🤖 OpenAI: {token.openai_tokens_used:,}/{token.openai_tokens_limit:,}")
                        if token.last_used:
                            print(f"🕐 Последнее использование: {token.last_used.strftime('%d.%m.%Y %H:%M')}")
                        print(f"🔗 {generator.site_url}/auth/token/{token.token}/")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '10':
                # Статистика
                stats = generator.get_token_stats()
                print("\n📈 Статистика токенов\n")
                print(f"Всего токенов: {stats['total']}")
                print(f"Активных токенов: {stats['active']}")
                print("\nПо типам:")
                print("  === ПУБЛИЧНЫЕ ===")
                for token_type in ['DEMO_FREE', 'BASIC', 'PRO', 'UNLIMITED']:
                    count = stats['by_type'].get(token_type, 0)
                    tariff = generator.available_tariffs.get(token_type, {})
                    name = tariff.get('name', token_type)
                    print(f"  {name} ({token_type}): {count}")
                print("\n  === СКРЫТЫЕ ===")
                for token_type in ['HIDDEN_14D', 'HIDDEN_30D', 'DEVELOPER']:
                    count = stats['by_type'].get(token_type, 0)
                    tariff = generator.available_tariffs.get(token_type, {})
                    name = tariff.get('name', token_type)
                    print(f"  {name} ({token_type}): {count}")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '11':
                # Деактивация токена
                print("\n❌ Деактивация токена\n")
                token_uuid = input("Введите UUID токена: ").strip()
                
                if generator.deactivate_token(token_uuid):
                    print("\n✅ Токен успешно деактивирован")
                else:
                    print("\n⚠️ Токен не найден")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '0':
                print("\n👋 До свидания!\n")
                break
            
            else:
                print("\n⚠️ Неверный выбор. Попробуйте снова.")
                input("\nНажмите Enter для продолжения...")
        
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем. До свидания!\n")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            input("\nНажмите Enter для продолжения...")


def quick_generate(token_type='DEMO_FREE'):
    """
    Быстрая генерация одного токена (для скриптов)
    
    Args:
        token_type (str): Тип токена (по умолчанию DEMO_FREE)
    
    Returns:
        str: URL токена
    """
    generator = TokenGenerator()
    token, url = generator.generate_token(token_type)
    print(url)
    return url


if __name__ == '__main__':
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == '--quick':
            # Быстрая генерация (по умолчанию DEMO_FREE)
            token_type = sys.argv[2] if len(sys.argv) > 2 else 'DEMO_FREE'
            quick_generate(token_type)
        elif sys.argv[1] == '--help':
            print(__doc__)
            print("\nДоступные типы токенов:")
            from generator.tariffs import TARIFFS
            for token_type, tariff in TARIFFS.items():
                print(f"  {token_type}: {tariff['name']} - {tariff['description']}")
            print("\nПримеры использования:")
            print("  python manual_token_generator.py --quick DEMO_FREE")
            print("  python manual_token_generator.py --quick DEVELOPER")
        else:
            print("Неизвестная команда. Используйте --help для справки.")
    else:
        # Интерактивный режим
        interactive_mode()
