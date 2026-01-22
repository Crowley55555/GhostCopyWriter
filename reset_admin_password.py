#!/usr/bin/env python3
"""
Скрипт для сброса пароля Django superuser

Использование:
    python reset_admin_password.py --username admin --password новый_пароль
"""

import os
import sys
import django
import argparse
from pathlib import Path

# Настройка Django окружения
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ghostwriter.settings')
django.setup()

from django.contrib.auth.models import User

def reset_password(username, password):
    """Сбрасывает пароль для указанного пользователя"""
    
    try:
        user = User.objects.get(username=username)
        
        # Устанавливаем новый пароль
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        
        print("="*70)
        print("OK: PAROL USPESHNO IZMENEN!")
        print("="*70)
        print(f"Username: {user.username}")
        print(f"Email: {user.email or '(ne ukazan)'}")
        print(f"Novyj parol: {'*' * len(password)}")
        print("\nAdmin-panel: http://localhost:8000/admin/")
        print("="*70)
        
    except User.DoesNotExist:
        print(f"ERROR: Polzovatel '{username}' ne najden!")
        print("\nDostupnye superuser:")
        for user in User.objects.filter(is_superuser=True):
            print(f"  - {user.username}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Сброс пароля Django superuser')
    parser.add_argument('--username', required=True, help='Username пользователя')
    parser.add_argument('--password', required=True, help='Новый пароль')
    
    args = parser.parse_args()
    
    reset_password(args.username, args.password)
