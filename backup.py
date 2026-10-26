"""Profile and full-app backup export/import (zip archives).

Includes profile artifacts (data.json, fitness.db) plus app-level creative/
document sidecars so Writing Projects manuscripts round-trip with the archive.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime

import paths
import profiles
import storage
import zip_import_safety

BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
PROFILE_ARTIFACTS = ("data.json", "fitness.db")
CREATIVE_PREFIX = "creative/"


def _manifest_profile_ids(manifest: dict) -> list[str]:
    raw = manifest.get("profiles", [])
    if not isinstance(raw, list):
        raise ValueError("Backup manifest profiles must be a list.")
    return [profiles.require_safe_profile_id(pid) for pid in raw]


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


def _restore_creative_files(
    zf: zipfile.ZipFile,
    creative_root: str,
    budget: zip_import_safety.ZipImportBudget,
) -> int:
    os.makedirs(creative_root, exist_ok=True)
    restored = 0
    for name in zf.namelist():
        normalized = name.replace("\\", "/")
        if not normalized.startswith(CREATIVE_PREFIX) or normalized.endswith("/"):
            continue
        rel = normalized[len(CREATIVE_PREFIX) :]
        if not rel or ".." in rel.split("/"):
            continue
        dest = os.path.join(creative_root, *rel.split("/"))
        zip_import_safety.copy_zip_member_to_file(zf, name, dest, budget)
        restored += 1
    return restored


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
            if not rel or ".." in rel.split("/"):
                continue
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
) -> dict:
    """Write a zip backup. One profile if profile_id set, else all profiles."""
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

    with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.json", json.dumps(config, indent=2, ensure_ascii=False))
        for pid in profile_ids:
            manifest["files"].extend(_write_profile_files(zf, pid))
        creative_files = _write_creative_files(zf, creative_root=creative_root)
        manifest["files"].extend(creative_files)
        manifest["creative_file_count"] = len(creative_files)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))

    return manifest


def validate_backup(zip_path: str) -> dict:
    """Verify backup structure. Raises ValueError if invalid."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        budget = zip_import_safety.prepare_zip_import(zf)
        names = set(zf.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("Backup missing manifest.json")
        if "config.json" not in names:
            raise ValueError("Backup missing config.json")

        manifest = json.loads(
            zip_import_safety.read_zip_member_bytes(zf, MANIFEST_NAME, budget).decode("utf-8")
        )
        if manifest.get("backup_version") != BACKUP_VERSION:
            raise ValueError(f"Unsupported backup version: {manifest.get('backup_version')}")

        for pid in _manifest_profile_ids(manifest):
            data_arc = f"profiles/{pid}/data.json"
            if data_arc not in names:
                raise ValueError(f"Backup missing required file: {data_arc}")

        return manifest


def import_backup(
    zip_path: str,
    merge_profiles: bool = True,
    *,
    creative_root: str | None = None,
) -> dict:
    """Restore profiles and creative documents from a validated backup zip."""
    manifest = validate_backup(zip_path)
    profiles.ensure_app_structure()
    creative_dest = creative_root if creative_root is not None else paths.creative_projects_dir()

    with zipfile.ZipFile(zip_path, "r") as zf:
        budget = zip_import_safety.prepare_zip_import(zf)
        imported_config = json.loads(
            zip_import_safety.read_zip_member_bytes(zf, "config.json", budget).decode("utf-8")
        )

        with tempfile.TemporaryDirectory() as staging:
            staging_profiles = os.path.join(staging, "profiles")
            staging_creative = os.path.join(staging, CREATIVE_PREFIX.rstrip("/"))
            os.makedirs(staging_profiles, exist_ok=True)

            for pid in _manifest_profile_ids(manifest):
                prefix = f"profiles/{pid}/"
                staged_profile = os.path.join(staging_profiles, pid)
                os.makedirs(staged_profile, exist_ok=True)
                for name in zf.namelist():
                    if not name.startswith(prefix) or name.endswith("/"):
                        continue
                    filename = name[len(prefix) :]
                    if filename not in PROFILE_ARTIFACTS:
                        continue
                    target = os.path.join(staged_profile, filename)
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


def list_backup_contents(zip_path: str) -> dict:
    """Human-readable summary of a backup file."""
    manifest = validate_backup(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        return {
            "manifest": manifest,
            "files": sorted(zf.namelist()),
        }
