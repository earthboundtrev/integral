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
_derived_key_cache: dict[tuple[str, bytes], bytes] = {}


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
    cache_key = (passphrase, salt)
    cached = _derived_key_cache.get(cache_key)
    if cached is not None:
        return cached
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
    _derived_key_cache[cache_key] = key
    return key


def _existing_salt(path: str) -> bytes | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and data.get("integral_encrypted") and data.get("salt"):
            return base64.b64decode(data["salt"])
    except (json.JSONDecodeError, OSError, ValueError):
        return None
    return None


def encrypt_payload(
    payload: dict[str, Any],
    passphrase: str,
    *,
    salt: bytes | None = None,
) -> dict[str, Any]:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Install cryptography: pip install cryptography")
    if salt is None:
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
        salt = _existing_salt(path)
        to_write = encrypt_payload(payload, passphrase, salt=salt)
    else:
        to_write = payload
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(to_write, handle, indent=2, ensure_ascii=False)
