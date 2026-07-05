"""Optional encryption at rest for Integral journal data."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


ENVELOPE_VERSION = 1


def is_encrypted_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return isinstance(data, dict) and data.get("integral_encrypted") is True
    except (json.JSONDecodeError, OSError):
        return False


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_payload(payload: dict[str, Any], passphrase: str) -> dict[str, Any]:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Install cryptography: pip install cryptography")
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return {
        "integral_encrypted": True,
        "envelope_version": ENVELOPE_VERSION,
        "salt": base64.b64encode(salt).decode("ascii"),
        "ciphertext": token.decode("ascii"),
    }


def decrypt_payload(envelope: dict[str, Any], passphrase: str) -> dict[str, Any]:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Install cryptography: pip install cryptography")
    if not envelope.get("integral_encrypted"):
        raise ValueError("File is not an Integral encrypted envelope.")
    salt = base64.b64decode(envelope["salt"])
    key = _derive_key(passphrase, salt)
    raw = Fernet(key).decrypt(envelope["ciphertext"].encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Decrypted payload is invalid.")
    return data


def load_data_file(path: str, passphrase: str | None) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict) and raw.get("integral_encrypted"):
        if not passphrase:
            raise PermissionError("Passphrase required for encrypted journal.")
        return decrypt_payload(raw, passphrase)
    return raw


def save_data_file(path: str, payload: dict[str, Any], *, encrypted: bool, passphrase: str | None) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if encrypted:
        if not passphrase:
            raise PermissionError("Passphrase required to save encrypted journal.")
        to_write = encrypt_payload(payload, passphrase)
    else:
        to_write = payload
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(to_write, handle, indent=2, ensure_ascii=False)
