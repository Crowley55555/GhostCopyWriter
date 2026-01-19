#!/usr/bin/env python3
"""
Ручной генератор DEMO токенов для бета-теста Ghostwriter

Запуск из PyCharm или терминала:
    python manual_token_generator.py

Возможности:
- Генерация DEMO токенов без проверок на дубликаты
- Настраиваемый срок действия и лимиты
- Массовая генерация токенов
- Список активных токенов
- Деактивация токенов

Использование:
1. Убедитесь что Django БД доступна
2. Запустите скрипт
3. Выберите действие из меню
4. Копируйте сгенерированные ссылки и отправляйте бета-тестерам
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
    
    def generate_demo_token(self, days=7, note=None):
        """
        Генерирует DEMO токен без проверок на дубликаты
        
        Args:
            days (int): Срок действия в днях (по умолчанию 7)
            note (str): Заметка (например, имя тестера)
        
        Returns:
            tuple: (token_object, url)
        """
        now = timezone.now()
        expires_at = now + timedelta(days=days)
        
        token = TemporaryAccessToken.objects.create(
            token_type='DEMO',
            expires_at=expires_at,
            daily_generations_left=-1,  # Безлимит
            generations_reset_date=None,
            is_active=True,
            total_used=0
        )
        
        url = f"{self.site_url}/auth/token/{token.token}/"
        
        return token, url
    
    def generate_monthly_token(self, note=None):
        """Генерирует MONTHLY токен (30 дней, безлимит)"""
        now = timezone.now()
        expires_at = now + timedelta(days=30)
        
        token = TemporaryAccessToken.objects.create(
            token_type='MONTHLY',
            expires_at=expires_at,
            daily_generations_left=-1,  # Безлимит
            is_active=True,
            total_used=0
        )
        
        url = f"{self.site_url}/auth/token/{token.token}/"
        return token, url
    
    def generate_yearly_token(self, note=None):
        """Генерирует YEARLY токен (365 дней, безлимит)"""
        now = timezone.now()
        expires_at = now + timedelta(days=365)
        
        token = TemporaryAccessToken.objects.create(
            token_type='YEARLY',
            expires_at=expires_at,
            daily_generations_left=-1,  # Безлимит
            is_active=True,
            total_used=0
        )
        
        url = f"{self.site_url}/auth/token/{token.token}/"
        return token, url
    
    def generate_developer_token(self, note=None):
        """Генерирует DEVELOPER токен (бессрочный, безлимит)"""
        # Устанавливаем срок на 100 лет в будущем (фактически бессрочный)
        now = timezone.now()
        expires_at = now + timedelta(days=365*100)
        
        token = TemporaryAccessToken.objects.create(
            token_type='DEVELOPER',
            expires_at=expires_at,
            daily_generations_left=-1,  # Безлимит
            is_active=True,
            total_used=0
        )
        
        url = f"{self.site_url}/auth/token/{token.token}/"
        return token, url
    
    def generate_bulk_tokens(self, count=10, token_type='DEMO', days=7):
        """
        Массовая генерация токенов
        
        Args:
            count (int): Количество токенов
            token_type (str): Тип токена
            days (int): Срок действия (для DEMO)
        
        Returns:
            list: Список кортежей (token, url)
        """
        tokens = []
        for i in range(count):
            if token_type == 'DEMO':
                token, url = self.generate_demo_token(days)
            elif token_type == 'MONTHLY':
                token, url = self.generate_monthly_token()
            elif token_type == 'YEARLY':
                token, url = self.generate_yearly_token()
            elif token_type == 'DEVELOPER':
                token, url = self.generate_developer_token()
            else:
                continue
            
            tokens.append((token, url))
        
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
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('-created_at')
        
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
    print("🎫 GHOSTWRITER - Генератор DEMO токенов для бета-теста".center(70))
    print("="*70 + "\n")


def print_menu():
    """Главное меню"""
    print("\n📋 Выберите действие:\n")
    print("  1. 🆓 Сгенерировать DEMO токен (7 дней, безлимит)")
    print("  2. 📅 Сгенерировать MONTHLY токен (30 дней, безлимит)")
    print("  3. 📆 Сгенерировать YEARLY токен (365 дней, безлимит)")
    print("  4. 👨‍💻 Сгенерировать DEVELOPER токен (бессрочный, безлимит)")
    print("  5. 📦 Массовая генерация токенов")
    print("  6. 📊 Список активных токенов")
    print("  7. 📈 Статистика токенов")
    print("  8. ❌ Деактивировать токен")
    print("  9. ⚙️ Настройки генерации")
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
    print(f"⏰ Истекает: {token.expires_at.strftime('%d.%m.%Y %H:%M')}")
    print(f"⚡ Лимит: Безлимит")
    
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
    
    # Настройки по умолчанию
    settings_demo = {'days': 7}
    
    while True:
        print_header()
        print_menu()
        
        try:
            choice = input("Ваш выбор: ").strip()
            
            if choice == '1':
                # DEMO токен (7 дней, безлимит)
                token, url = generator.generate_demo_token(
                    days=settings_demo['days']
                )
                print_token_info(token, url)
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '2':
                # MONTHLY токен
                token, url = generator.generate_monthly_token()
                print_token_info(token, url)
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '3':
                # YEARLY токен
                token, url = generator.generate_yearly_token()
                print_token_info(token, url)
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '4':
                # DEVELOPER токен
                token, url = generator.generate_developer_token()
                print_token_info(token, url)
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '5':
                # Массовая генерация
                print("\n📦 Массовая генерация токенов\n")
                
                count = int(input("Количество токенов (по умолчанию 10): ").strip() or "10")
                print("\nТип токена:")
                print("  1. DEMO")
                print("  2. MONTHLY")
                print("  3. YEARLY")
                token_type_choice = input("Выбор (1-3, по умолчанию 1): ").strip() or "1"
                
                token_types = {'1': 'DEMO', '2': 'MONTHLY', '3': 'YEARLY'}
                token_type = token_types.get(token_type_choice, 'DEMO')
                
                print(f"\nГенерация {count} токенов типа {token_type}...")
                tokens = generator.generate_bulk_tokens(
                    count=count,
                    token_type=token_type,
                    days=settings_demo['days']
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
            
            elif choice == '6':
                # Список активных токенов
                print("\n📊 Активные токены\n")
                
                print("Фильтр по типу:")
                print("  1. Все")
                print("  2. DEMO")
                print("  3. MONTHLY")
                print("  4. YEARLY")
                print("  5. DEVELOPER")
                filter_choice = input("Выбор (1-5, по умолчанию 1): ").strip() or "1"
                
                filters = {'1': None, '2': 'DEMO', '3': 'MONTHLY', '4': 'YEARLY', '5': 'DEVELOPER'}
                token_filter = filters.get(filter_choice)
                
                tokens = generator.list_active_tokens(token_type=token_filter)
                
                if not tokens:
                    print("\n⚠️ Активных токенов не найдено")
                else:
                    print(f"\nНайдено токенов: {tokens.count()}\n")
                    for token in tokens:
                        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        print(f"🔑 {token.token}")
                        print(f"📝 Тип: {token.get_token_type_display()}")
                        print(f"📅 Создан: {token.created_at.strftime('%d.%m.%Y %H:%M')}")
                        print(f"⏰ Истекает: {token.expires_at.strftime('%d.%m.%Y %H:%M')}")
                        print(f"📊 Использован: {token.total_used} раз")
                        if token.last_used:
                            print(f"🕐 Последнее использование: {token.last_used.strftime('%d.%m.%Y %H:%M')}")
                        print(f"🔗 {generator.site_url}/auth/token/{token.token}/")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '7':
                # Статистика
                stats = generator.get_token_stats()
                print("\n📈 Статистика токенов\n")
                print(f"Всего токенов: {stats['total']}")
                print(f"Активных токенов: {stats['active']}")
                print("\nПо типам:")
                for token_type, count in stats['by_type'].items():
                    print(f"  {token_type}: {count}")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '8':
                # Деактивация токена
                print("\n❌ Деактивация токена\n")
                token_uuid = input("Введите UUID токена: ").strip()
                
                if generator.deactivate_token(token_uuid):
                    print("\n✅ Токен успешно деактивирован")
                else:
                    print("\n⚠️ Токен не найден")
                
                input("\nНажмите Enter для продолжения...")
            
            elif choice == '9':
                # Настройки
                print("\n⚙️ Настройки генерации DEMO токенов\n")
                print("ℹ️ DEMO токены теперь без лимита генераций (только срок действия)\n")
                
                days = input(f"Срок действия в днях (текущее: {settings_demo['days']}): ").strip()
                if days:
                    settings_demo['days'] = int(days)
                
                print(f"\n✅ Настройки обновлены:")
                print(f"   Срок: {settings_demo['days']} дней")
                print(f"   Лимит: Безлимит")
                
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
            input("\nНажмите Enter для продолжения...")


def quick_generate():
    """Быстрая генерация одного DEMO токена (для скриптов)"""
    generator = TokenGenerator()
    token, url = generator.generate_demo_token()
    print(url)
    return url


if __name__ == '__main__':
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == '--quick':
            # Быстрая генерация
            quick_generate()
        elif sys.argv[1] == '--help':
            print(__doc__)
        else:
            print("Неизвестная команда. Используйте --help для справки.")
    else:
        # Интерактивный режим
        interactive_mode()
