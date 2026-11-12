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


def _remove_empty_staging_parent(parent: str) -> None:
    if not os.path.isdir(parent) or any(os.scandir(parent)):
        return
    try:
        app_dir = profiles.get_app_dir()
        parent_real = os.path.normcase(os.path.realpath(parent))
        app_real = os.path.normcase(os.path.realpath(app_dir))
        sep = os.path.normcase(os.sep)
        if parent_real.startswith(app_real + sep):
            os.rmdir(parent)
    except OSError:
        pass


@contextmanager
def _backup_import_staging() -> Iterator[str]:
    """Stage backup extracts under the app data directory; always removed after use."""
    profiles.ensure_app_structure()
    parent = os.path.join(profiles.get_app_dir(), BACKUP_IMPORT_STAGING_DIRNAME)
    os.makedirs(parent, exist_ok=True)
    staging = os.path.join(parent, f"run-{os.getpid()}-{os.urandom(4).hex()}")
    os.makedirs(staging, exist_ok=True)
    try:
        yield staging
    finally:
        shutil.rmtree(staging, ignore_errors=True)
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
) -> dict:
    """Restore profiles and creative documents from a validated backup zip."""
    manifest = validate_backup(zip_path, passphrase=passphrase)
    profiles.ensure_app_structure()
    creative_dest = creative_root if creative_root is not None else paths.creative_projects_dir()

    with _backup_zipfile(zip_path, passphrase) as zf:
        budget = zip_import_safety.prepare_zip_import(zf)
        imported_config = json.loads(
            zip_import_safety.read_zip_member_bytes(zf, "config.json", budget).decode("utf-8")
        )

        with _backup_import_staging() as staging:
            staging_profiles = os.path.join(staging, "profiles")
            staging_creative = os.path.join(staging, CREATIVE_PREFIX.rstrip("/"))
            os.makedirs(staging_profiles, exist_ok=True)

            for pid in _manifest_profile_ids(manifest):
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

            restored_docs = _restore_creative_files(zf, staging_creative, budget)

            for pid in _manifest_profile_ids(manifest):
                _install_profile_artifacts(staging_profiles, pid)
            restored_docs = _install_creative_tree(staging_creative, creative_dest)

        manifest = {**manifest, "restored_creative_files": restored_docs}

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
