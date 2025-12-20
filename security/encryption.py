from cryptography.fernet import Fernet
import base64
import os
import hashlib

_SECRET = os.getenv("DATA_ENCRYPTION_SECRET", "fallback_secret")

def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)

FERNET = Fernet(_derive_key(_SECRET))


def encrypt_value(value: str) -> str:
    if value is None:
        return None
    return FERNET.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    if value is None:
        return None
    return FERNET.decrypt(value.encode()).decode()
