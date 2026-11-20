from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _cipher():
    key = settings.CONFIG_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured(
            "Configure CONFIG_ENCRYPTION_KEY no ambiente antes de salvar segredos."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "CONFIG_ENCRYPTION_KEY deve ser uma chave Fernet válida."
        ) from exc


def validate_encryption_key():
    _cipher()


def encrypt_bytes(value):
    return _cipher().encrypt(value)


def decrypt_bytes(value):
    try:
        return _cipher().decrypt(bytes(value))
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            "Não foi possível descriptografar os dados. Verifique CONFIG_ENCRYPTION_KEY."
        ) from exc


def encrypt_text(value):
    return encrypt_bytes(value.encode("utf-8"))


def decrypt_text(value):
    return decrypt_bytes(value).decode("utf-8")
