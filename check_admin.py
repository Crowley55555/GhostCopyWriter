#!/usr/bin/env python3
"""
Скрипт для проверки и исправления доступа к админ-панели

Использование:
    python check_admin.py
"""

import os
import sys
import django
from pathlib import Path

# Настройка Django окружения
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ghostwriter.settings')
django.setup()

from django.contrib.auth.models import User

def check_and_fix_admin():
    """Проверяет и исправляет доступ к админ-панели"""
    
    print("="*70)
    print("PROVERKA DOSTUPA K ADMIN-PANELI")
    print("="*70)
    
    # Проверяем всех superuser
    superusers = User.objects.filter(is_superuser=True)
    
    if not superusers.exists():
        print("\nERROR: Superuser ne najden!")
        print("\nSozdayte superuser komandoj:")
        print("  python manage.py createsuperuser")
        return
    
    print(f"\nOK: Najdeno superuser: {superusers.count()}")
    print("\nSpisok superuser:")
    print("-" * 70)
    
    for user in superusers:
        print(f"\nUsername: {user.username}")
        print(f"Email: {user.email or '(ne ukazan)'}")
        print(f"is_superuser: {user.is_superuser}")
        print(f"is_staff: {user.is_staff}")
        print(f"is_active: {user.is_active}")
        print(f"Data registracii: {user.date_joined}")
        
        # Проверяем проблемы
        issues = []
        if not user.is_staff:
            issues.append("WARNING: is_staff = False (nuzhno True dlya adminki)")
        if not user.is_active:
            issues.append("WARNING: is_active = False (akkaunt neaktiven)")
        if not user.email:
            issues.append("WARNING: Email ne ukazan (rekomenduetsya)")
        
        if issues:
            print("\nPROBLEMY:")
            for issue in issues:
                print(f"   {issue}")
            
            # Исправляем автоматически
            print("\nISPRAVLENIE:")
            if not user.is_staff:
                user.is_staff = True
                print("   OK: Ustanovlen is_staff = True")
            if not user.is_active:
                user.is_active = True
                print("   OK: Ustanovlen is_active = True")
            
            user.save()
            print("   OK: Izmeneniya sohraneny!")
        else:
            print("\nOK: Vse nastrojki korrektny!")
    
    print("\n" + "="*70)
    print("ADMIN-PANEL DOSTUPNA PO ADRESU:")
    print("   http://localhost:8000/admin/")
    print("\nISPOLZUJTE:")
    print("   - Username: (iz spiska vyshe)")
    print("   - Password: (kotoryj vy ukazali pri sozdanii)")
    print("="*70)
    
    # Проверяем пароль
    print("\nPROVERKA PAROLYA:")
    print("Esli zabyl parol, mozhno sbrosit ego:")
    print("\nVariant 1: Cherez Django shell")
    print("  python manage.py shell")
    print("  >>> from django.contrib.auth.models import User")
    print("  >>> user = User.objects.get(username='vash_username')")
    print("  >>> user.set_password('novyj_parol')")
    print("  >>> user.save()")
    print("\nVariant 2: Cherez skript")
    print("  python reset_admin_password.py --username vash_username --password novyj_parol")

if __name__ == '__main__':
    check_and_fix_admin()
