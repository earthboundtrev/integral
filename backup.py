"""Profile and full-app backup export/import (zip archives).

Includes profile artifacts (data.json, fitness.db) plus app-level creative/
document sidecars so Writing Projects manuscripts round-trip with the archive.

Optional passphrase encryption writes a non-zip container (magic header + Fernet
ciphertext). Plain zip backups are unchanged for backward compatibility.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import struct
import tempfile
import unicodedata
import zipfile
from contextlib import contextmanager
from datetime import datetime
from dataclasses import dataclass, field
from typing import Iterator

import paths
import profiles
import storage
import zip_import_safety

from vault import CRYPTO_AVAILABLE, PassphraseRequiredError, WrongPassphraseError

if CRYPTO_AVAILABLE:
    import base64

    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
else:
    InvalidToken = None  # type: ignore[misc, assignment]
    Fernet = None  # type: ignore[misc, assignment]

BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
PROFILE_ARTIFACTS = ("data.json", "fitness.db")
CREATIVE_PREFIX = "creative/"

ENCRYPTED_BACKUP_MAGIC = b"INTGRBAK"
ENCRYPTED_BACKUP_FORMAT_VERSION = 1
ENCRYPTED_BACKUP_KDF_ITERATIONS = 600_000
ENCRYPTED_BACKUP_KDF_ITERATIONS_MIN = 600_000
ENCRYPTED_BACKUP_KDF_ITERATIONS_MAX = 2_000_000
ENCRYPTED_BACKUP_SALT_BYTES = 16
ENCRYPTED_BACKUP_MAX_CONTAINER_BYTES = 512 * 1024 * 1024
ENCRYPTED_BACKUP_DEFAULT_SUFFIX = ".integral-backup.enc"
BACKUP_IMPORT_STAGING_DIRNAME = ".backup-import-staging"
BACKUP_REPLACE_ASIDE_DIRNAME = ".backup-replace-aside"
REPLACE_PENDING_MARKER_BASENAME = ".backup-replace-pending.json"
REPLACE_LEDGER_STATE_FILENAME = "ledger-state.json"
REPLACE_CONFIG_BEFORE_FILENAME = "config-before.json"
REPLACE_LEDGER_MANIFEST_KEY = "_replace_aside_ledger"
_REPLACE_MARKER_VERSION = 1
_REPLACE_TEST_HOOK: str | None = None
_REPLACE_TEST_INSTALL_COUNT = 0


def _replace_test_hook(name: str) -> None:
    global _REPLACE_TEST_HOOK
    if _REPLACE_TEST_HOOK == name:
        raise OSError(f"replace-test-hook:{name}")


def normalize_backup_passphrase(passphrase: str) -> str:
    """Normalize passphrase for stable UTF-8 key derivation (NFC)."""
    return unicodedata.normalize("NFC", passphrase)


def is_encrypted_backup_file(path: str) -> bool:
    """True when the file begins with the encrypted backup magic (not a zip)."""
    return is_encrypted_backup_blob(_read_file_prefix(path, len(ENCRYPTED_BACKUP_MAGIC)))


def is_encrypted_backup_blob(prefix: bytes) -> bool:
    return len(prefix) >= len(ENCRYPTED_BACKUP_MAGIC) and prefix[: len(ENCRYPTED_BACKUP_MAGIC)] == ENCRYPTED_BACKUP_MAGIC


def _read_file_prefix(path: str, nbytes: int) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(nbytes)
    except OSError:
        return b""


def _require_crypto() -> None:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("Install cryptography: pip install cryptography")


def _coerce_kdf_iterations(iterations: int) -> int:
    if iterations < ENCRYPTED_BACKUP_KDF_ITERATIONS_MIN:
        raise ValueError("Encrypted backup uses unsupported KDF parameters.")
    if iterations > ENCRYPTED_BACKUP_KDF_ITERATIONS_MAX:
        raise ValueError("Encrypted backup uses unsupported KDF parameters.")
    return iterations


def _derive_backup_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    _require_crypto()
    iterations = _coerce_kdf_iterations(iterations)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _pack_encrypted_backup(zip_bytes: bytes, passphrase: str) -> bytes:
    _require_crypto()
    salt = os.urandom(ENCRYPTED_BACKUP_SALT_BYTES)
    iterations = ENCRYPTED_BACKUP_KDF_ITERATIONS
    key = _derive_backup_key(passphrase, salt, iterations)
    token = Fernet(key).encrypt(zip_bytes)
    header = b"".join(
        [
            ENCRYPTED_BACKUP_MAGIC,
            bytes([ENCRYPTED_BACKUP_FORMAT_VERSION]),
            struct.pack(">I", ENCRYPTED_BACKUP_KDF_ITERATIONS),
            bytes([len(salt)]),
            salt,
            struct.pack(">Q", len(token)),
        ]
    )
    return header + token


def _unpack_encrypted_backup(data: bytes, passphrase: str) -> bytes:
    _require_crypto()
    header_floor = len(ENCRYPTED_BACKUP_MAGIC) + 1 + 4 + 1 + 1 + 8
    if len(data) < header_floor:
        raise ValueError("Not a valid Integral backup file.")
    if data[: len(ENCRYPTED_BACKUP_MAGIC)] != ENCRYPTED_BACKUP_MAGIC:
        raise ValueError("Not a valid Integral backup file.")
    pos = len(ENCRYPTED_BACKUP_MAGIC)
    if data[pos] != ENCRYPTED_BACKUP_FORMAT_VERSION:
        raise ValueError(f"Unsupported encrypted backup version: {data[pos]}")
    pos += 1
    (iterations,) = struct.unpack_from(">I", data, pos)
    pos += 4
    salt_len = data[pos]
    pos += 1
    if salt_len <= 0 or salt_len > 64:
        raise ValueError("Encrypted backup header is invalid.")
    if pos + salt_len + 8 > len(data):
        raise ValueError("Encrypted backup header is invalid.")
    salt = data[pos : pos + salt_len]
    pos += salt_len
    (ct_len,) = struct.unpack_from(">Q", data, pos)
    pos += 8
    if ct_len <= 0 or pos + ct_len != len(data):
        raise ValueError("Encrypted backup header is invalid.")
    token = data[pos : pos + ct_len]
    key = _derive_backup_key(passphrase, salt, iterations)
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken:
        raise WrongPassphraseError("That passphrase didn't work for this backup.") from None


def _atomic_write_bytes(dest_path: str, payload: bytes) -> None:
    directory = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=directory,
        prefix=".integral-backup-",
        suffix=".partial",
    )
    closed = False
    try:
        with os.fdopen(fd, "wb") as handle:
            closed = True
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, dest_path)
    except Exception:
        if not closed:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _read_encrypted_backup_file(path: str, passphrase: str) -> bytes:
    size = os.path.getsize(path)
    if size > ENCRYPTED_BACKUP_MAX_CONTAINER_BYTES:
        raise ValueError("Encrypted backup file is too large to import safely.")
    with open(path, "rb") as handle:
        raw = handle.read(size + 1)
    if len(raw) > ENCRYPTED_BACKUP_MAX_CONTAINER_BYTES:
        raise ValueError("Encrypted backup file is too large to import safely.")
    return _unpack_encrypted_backup(raw, passphrase)


@contextmanager
def _backup_zipfile(path: str, passphrase: str | None = None) -> Iterator[zipfile.ZipFile]:
    if is_encrypted_backup_file(path):
        if passphrase is None:
            raise PassphraseRequiredError("Passphrase required for encrypted backup.")
        normalized = normalize_backup_passphrase(passphrase)
        if not normalized.strip():
            raise ValueError("Passphrase required for encrypted backup.")
        zip_bytes = _read_encrypted_backup_file(path, normalized)
        if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
            raise ValueError("Backup payload is not a valid zip archive.")
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    else:
        if passphrase is not None:
            normalized = normalize_backup_passphrase(passphrase)
            if normalized.strip():
                raise ValueError("Passphrase not accepted for an unencrypted backup.")
        zf = zipfile.ZipFile(path, "r")
    try:
        yield zf
    finally:
        zf.close()


def _validate_backup_zip_member(name: str) -> None:
    """Reject unsafe zip entry names before backup import."""
    normalized = name.replace("\\", "/")
    if ":" in normalized:
        raise ValueError(f"Backup archive contains an unsafe path: {name!r}")
    zip_import_safety.require_safe_zip_member_path(name)


def _staging_path_contained_in_app_dir(path: str) -> bool:
    try:
        app_dir = profiles.get_app_dir()
        path_real = os.path.normcase(os.path.realpath(path))
        app_real = os.path.normcase(os.path.realpath(app_dir))
        sep = os.path.normcase(os.sep)
        return path_real == app_real or path_real.startswith(app_real + sep)
    except OSError:
        return False


def _remove_import_staging_dir(staging: str) -> None:
    if not os.path.isdir(staging):
        return
    if not _staging_path_contained_in_app_dir(staging):
        return
    shutil.rmtree(staging, ignore_errors=True)


def _remove_empty_staging_parent(parent: str) -> None:
    if not os.path.isdir(parent) or any(os.scandir(parent)):
        return
    if not _staging_path_contained_in_app_dir(parent):
        return
    try:
        os.rmdir(parent)
    except OSError:
        pass


@contextmanager
def _backup_import_staging() -> Iterator[str]:
    """Stage backup extracts under the app data directory; always removed after use."""
    from profile_journal_sync import _refuse_link

    _refuse_link(profiles.get_app_dir())
    profiles.ensure_app_structure()
    parent = os.path.join(profiles.get_app_dir(), BACKUP_IMPORT_STAGING_DIRNAME)
    os.makedirs(parent, exist_ok=True)
    staging = os.path.join(parent, f"run-{os.getpid()}-{os.urandom(4).hex()}")
    os.makedirs(staging, exist_ok=True)
    try:
        yield staging
    finally:
        _remove_import_staging_dir(staging)
        _remove_empty_staging_parent(parent)


def _manifest_profile_ids(manifest: dict) -> list[str]:
    return profiles.validate_manifest_profile_ids(manifest)


def _write_profile_files(zf: zipfile.ZipFile, profile_id: str) -> list[str]:
    included: list[str] = []
    profile_dir = profiles.get_profile_dir(profile_id)
    data_path = os.path.join(profile_dir, storage.DATA_FILE_NAME)
    if os.path.exists(data_path):
        arcname = f"profiles/{profile_id}/{storage.DATA_FILE_NAME}"
        zf.write(data_path, arcname)
        included.append(arcname)
    else:
        arcname = f"profiles/{profile_id}/{storage.DATA_FILE_NAME}"
        zf.writestr(
            arcname,
            json.dumps(storage.empty_data(), indent=2, ensure_ascii=False),
        )
        included.append(arcname)

    fitness_path = os.path.join(profile_dir, "fitness.db")
    if os.path.exists(fitness_path):
        arcname = f"profiles/{profile_id}/fitness.db"
        zf.write(fitness_path, arcname)
        included.append(arcname)
    return included


def _write_creative_files(zf: zipfile.ZipFile, creative_root: str | None = None) -> list[str]:
    root = creative_root if creative_root is not None else paths.creative_projects_dir()
    if not root or not os.path.isdir(root):
        return []
    included: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, root).replace("\\", "/")
            if not rel or ".." in rel.split("/"):
                continue
            arcname = f"{CREATIVE_PREFIX}{rel}"
            zf.write(abs_path, arcname)
            included.append(arcname)
    return included


def _populate_backup_zip(
    zf: zipfile.ZipFile,
    *,
    profile_id: str | None,
    creative_root: str | None,
) -> dict:
    profiles.ensure_app_structure()
    config = profiles.load_config()
    profile_ids = [profile_id] if profile_id else [p["id"] for p in config["profiles"]]

    manifest = {
        "backup_version": BACKUP_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "profiles": profile_ids,
        "active_profile_id": config.get("active_profile_id"),
        "files": [],
        "creative_file_count": 0,
    }

    zf.writestr("config.json", json.dumps(config, indent=2, ensure_ascii=False))
    for pid in profile_ids:
        manifest["files"].extend(_write_profile_files(zf, pid))
    creative_files = _write_creative_files(zf, creative_root=creative_root)
    manifest["files"].extend(creative_files)
    manifest["creative_file_count"] = len(creative_files)
    zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def _restore_creative_files(
    zf: zipfile.ZipFile,
    creative_root: str,
    budget: zip_import_safety.ZipImportBudget,
) -> int:
    os.makedirs(creative_root, exist_ok=True)
    restored = 0
    for name in zf.namelist():
        _validate_backup_zip_member(name)
        normalized = name.replace("\\", "/")
        if not normalized.startswith(CREATIVE_PREFIX) or normalized.endswith("/"):
            continue
        rel = normalized[len(CREATIVE_PREFIX) :]
        dest = os.path.join(creative_root, *rel.split("/"))
        _assert_path_within_root(dest, creative_root)
        zip_import_safety.copy_zip_member_to_file(zf, name, dest, budget)
        restored += 1
    return restored


def _assert_path_within_root(dest_path: str, root: str) -> None:
    dest_real = os.path.normcase(os.path.realpath(dest_path))
    root_real = os.path.normcase(os.path.realpath(root))
    sep = os.path.normcase(os.sep)
    if dest_real != root_real and not dest_real.startswith(root_real + sep):
        raise ValueError("Backup archive contains an unsafe path.")


def _install_profile_artifacts(staging_profiles: str, profile_id: str) -> None:
    safe_id = profiles.require_safe_profile_id(profile_id)
    dest_dir = profiles.get_profile_dir(safe_id)
    os.makedirs(dest_dir, exist_ok=True)
    staged_dir = os.path.join(staging_profiles, safe_id)
    if not os.path.isdir(staged_dir):
        return
    for filename in PROFILE_ARTIFACTS:
        src = os.path.join(staged_dir, filename)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest_dir, filename))


@dataclass
class ReplaceAsideLedger:
    root: str
    config_before: dict | None = None
    ops: list[tuple[str, ...]] = field(default_factory=list)

    def record_aside(self, aside_path: str, live_path: str, *, is_dir: bool = False) -> None:
        self.ops.append(("aside", aside_path, live_path, "1" if is_dir else "0"))
        self._persist_state()

    def record_install(self, live_path: str) -> None:
        self.ops.append(("install", live_path))
        self._persist_state()

    def _persist_state(self) -> None:
        state_path = os.path.join(self.root, REPLACE_LEDGER_STATE_FILENAME)
        payload = {
            "version": _REPLACE_MARKER_VERSION,
            "ops": [list(op) for op in self.ops],
        }
        _ensure_parent_dir(state_path)
        temp = f"{state_path}.tmp-{os.getpid()}"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, state_path)
        if self.config_before is not None:
            snap = os.path.join(self.root, REPLACE_CONFIG_BEFORE_FILENAME)
            temp_cfg = f"{snap}.tmp-{os.getpid()}"
            with open(temp_cfg, "w", encoding="utf-8") as handle:
                json.dump(self.config_before, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_cfg, snap)

    def rollback(self) -> bool:
        """Best-effort rollback; returns True when fully restored, False if leftovers remain."""
        incomplete = False
        for op in reversed(self.ops):
            try:
                if op[0] == "install":
                    live_path = op[1]
                    if os.path.isfile(live_path):
                        os.remove(live_path)
                    elif os.path.isdir(live_path) and not os.path.islink(live_path):
                        try:
                            os.rmdir(live_path)
                        except OSError:
                            incomplete = True
                elif op[0] == "aside":
                    aside_path = op[1]
                    live_path = op[2]
                    is_dir = op[3] == "1"
                    _assert_path_within_root(aside_path, self.root)
                    if not os.path.lexists(aside_path):
                        continue
                    parent = os.path.dirname(live_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    if os.path.lexists(live_path):
                        if os.path.isfile(live_path):
                            os.remove(live_path)
                        elif os.path.isdir(live_path):
                            incomplete = True
                            continue
                    if is_dir:
                        os.replace(aside_path, live_path)
                    else:
                        os.replace(aside_path, live_path)
            except OSError:
                incomplete = True
        if self.config_before is not None:
            try:
                profiles.save_config(self.config_before)
            except OSError:
                incomplete = True
        if incomplete:
            _write_replace_pending_marker(self.root)
            return False
        return True

    def commit(self) -> None:
        if not _staging_path_contained_in_app_dir(self.root):
            raise OSError("Refusing to remove aside ledger outside app data directory.")
        _clear_replace_pending_marker()
        shutil.rmtree(self.root)


def _replace_pending_marker_path() -> str:
    return os.path.join(profiles.get_app_dir(), REPLACE_PENDING_MARKER_BASENAME)


def _write_replace_pending_marker(aside_root: str) -> None:
    marker_path = _replace_pending_marker_path()
    payload = {
        "version": _REPLACE_MARKER_VERSION,
        "aside_root": os.path.abspath(aside_root),
    }
    _ensure_parent_dir(marker_path)
    temp = f"{marker_path}.tmp-{os.getpid()}"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, marker_path)


def _clear_replace_pending_marker() -> None:
    marker_path = _replace_pending_marker_path()
    if os.path.lexists(marker_path):
        try:
            os.remove(marker_path)
        except OSError as exc:
            raise OSError(f"Could not clear replace pending marker: {marker_path!r}") from exc


def _load_ledger_from_aside_root(aside_root: str) -> ReplaceAsideLedger | None:
    state_path = os.path.join(aside_root, REPLACE_LEDGER_STATE_FILENAME)
    if not os.path.isfile(state_path):
        return None
    try:
        with open(state_path, encoding="utf-8") as handle:
            payload = json.load(handle)
        raw_ops = payload.get("ops")
        if not isinstance(raw_ops, list):
            return None
        ops = [tuple(str(item) for item in entry) for entry in raw_ops if isinstance(entry, list)]
        ledger = ReplaceAsideLedger(root=aside_root, ops=ops)
        cfg_path = os.path.join(aside_root, REPLACE_CONFIG_BEFORE_FILENAME)
        if os.path.isfile(cfg_path):
            with open(cfg_path, encoding="utf-8") as handle:
                ledger.config_before = json.load(handle)
        return ledger
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


def sweep_replace_aside_pending_at_startup() -> None:
    """Finish interrupted exact-replace imports using aside ledger state."""
    profiles.ensure_app_structure()
    app_dir = profiles.get_app_dir()
    marker_path = _replace_pending_marker_path()
    aside_roots: list[str] = []
    if os.path.isfile(marker_path):
        try:
            with open(marker_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            raw_root = payload.get("aside_root")
            if isinstance(raw_root, str) and raw_root.strip():
                aside_roots.append(os.path.abspath(raw_root.strip()))
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    parent = os.path.join(app_dir, BACKUP_REPLACE_ASIDE_DIRNAME)
    if os.path.isdir(parent):
        for name in os.listdir(parent):
            run_dir = os.path.join(parent, name)
            if os.path.isdir(run_dir) and run_dir not in aside_roots:
                state = os.path.join(run_dir, REPLACE_LEDGER_STATE_FILENAME)
                if os.path.isfile(state):
                    aside_roots.append(run_dir)
    seen: set[str] = set()
    for aside_root in aside_roots:
        norm = os.path.normcase(os.path.abspath(aside_root))
        if norm in seen or not _staging_path_contained_in_app_dir(aside_root):
            continue
        seen.add(norm)
        ledger = _load_ledger_from_aside_root(aside_root)
        if ledger is None:
            continue
        if ledger.rollback():
            try:
                shutil.rmtree(aside_root)
            except OSError:
                pass
            try:
                _clear_replace_pending_marker()
            except OSError:
                pass


def commit_replace_aside_ledger(ledger: ReplaceAsideLedger) -> None:
    ledger.commit()


def rollback_replace_aside_ledger(ledger: ReplaceAsideLedger | None) -> None:
    if ledger is None:
        return
    ledger.rollback()


def replace_import_recovery_pending() -> bool:
    return os.path.isfile(_replace_pending_marker_path())


def _create_replace_aside_ledger() -> ReplaceAsideLedger:
    profiles.ensure_app_structure()
    parent = os.path.join(profiles.get_app_dir(), BACKUP_REPLACE_ASIDE_DIRNAME)
    os.makedirs(parent, exist_ok=True)
    root = os.path.join(parent, f"run-{os.getpid()}-{os.urandom(4).hex()}")
    os.makedirs(root, exist_ok=True)
    if not _staging_path_contained_in_app_dir(root):
        raise OSError("Aside ledger path is outside the app data directory.")
    return ReplaceAsideLedger(root=root)


def _aside_path_for_key(ledger: ReplaceAsideLedger, key: str) -> str:
    normalized = key.replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        raise ValueError(f"Unsafe aside key: {key!r}")
    dest = os.path.join(ledger.root, *normalized.split("/"))
    _assert_path_within_root(dest, ledger.root)
    return dest


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _move_live_path_to_aside(
    live_path: str, aside_path: str, ledger: ReplaceAsideLedger, *, is_dir: bool = False
) -> None:
    _ensure_parent_dir(aside_path)
    if os.path.lexists(aside_path):
        raise OSError(f"Aside path already exists: {aside_path!r}")
    os.replace(live_path, aside_path)
    ledger.record_aside(aside_path, live_path, is_dir=is_dir)


def _atomic_install_staged_file(
    staged_src: str,
    dest: str,
    ledger: ReplaceAsideLedger,
    aside_key: str,
) -> None:
    if not os.path.isfile(staged_src):
        raise OSError(f"Staged file missing: {staged_src!r}")
    if os.path.lexists(dest):
        aside_path = _aside_path_for_key(ledger, aside_key)
        _move_live_path_to_aside(dest, aside_path, ledger)
    _ensure_parent_dir(dest)
    temp_path = f"{dest}.import-{os.getpid()}-{os.urandom(4).hex()}"
    shutil.copy2(staged_src, temp_path)
    try:
        os.replace(temp_path, dest)
    except OSError:
        if os.path.isfile(temp_path):
            os.remove(temp_path)
        raise
    ledger.record_install(dest)
    global _REPLACE_TEST_INSTALL_COUNT
    _REPLACE_TEST_INSTALL_COUNT += 1
    _replace_test_hook(f"install-{_REPLACE_TEST_INSTALL_COUNT}")


def _aside_config_profile_dirs(
    config_profile_ids: set[str],
    backup_profile_ids: set[str],
    ledger: ReplaceAsideLedger,
) -> None:
    removed_parent = os.path.join(ledger.root, "profiles-removed")
    os.makedirs(removed_parent, exist_ok=True)
    for pid in config_profile_ids - backup_profile_ids:
        safe_id = profiles.require_safe_profile_id(pid)
        profile_dir = profiles.get_profile_dir(safe_id)
        if not os.path.isdir(profile_dir):
            continue
        aside_path = os.path.join(removed_parent, safe_id)
        if os.path.lexists(aside_path):
            raise OSError(f"Aside profile path already exists: {aside_path!r}")
        os.replace(profile_dir, aside_path)
        ledger.record_aside(aside_path, profile_dir, is_dir=True)


def _staging_creative_relative_paths(staging_creative: str) -> set[str]:
    if not os.path.isdir(staging_creative):
        return set()
    rels: set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(staging_creative):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, staging_creative).replace("\\", "/")
            if rel and ".." not in rel.split("/"):
                rels.add(rel)
    return rels


def _aside_creative_orphans(
    creative_root: str,
    backup_rels: set[str],
    ledger: ReplaceAsideLedger,
) -> None:
    if not os.path.isdir(creative_root):
        return
    for dirpath, _dirnames, filenames in os.walk(creative_root):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, creative_root).replace("\\", "/")
            if not rel or ".." in rel.split("/"):
                continue
            if rel in backup_rels:
                continue
            aside_path = _aside_path_for_key(ledger, f"creative-removed/{rel}")
            _move_live_path_to_aside(abs_path, aside_path, ledger)


def _replace_profile_artifacts_from_staging(
    staging_profiles: str,
    profile_id: str,
    ledger: ReplaceAsideLedger,
) -> None:
    safe_id = profiles.require_safe_profile_id(profile_id)
    dest_dir = profiles.get_profile_dir(safe_id)
    os.makedirs(dest_dir, exist_ok=True)
    staged_dir = os.path.join(staging_profiles, safe_id)
    if not os.path.isdir(staged_dir):
        return
    for filename in PROFILE_ARTIFACTS:
        staged_src = os.path.join(staged_dir, filename)
        if not os.path.isfile(staged_src):
            continue
        dest = os.path.join(dest_dir, filename)
        aside_key = f"profiles-replaced/{safe_id}/{filename}"
        _atomic_install_staged_file(staged_src, dest, ledger, aside_key)


def _install_creative_tree_replace(
    staging_creative: str,
    creative_root: str,
    ledger: ReplaceAsideLedger,
) -> int:
    if not os.path.isdir(staging_creative):
        return 0
    installed = 0
    for dirpath, _dirnames, filenames in os.walk(staging_creative):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, staging_creative).replace("\\", "/")
            if not rel or ".." in rel.split("/"):
                continue
            dest = os.path.join(creative_root, *rel.split("/"))
            aside_key = f"creative-replaced/{rel}"
            _atomic_install_staged_file(abs_path, dest, ledger, aside_key)
            installed += 1
    return installed


def _atomic_replace_config(imported_config: dict, ledger: ReplaceAsideLedger) -> None:
    config_path = profiles.get_config_path()
    temp_path = f"{config_path}.import-{os.getpid()}-{os.urandom(4).hex()}"
    _ensure_parent_dir(config_path)
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(imported_config, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    if os.path.lexists(config_path):
        aside_path = _aside_path_for_key(ledger, "config-replaced/config.json")
        _move_live_path_to_aside(config_path, aside_path, ledger)
    os.replace(temp_path, config_path)
    ledger.record_install(config_path)


def _apply_replace_app_state(
    *,
    staging_profiles: str,
    staging_creative: str,
    creative_dest: str,
    backup_profile_ids: list[str],
    imported_config: dict,
) -> tuple[int, ReplaceAsideLedger]:
    config_before = profiles.load_config()
    ledger = _create_replace_aside_ledger()
    ledger.config_before = config_before
    ledger._persist_state()
    config_profile_ids = {
        profiles.require_safe_profile_id(p["id"])
        for p in config_before.get("profiles", [])
        if isinstance(p, dict)
    }
    backup_ids = {profiles.require_safe_profile_id(pid) for pid in backup_profile_ids}
    backup_creative_rels = _staging_creative_relative_paths(staging_creative)
    try:
        _aside_config_profile_dirs(config_profile_ids, backup_ids, ledger)
        _replace_test_hook("after-aside-profiles")
        _aside_creative_orphans(creative_dest, backup_creative_rels, ledger)
        _replace_test_hook("after-aside-creative")
        for pid in backup_profile_ids:
            _replace_profile_artifacts_from_staging(staging_profiles, pid, ledger)
        _replace_test_hook("after-profile-artifacts")
        restored_docs = _install_creative_tree_replace(staging_creative, creative_dest, ledger)
        _replace_test_hook("after-creative-install")
        _atomic_replace_config(imported_config, ledger)
        _replace_test_hook("after-config-replace")
    except Exception:
        ledger.rollback()
        raise
    return restored_docs, ledger


def _install_creative_tree(staging_creative: str, creative_root: str) -> int:
    if not os.path.isdir(staging_creative):
        return 0
    installed = 0
    for dirpath, _dirnames, filenames in os.walk(staging_creative):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, staging_creative).replace("\\", "/")
            dest = os.path.join(creative_root, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(abs_path, dest)
            installed += 1
    return installed


def export_backup(
    dest_path: str,
    profile_id: str | None = None,
    *,
    creative_root: str | None = None,
    passphrase: str | None = None,
) -> dict:
    """Write a zip backup. One profile if profile_id set, else all profiles.

    When ``passphrase`` is set, the zip is built in memory and written as an
    encrypted container (not readable as a zip file). No plaintext zip is left on disk.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = _populate_backup_zip(
            zf,
            profile_id=profile_id,
            creative_root=creative_root,
        )
    zip_bytes = buffer.getvalue()

    if passphrase is not None:
        normalized = normalize_backup_passphrase(passphrase)
        if not normalized.strip():
            raise ValueError("Passphrase required for encrypted backup.")
        payload = _pack_encrypted_backup(zip_bytes, normalized)
        _atomic_write_bytes(dest_path, payload)
        manifest = {**manifest, "encrypted": True}
    else:
        with open(dest_path, "wb") as handle:
            handle.write(zip_bytes)
        manifest = {**manifest, "encrypted": False}

    return manifest


def validate_backup(zip_path: str, *, passphrase: str | None = None) -> dict:
    """Verify backup structure. Raises ValueError if invalid."""
    with _backup_zipfile(zip_path, passphrase) as zf:
        budget = zip_import_safety.prepare_zip_import(zf)
        names = set(zf.namelist())
        for member in names:
            _validate_backup_zip_member(member)
        if MANIFEST_NAME not in names:
            raise ValueError("Backup missing manifest.json")
        if "config.json" not in names:
            raise ValueError("Backup missing config.json")

        manifest = json.loads(
            zip_import_safety.read_zip_member_bytes(zf, MANIFEST_NAME, budget).decode("utf-8")
        )
        if manifest.get("backup_version") != BACKUP_VERSION:
            raise ValueError(f"Unsupported backup version: {manifest.get('backup_version')}")

        profile_ids = _manifest_profile_ids(manifest)
        zip_import_safety.validate_profile_backup_namelist(
            list(names),
            profile_ids=profile_ids,
            profile_filenames=PROFILE_ARTIFACTS,
        )

        for pid in profile_ids:
            data_arc = f"profiles/{pid}/data.json"
            if data_arc not in names:
                raise ValueError(f"Backup missing required file: {data_arc}")

        return manifest


def import_backup(
    zip_path: str,
    merge_profiles: bool = True,
    *,
    creative_root: str | None = None,
    passphrase: str | None = None,
    replace_app_state: bool = False,
) -> dict:
    """Restore profiles and creative documents from a validated backup zip."""
    if replace_app_state and merge_profiles:
        raise ValueError("replace_app_state requires merge_profiles=False")
    manifest = validate_backup(zip_path, passphrase=passphrase)
    profiles.ensure_app_structure()
    creative_dest = creative_root if creative_root is not None else paths.creative_projects_dir()
    backup_profile_ids = _manifest_profile_ids(manifest)

    with _backup_zipfile(zip_path, passphrase) as zf:
        budget = zip_import_safety.prepare_zip_import(zf)
        imported_config = json.loads(
            zip_import_safety.read_zip_member_bytes(zf, "config.json", budget).decode("utf-8")
        )

        with _backup_import_staging() as staging:
            staging_profiles = os.path.join(staging, "profiles")
            staging_creative = os.path.join(staging, CREATIVE_PREFIX.rstrip("/"))
            os.makedirs(staging_profiles, exist_ok=True)

            for pid in backup_profile_ids:
                prefix = f"profiles/{pid}/"
                staged_profile = os.path.join(staging_profiles, pid)
                os.makedirs(staged_profile, exist_ok=True)
                for name in zf.namelist():
                    _validate_backup_zip_member(name)
                    if not name.startswith(prefix) or name.endswith("/"):
                        continue
                    filename = name[len(prefix) :]
                    if filename not in PROFILE_ARTIFACTS:
                        continue
                    target = os.path.join(staged_profile, filename)
                    _assert_path_within_root(target, staged_profile)
                    zip_import_safety.copy_zip_member_to_file(zf, name, target, budget)

            _restore_creative_files(zf, staging_creative, budget)

            replace_ledger: ReplaceAsideLedger | None = None
            if replace_app_state:
                restored_docs, replace_ledger = _apply_replace_app_state(
                    staging_profiles=staging_profiles,
                    staging_creative=staging_creative,
                    creative_dest=creative_dest,
                    backup_profile_ids=backup_profile_ids,
                    imported_config=imported_config,
                )
            else:
                for pid in backup_profile_ids:
                    _install_profile_artifacts(staging_profiles, pid)
                restored_docs = _install_creative_tree(staging_creative, creative_dest)

        manifest = {**manifest, "restored_creative_files": restored_docs}
        if replace_ledger is not None:
            manifest[REPLACE_LEDGER_MANIFEST_KEY] = replace_ledger

        if not replace_app_state:
            if merge_profiles:
                current = profiles.load_config()
                existing_ids = {p["id"] for p in current["profiles"]}
                for profile in imported_config.get("profiles", []):
                    if not isinstance(profile, dict):
                        continue
                    pid = profiles.require_safe_profile_id(profile.get("id"))
                    profile = {**profile, "id": pid}
                    if pid not in existing_ids:
                        current["profiles"].append(profile)
                profiles.save_config(current)
            else:
                profiles.save_config(imported_config)

    return manifest


def list_backup_contents(zip_path: str, *, passphrase: str | None = None) -> dict:
    """Human-readable summary of a backup file."""
    manifest = validate_backup(zip_path, passphrase=passphrase)
    with _backup_zipfile(zip_path, passphrase) as zf:
        return {
            "manifest": manifest,
            "files": sorted(zf.namelist()),
            "encrypted": is_encrypted_backup_file(zip_path),
        }
