#!/usr/bin/env python3
"""
Модуль шифрования для Flask Generator API

Обеспечивает безопасную передачу данных между Django и Flask приложениями
с использованием симметричного шифрования Fernet.

Функции:
- encrypt_data(): Шифрование данных
- decrypt_data(): Расшифровка данных
"""

# =============================================================================
# IMPORTS
# =============================================================================
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

ENCRYPTION_KEY = os.environ.get('GENERATOR_ENCRYPTION_KEY')

if not ENCRYPTION_KEY:
    # Генерируем валидный ключ автоматически
    key = Fernet.generate_key()
    ENCRYPTION_KEY = key.decode()
    print(f"🔑 Flask: Сгенерирован новый ключ: {ENCRYPTION_KEY}")
    print("💡 Добавьте этот ключ в ОБА .env файла:")
    print(f"GENERATOR_ENCRYPTION_KEY={ENCRYPTION_KEY}")
    print("🔄 Затем перезапустите приложения")

try:
    if isinstance(ENCRYPTION_KEY, str):
        cipher = Fernet(ENCRYPTION_KEY.encode())
    else:
        cipher = Fernet(ENCRYPTION_KEY)
    print(f"✅ Flask: Ключ шифрования инициализирован")
except ValueError as e:
    # Генерируем новый валидный ключ
    key = Fernet.generate_key()
    ENCRYPTION_KEY = key.decode()
    cipher = Fernet(key)
    print(f"🔑 Flask: Сгенерирован исправленный ключ: {ENCRYPTION_KEY}")
    print("💡 Добавьте этот ключ в ОБА .env файла:")
    print(f"GENERATOR_ENCRYPTION_KEY={ENCRYPTION_KEY}")
    print("🔄 Затем перезапустите приложения")

# =============================================================================
# ENCRYPTION FUNCTIONS
# =============================================================================

def encrypt_data(data: bytes) -> str:
    """
    Шифрует данные с помощью Fernet
    
    Args:
        data (bytes): Данные для шифрования
    
    Returns:
        str: Зашифрованная строка в base64
    """
    return cipher.encrypt(data).decode()

def decrypt_data(token: str) -> bytes:
    """
    Расшифровывает данные с помощью Fernet
    
    Args:
        token (str): Зашифрованная строка в base64
    
    Returns:
        bytes: Расшифрованные данные
    """
    return cipher.decrypt(token.encode()) 