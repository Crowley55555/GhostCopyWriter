import os
from cryptography.fernet import Fernet

ENCRYPTION_KEY = os.environ.get('GENERATOR_ENCRYPTION_KEY', Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_data(data: bytes) -> str:
    return cipher.encrypt(data).decode()

def decrypt_data(token: str) -> bytes:
    return cipher.decrypt(token.encode()) 