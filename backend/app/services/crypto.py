import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    import base64

    digest = hashlib.sha256(settings.TOKEN_ENCRYPTION_SECRET.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain_text: str) -> str:
    return _fernet().encrypt(plain_text.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher_text: str) -> str:
    return _fernet().decrypt(cipher_text.encode("ascii")).decode("utf-8")
