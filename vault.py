"""Optional encryption at rest for Integral journal data."""

from __future__ import annotations

import base64
import json
import os
import threading
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidToken = None  # type: ignore[misc, assignment]


ENVELOPE_VERSION = 1
_derived_key_cache: dict[tuple[str, bytes], bytes] = {}
_save_lock = threading.Lock()


class VaultPassphraseError(Exception):
    """Passphrase missing or incorrect — not file corruption."""


class PassphraseRequiredError(VaultPassphraseError):
    """Encrypted journal requires a passphrase."""


class WrongPassphraseError(VaultPassphraseError):
    """Decryption failed because the passphrase does not match."""


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
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Install cryptography: pip install cryptography")
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
    try:
        raw = Fernet(key).decrypt(envelope["ciphertext"].encode("ascii"))
    except InvalidToken:
        raise WrongPassphraseError("Incorrect passphrase for encrypted journal.") from None
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Decrypted payload is invalid.")
    return data


def load_data_file(path: str, passphrase: str | None) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict) and raw.get("integral_encrypted"):
        if not passphrase:
            raise PassphraseRequiredError("Passphrase required for encrypted journal.")
        return decrypt_payload(raw, passphrase)
    return raw


def load_data_file_with_recovery(
    path: str, 
    passphrase: str | None,
    *,
    on_recovery_prompt=None,
    on_both_corrupt_prompt=None
) -> dict[str, Any]:
    """Load data.json with automatic recovery from .bak if corrupt.
    
    If data.json fails to load or parse:
    1. Try to load from data.json.bak
    2. If .bak is valid, prompt to restore it (via callback)
    3. If both are corrupt, prompt to preserve and start empty
    
    Args:
        path: Path to data.json
        passphrase: Vault passphrase if encrypted
        on_recovery_prompt: Callable(bak_path, bak_timestamp_str) -> bool
            Returns True to restore from backup, False to abort
        on_both_corrupt_prompt: Callable() -> bool
            Returns True to preserve corrupt file and start empty, False to abort
    
    Returns:
        Loaded data dict (or empty dict if starting fresh)
        
    Raises:
        ValueError: If user declines recovery and no valid data exists
    """
    import logging
    import shutil
    from datetime import datetime
    
    # Try to load the main file
    try:
        return load_data_file(path, passphrase)
    except VaultPassphraseError:
        raise
    except PermissionError:
        raise
    except (json.JSONDecodeError, ValueError) as e:
        logging.error(f"Failed to load {path}: {e}")
        
        # Try to load backup
        bak_path = f"{path}.bak"
        bak_data = None
        bak_timestamp = None
        
        if os.path.exists(bak_path):
            try:
                bak_data = load_data_file(bak_path, passphrase)
                # Get backup timestamp
                bak_stat = os.stat(bak_path)
                bak_timestamp = datetime.fromtimestamp(bak_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except VaultPassphraseError:
                raise
            except PermissionError:
                raise
            except (json.JSONDecodeError, ValueError) as bak_e:
                logging.error(f"Backup {bak_path} is also corrupt: {bak_e}")
        
        # If backup is valid, offer to restore it
        if bak_data is not None:
            if on_recovery_prompt is None or on_recovery_prompt(bak_path, bak_timestamp):
                # Preserve the corrupt file before restoring
                corrupt_path = f"{path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                shutil.copy2(path, corrupt_path)
                logging.info(f"Preserved corrupt file as {corrupt_path}")
                
                # Restore backup atomically with save lock
                from integral_io import atomic_copy_file
                atomic_copy_file(bak_path, path)
                logging.info(f"Restored from backup: {bak_path}")
                return bak_data
            else:
                raise ValueError("User declined recovery from backup")
        
        # Both files are corrupt - offer to start empty
        if on_both_corrupt_prompt is None or on_both_corrupt_prompt():
            # Preserve corrupt file
            corrupt_path = f"{path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            if os.path.exists(path):
                shutil.copy2(path, corrupt_path)
                logging.info(f"Preserved corrupt file as {corrupt_path}")
            
            # Start with empty data
            logging.warning("Starting with empty data after corruption")
            return {}
        else:
            raise ValueError("User declined to start with empty data")



def save_data_file(path: str, payload: dict[str, Any], *, encrypted: bool, passphrase: str | None) -> None:
    """Atomically save data.json with backup rotation.
    
    Write to temp file, fsync, then os.replace. Before replacing, rotate the
    current good data.json to data.json.bak. Use a lock to serialize saves.
    """
    with _save_lock:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if encrypted:
            if not passphrase:
                raise PassphraseRequiredError("Passphrase required to save encrypted journal.")
            salt = _existing_salt(path)
            to_write = encrypt_payload(payload, passphrase, salt=salt)
        else:
            to_write = payload
        
        # Write to temp file in same directory
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(to_write, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        
        # Rotate current good file to backup before replacing
        bak_path = f"{path}.bak"
        if os.path.exists(path):
            # Use os.replace which is atomic on both Windows and Unix
            if os.path.exists(bak_path):
                os.remove(bak_path)
            os.replace(path, bak_path)
        
        # Atomic replace temp with real file
        os.replace(temp_path, path)
