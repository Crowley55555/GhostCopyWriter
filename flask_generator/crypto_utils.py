import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Загружаем переменные окружения
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

def encrypt_data(data: bytes) -> str:
    return cipher.encrypt(data).decode()

def decrypt_data(token: str) -> bytes:
    return cipher.decrypt(token.encode()) 