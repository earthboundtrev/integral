"""Optional encryption at rest for Integral journal data."""

from __future__ import annotations

import base64
import json
import os
import threading
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
_save_lock = threading.Lock()


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


def load_data_file_with_recovery(
    path: str, 
    passphrase: str | None,
    *,
    on_recovery_prompt=None,
    on_both_corrupt_prompt=None
) -> dict[str, Any]:
    """Load data.json with automatic recovery from .bak or .tmp if corrupt/missing.
    
    Recovery cases:
    1. data.json missing but .bak or .tmp exists: prompt to restore
    2. data.json corrupt but .bak valid: prompt to restore from .bak
    3. Both corrupt: prompt to preserve both and start empty
    
    Args:
        path: Path to data.json
        passphrase: Vault passphrase if encrypted
        on_recovery_prompt: Callable(bak_path, bak_timestamp_str) -> bool
            Returns True to restore from backup, False to decline
        on_both_corrupt_prompt: Callable() -> bool
            Returns True to preserve corrupt files and start empty, False to decline
    
    Returns:
        Loaded data dict (or empty dict if starting fresh after decline)
        
    Raises:
        RuntimeError: If recovery is needed but user declined (not ValueError)
    """
    import logging
    import shutil
    from datetime import datetime
    
    main_exists = os.path.exists(path)
    main_data = None
    main_error = None
    
    # Try to load the main file if it exists
    if main_exists:
        try:
            return load_data_file(path, passphrase)
        except (json.JSONDecodeError, OSError, ValueError, PermissionError) as e:
            main_error = e
            logging.error(f"Failed to load {path}: {e}")
    else:
        logging.warning(f"Main file {path} is missing")
    
    # Main file missing or corrupt - try backup or temp
    bak_path = f"{path}.bak"
    tmp_path = f"{path}.tmp"
    bak_data = None
    bak_timestamp = None
    recovery_source = None
    
    # Try .bak first
    if os.path.exists(bak_path):
        try:
            bak_data = load_data_file(bak_path, passphrase)
            bak_stat = os.stat(bak_path)
            bak_timestamp = datetime.fromtimestamp(bak_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            recovery_source = bak_path
        except (json.JSONDecodeError, OSError, ValueError, PermissionError) as bak_e:
            logging.error(f"Backup {bak_path} is also corrupt: {bak_e}")
    
    # If no valid .bak but main is missing, try leftover .tmp
    if bak_data is None and not main_exists and os.path.exists(tmp_path):
        try:
            bak_data = load_data_file(tmp_path, passphrase)
            tmp_stat = os.stat(tmp_path)
            bak_timestamp = datetime.fromtimestamp(tmp_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            recovery_source = tmp_path
            logging.info(f"Found valid leftover temp file {tmp_path}")
        except (json.JSONDecodeError, OSError, ValueError, PermissionError) as tmp_e:
            logging.error(f"Temp file {tmp_path} is also corrupt: {tmp_e}")
    
    # If backup/tmp is valid, offer to restore
    if bak_data is not None:
        if on_recovery_prompt is None or on_recovery_prompt(recovery_source, bak_timestamp):
            # Preserve the corrupt main file before restoring (if it exists)
            if main_exists:
                timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]  # Include milliseconds
                corrupt_path = f"{path}.corrupt-{timestamp}"
                shutil.copy2(path, corrupt_path)
                logging.info(f"Preserved corrupt file as {corrupt_path}")
            
            # Restore backup atomically with save lock
            from integral_io import atomic_copy_file
            atomic_copy_file(recovery_source, path)
            logging.info(f"Restored from {recovery_source}")
            
            # Clean up .tmp if that was the source
            if recovery_source == tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            
            return bak_data
        else:
            # User declined recovery - preserve all files and raise to exit cleanly
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]  # Include milliseconds
            preserved = []
            data_dir = os.path.dirname(path) or "."
            
            # Helper to check if file already preserved with same content
            def already_preserved(target_pattern):
                import glob
                existing = glob.glob(target_pattern)
                if not existing:
                    return None
                # Check newest file with same content
                for exist_path in sorted(existing, reverse=True):
                    try:
                        if os.path.getsize(exist_path) == os.path.getsize(source_for_compare):
                            with open(exist_path, 'rb') as f1, open(source_for_compare, 'rb') as f2:
                                if f1.read() == f2.read():
                                    return exist_path
                    except OSError:
                        continue
                return None
            
            if main_exists:
                source_for_compare = path
                existing = already_preserved(f"{path}.corrupt-*")
                if existing:
                    declined_path = existing
                    logging.info(f"Using existing preserved copy: {declined_path}")
                else:
                    declined_path = f"{path}.corrupt-{timestamp}"
                    shutil.copy2(path, declined_path)
                    logging.info(f"Preserved declined main file as {declined_path}")
                preserved.append(declined_path)
            
            if os.path.exists(recovery_source):
                source_for_compare = recovery_source
                existing = already_preserved(f"{recovery_source}.declined-*")
                if existing:
                    declined_bak = existing
                    logging.info(f"Using existing preserved copy: {declined_bak}")
                else:
                    declined_bak = f"{recovery_source}.declined-{timestamp}"
                    shutil.copy2(recovery_source, declined_bak)
                    logging.info(f"Preserved good backup as {declined_bak}")
                preserved.append(declined_bak)
            
            if os.path.exists(tmp_path) and tmp_path != recovery_source:
                source_for_compare = tmp_path
                existing = already_preserved(f"{tmp_path}.declined-*")
                if existing:
                    declined_tmp = existing
                    logging.info(f"Using existing preserved copy: {declined_tmp}")
                else:
                    declined_tmp = f"{tmp_path}.declined-{timestamp}"
                    shutil.copy2(tmp_path, declined_tmp)
                    logging.info(f"Preserved temp file as {declined_tmp}")
                preserved.append(declined_tmp)
            
            # Build helpful message
            good_data_file = next((p for p in preserved if '.declined-' in p), preserved[0] if preserved else recovery_source)
            msg = (
                f"Your data is safe in: {os.path.basename(good_data_file)}\n\n"
                f"Data folder: {os.path.abspath(data_dir)}\n\n"
                f"To restore later:\n"
                f"1. Close this app\n"
                f"2. In the data folder, rename {os.path.basename(good_data_file)} to data.json\n"
                f"3. Restart the app"
            )
            
            # Raise to signal clean exit - do not continue with empty data
            raise RuntimeError(msg)
    
    # Both files corrupt or missing - offer to start empty
    if on_both_corrupt_prompt is None or on_both_corrupt_prompt():
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]  # Include milliseconds
        preserved = []
        
        # Preserve corrupt main file
        if main_exists:
            corrupt_path = f"{path}.corrupt-{timestamp}"
            shutil.copy2(path, corrupt_path)
            preserved.append(corrupt_path)
            logging.info(f"Preserved corrupt main file as {corrupt_path}")
        
        # Preserve corrupt backup file
        if os.path.exists(bak_path):
            bak_corrupt_path = f"{bak_path}.corrupt-{timestamp}"
            shutil.copy2(bak_path, bak_corrupt_path)
            preserved.append(bak_corrupt_path)
            logging.info(f"Preserved corrupt backup as {bak_corrupt_path}")
        
        # Preserve leftover .tmp if present
        if os.path.exists(tmp_path):
            tmp_corrupt_path = f"{tmp_path}.corrupt-{timestamp}"
            shutil.copy2(tmp_path, tmp_corrupt_path)
            preserved.append(tmp_corrupt_path)
            logging.info(f"Preserved temp file as {tmp_corrupt_path}")
        
        # Start with empty data
        logging.warning("Starting with empty data after corruption")
        return {}
    else:
        # User declined - preserve all files and raise to exit cleanly
        import glob
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]  # Include milliseconds
        preserved = []
        data_dir = os.path.dirname(path) or "."
        
        # Helper to check if file already preserved with same content
        def file_already_preserved(source_path, pattern):
            if not os.path.exists(source_path):
                return None
            existing = glob.glob(pattern)
            for exist_path in sorted(existing, reverse=True):
                try:
                    if os.path.getsize(exist_path) == os.path.getsize(source_path):
                        with open(exist_path, 'rb') as f1, open(source_path, 'rb') as f2:
                            if f1.read() == f2.read():
                                return exist_path
                except OSError:
                    continue
            return None
        
        if main_exists:
            existing = file_already_preserved(path, f"{path}.corrupt-*")
            if existing:
                declined_path = existing
                logging.info(f"Using existing preserved copy: {declined_path}")
            else:
                declined_path = f"{path}.corrupt-{timestamp}"
                shutil.copy2(path, declined_path)
                logging.info(f"Preserved declined main file as {declined_path}")
            preserved.append(declined_path)
        
        if os.path.exists(bak_path):
            existing = file_already_preserved(bak_path, f"{bak_path}.declined-*")
            if existing:
                declined_bak = existing
                logging.info(f"Using existing preserved copy: {declined_bak}")
            else:
                declined_bak = f"{bak_path}.declined-{timestamp}"
                shutil.copy2(bak_path, declined_bak)
                logging.info(f"Preserved backup as {declined_bak}")
            preserved.append(declined_bak)
        
        if os.path.exists(tmp_path):
            existing = file_already_preserved(tmp_path, f"{tmp_path}.declined-*")
            if existing:
                declined_tmp = existing
                logging.info(f"Using existing preserved copy: {declined_tmp}")
            else:
                declined_tmp = f"{tmp_path}.declined-{timestamp}"
                shutil.copy2(tmp_path, declined_tmp)
                logging.info(f"Preserved temp file as {declined_tmp}")
            preserved.append(declined_tmp)
        
        # Build helpful message - if all files corrupt, no single "good" file
        msg = (
            f"All files appear damaged. Preserved copies:\n"
            f"{chr(10).join('  ' + os.path.basename(p) for p in preserved)}\n\n"
            f"Data folder: {os.path.abspath(data_dir)}\n\n"
            f"To attempt manual recovery, inspect these files and rename "
            f"the best one to data.json, then restart."
        )
        
        # Raise to signal clean exit - do not continue with empty data
        raise RuntimeError(msg)



def save_data_file(path: str, payload: dict[str, Any], *, encrypted: bool, passphrase: str | None) -> None:
    """Atomically save data.json with backup rotation.
    
    Write to temp file, fsync, then os.replace. Before replacing, copy the
    current good data.json to data.json.bak (never leave main file missing).
    Use a lock to serialize saves. Handle Windows file-locking with retry.
    """
    import logging
    import shutil
    import time
    
    with _save_lock:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if encrypted:
            if not passphrase:
                raise PermissionError("Passphrase required to save encrypted journal.")
            salt = _existing_salt(path)
            to_write = encrypt_payload(payload, passphrase, salt=salt)
        else:
            to_write = payload
        
        # Serialize to JSON string under lock (safe snapshot before threading)
        json_str = json.dumps(to_write, indent=2, ensure_ascii=False)
        
        # Write to temp file in same directory with retry for PermissionError
        temp_path = f"{path}.tmp"
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries + 1):
            try:
                with open(temp_path, "w", encoding="utf-8") as handle:
                    handle.write(json_str)
                    handle.flush()
                    os.fsync(handle.fileno())
                break
            except PermissionError as e:
                if attempt < max_retries:
                    logging.warning(f"PermissionError writing {temp_path}, retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    # Clean up temp file on final failure
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except OSError:
                        pass
                    raise RuntimeError(f"Failed to write {temp_path} after {max_retries} retries: {e}")
        
        # Copy current good file to backup (never leave main file missing)
        # Validate main file is parseable before rotating to backup
        bak_path = f"{path}.bak"
        if os.path.exists(path):
            # Validate existing file before copying to backup
            # Use same loader that respects encryption
            try:
                existing_data = load_data_file(path, passphrase)
                # File is valid (decrypted if needed), safe to rotate to backup
                for attempt in range(max_retries + 1):
                    try:
                        shutil.copy2(path, bak_path)
                        break
                    except PermissionError as e:
                        if attempt < max_retries:
                            logging.warning(f"PermissionError copying to {bak_path}, retry {attempt + 1}/{max_retries}")
                            time.sleep(retry_delay * (2 ** attempt))
                        else:
                            # Log but continue - backup rotation failure shouldn't block save
                            logging.error(f"Failed to create backup after {max_retries} retries: {e}")
            except (json.JSONDecodeError, OSError, ValueError, PermissionError) as e:
                # Existing main file is corrupt or wrong passphrase - do NOT copy to backup
                logging.warning(f"Skipping backup rotation: existing {path} is invalid ({e})")
                # Preserve the corrupt file before overwriting (with milliseconds for uniqueness)
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]  # Include milliseconds
                corrupt_path = f"{path}.corrupt-{timestamp}"
                try:
                    shutil.copy2(path, corrupt_path)
                    logging.info(f"Preserved corrupt file as {corrupt_path}")
                except OSError:
                    pass
        
        # Atomic replace temp with real file with retry
        for attempt in range(max_retries + 1):
            try:
                os.replace(temp_path, path)
                break
            except PermissionError as e:
                if attempt < max_retries:
                    logging.warning(f"PermissionError replacing {path}, retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    raise RuntimeError(f"Failed to replace {path} after {max_retries} retries: {e}")
