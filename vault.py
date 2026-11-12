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

_LEFTOVER_SAVE_TEMP_WARNING = (
    "Could not remove a leftover save temp file; will retry on the next save."
)
_MISMATCHED_JOURNAL_BACKUP_WARNING = (
    "Could not remove a mismatched journal backup file; will retry on the next save."
)
_STARTUP_DEFER_BACKUP_CLEANUP_WARNING = (
    "Journal backup cleanup was deferred because the live journal could not be verified."
)
_SWEEP_PATH_SKIPPED_WARNING = (
    "Journal cleanup was skipped for a profile path that could not be verified."
)
_JOURNAL_BASENAME = "data.json"


class VaultPassphraseError(Exception):
    """Passphrase missing or incorrect — not file corruption."""


class PassphraseRequiredError(VaultPassphraseError):
    """Encrypted journal requires a passphrase."""


class WrongPassphraseError(VaultPassphraseError):
    """Decryption failed because the passphrase does not match."""


def _is_readable_plaintext_journal(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return isinstance(data, dict) and not data.get("integral_encrypted")
    except (json.JSONDecodeError, OSError, TypeError):
        return False


def encrypted_journal_envelope_path(data_path: str) -> str | None:
    """Return the path to an encrypted journal envelope (main file or .bak)."""
    if is_encrypted_file(data_path):
        return data_path
    if _is_readable_plaintext_journal(data_path):
        return None
    bak_path = f"{data_path}.bak"
    if is_encrypted_file(bak_path):
        return bak_path
    return None


def _logger():
    from integral_logging import get_logger

    return get_logger()


def save_temp_path(data_path: str) -> str:
    return f"{data_path}.tmp"


def _is_same_or_within(child: str, parent_dir: str) -> bool:
    """True when ``child`` resolves to ``parent_dir`` or a path inside it."""
    try:
        parent = os.path.normcase(os.path.realpath(parent_dir))
        target = os.path.normcase(os.path.realpath(child))
    except OSError:
        return False
    if target == parent:
        return True
    return target.startswith(parent + os.sep)


def _artifact_paths_for_journal(data_path: str) -> tuple[str, str, str]:
    return (data_path, save_temp_path(data_path), f"{data_path}.bak")


def _journal_artifacts_contained(data_path: str, container_dir: str) -> bool:
    if os.path.basename(data_path) != _JOURNAL_BASENAME:
        return False
    for artifact in _artifact_paths_for_journal(data_path):
        if os.path.lexists(artifact) and not _is_same_or_within(artifact, container_dir):
            return False
    if not _is_same_or_within(data_path, container_dir):
        return False
    temp_name = f"{_JOURNAL_BASENAME}.tmp"
    bak_name = f"{_JOURNAL_BASENAME}.bak"
    for artifact in _artifact_paths_for_journal(data_path):
        base = os.path.basename(artifact)
        if base not in (_JOURNAL_BASENAME, temp_name, bak_name):
            return False
    return True


def confirmed_live_journal_encrypted(data_path: str) -> bool | None:
    """Return the on-disk encryption mode when the primary journal is readable; else None."""
    if not os.path.isfile(data_path):
        return None
    if is_encrypted_file(data_path):
        return True
    if _is_readable_plaintext_journal(data_path):
        return False
    return None


def try_remove_leftover_save_temp(data_path: str, *, container_dir: str | None = None) -> bool:
    """Remove ``data.json.tmp`` in the same folder as ``data_path`` if present."""
    if container_dir is not None and not _journal_artifacts_contained(data_path, container_dir):
        _logger().warning(_SWEEP_PATH_SKIPPED_WARNING)
        return False
    temp_path = save_temp_path(data_path)
    if os.path.basename(temp_path) != f"{_JOURNAL_BASENAME}.tmp":
        return False
    if not os.path.exists(temp_path):
        return True
    try:
        os.remove(temp_path)
        return True
    except OSError:
        _logger().warning(_LEFTOVER_SAVE_TEMP_WARNING)
        return False


def _remove_mismatched_journal_backup(data_path: str, *, encrypted: bool) -> bool:
    """Delete ``data.json.bak`` only when its envelope format differs from the live journal."""
    bak_path = f"{data_path}.bak"
    if os.path.basename(bak_path) != f"{_JOURNAL_BASENAME}.bak":
        return False
    if not os.path.exists(bak_path):
        return True
    bak_encrypted = is_encrypted_file(bak_path)
    mismatch = (encrypted and not bak_encrypted) or (not encrypted and bak_encrypted)
    if not mismatch:
        return True
    try:
        os.remove(bak_path)
        return True
    except OSError:
        _logger().warning(_MISMATCHED_JOURNAL_BACKUP_WARNING)
        return False


def drop_opposite_format_journal_backup(path: str, *, encrypted: bool) -> None:
    """Remove a .bak that does not match the on-disk journal format after a successful save."""
    _remove_mismatched_journal_backup(path, encrypted=encrypted)


def drop_mismatched_journal_backup_after_journal_open(data_path: str) -> None:
    """Remove a format-mismatched .bak after the live journal has been opened."""
    with _save_lock:
        live_format = confirmed_live_journal_encrypted(data_path)
        if live_format is None:
            return
        _remove_mismatched_journal_backup(data_path, encrypted=live_format)


def _drop_mismatched_backups_on_validated_journal_paths() -> None:
    for data_path in _validated_journal_sweep_data_paths():
        live_format = confirmed_live_journal_encrypted(data_path)
        if live_format is None:
            continue
        _remove_mismatched_journal_backup(data_path, encrypted=live_format)


def drop_mismatched_journal_backups_after_journal_open() -> None:
    """Drop mismatched ``.bak`` files on every validated journal path after open."""
    with _save_lock:
        _drop_mismatched_backups_on_validated_journal_paths()


def retry_journal_save_artifact_cleanup(data_path: str) -> None:
    """Retry removing a leftover save temp for one journal path (pre-save only)."""
    try_remove_leftover_save_temp(data_path)


def iter_journal_sweep_targets(*, prepare_layout: bool = True) -> list[tuple[str, str]]:
    """Return ``(data.json path, owning profile directory)`` pairs for startup sweeps."""
    import paths
    import profiles

    if prepare_layout:
        profiles.ensure_app_structure()
    profiles_root = profiles.get_profiles_root()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    def _append(data_path: str, container_dir: str) -> None:
        key = os.path.normcase(os.path.normpath(data_path))
        if key in seen:
            return
        seen.add(key)
        out.append((data_path, container_dir))

    root_data = paths.data_file()
    root_container = os.path.dirname(root_data) or "."
    _append(root_data, root_container)

    if prepare_layout:
        profile_rows = profiles.list_profiles()
    else:
        profile_rows: list[dict[str, Any]] = []
        config_path = profiles.get_config_path()
        if os.path.isfile(config_path):
            try:
                with open(config_path, encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    raw_profiles = loaded.get("profiles")
                    if isinstance(raw_profiles, list):
                        profile_rows = [p for p in raw_profiles if isinstance(p, dict)]
            except (json.JSONDecodeError, OSError, TypeError):
                profile_rows = []

    for profile in profile_rows:
        try:
            profile_id = profiles.require_safe_profile_id(profile.get("id"))
        except ValueError:
            _logger().warning(_SWEEP_PATH_SKIPPED_WARNING)
            continue
        profile_dir = profiles.get_profile_dir(profile_id)
        if not _is_same_or_within(profile_dir, profiles_root):
            _logger().warning(_SWEEP_PATH_SKIPPED_WARNING)
            continue
        data_path = os.path.join(profile_dir, _JOURNAL_BASENAME)
        _append(data_path, profile_dir)
    return out


def _validated_journal_sweep_data_paths() -> list[str]:
    """Journal ``data.json`` paths that pass container validation (issue #275-style paths)."""
    paths_out: list[str] = []
    for data_path, container_dir in iter_journal_sweep_targets(prepare_layout=False):
        if _journal_artifacts_contained(data_path, container_dir):
            paths_out.append(data_path)
    return paths_out


def sweep_journal_save_artifacts_at_startup() -> None:
    """Remove leftover save temps before the first save (defer .bak cleanup until open)."""
    for data_path, container_dir in iter_journal_sweep_targets():
        if not _journal_artifacts_contained(data_path, container_dir):
            _logger().warning(_SWEEP_PATH_SKIPPED_WARNING)
            continue
        try_remove_leftover_save_temp(data_path, container_dir=container_dir)
        if confirmed_live_journal_encrypted(data_path) is None:
            bak_path = f"{data_path}.bak"
            if os.path.lexists(bak_path):
                _logger().warning(_STARTUP_DEFER_BACKUP_CLEANUP_WARNING)


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
        retry_journal_save_artifact_cleanup(path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if encrypted:
            if not passphrase:
                raise PassphraseRequiredError("Passphrase required to save encrypted journal.")
            salt = _existing_salt(path)
            to_write = encrypt_payload(payload, passphrase, salt=salt)
        else:
            to_write = payload
        
        temp_path = f"{path}.tmp"
        bak_path = f"{path}.bak"
        rotated = False
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(to_write, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())

            if os.path.exists(path):
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.replace(path, bak_path)
                rotated = True

            os.replace(temp_path, path)
            try_remove_leftover_save_temp(path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    _logger().warning(_LEFTOVER_SAVE_TEMP_WARNING)
            if rotated and os.path.exists(bak_path) and not os.path.exists(path):
                try:
                    os.replace(bak_path, path)
                except OSError:
                    pass
            raise
    with _save_lock:
        _drop_mismatched_backups_on_validated_journal_paths()
