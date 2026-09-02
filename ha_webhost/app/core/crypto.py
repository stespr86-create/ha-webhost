"""Verschlüsselung von Secrets (Git-Access-Token) in der SQLite-DB.

Der Schlüssel wird beim ersten Start einmalig generiert und persistent
unter /data/secret.key abgelegt (0600) - das Add-on-eigene /data ist
bereits die Vertrauensgrenze (nur Add-on selbst + Root auf dem Host
lesbar), analog zur SQLite-DB selbst.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_DIR

KEY_PATH = DATA_DIR / "secret.key"


class DecryptionError(RuntimeError):
    pass


def _load_or_create_key() -> bytes:
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()

    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    os.chmod(KEY_PATH, 0o600)
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError(
            "Gespeicherter Wert konnte nicht entschlüsselt werden "
            "(secret.key fehlt oder wurde ausgetauscht)."
        ) from exc
