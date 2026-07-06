"""Profile and full-app backup export/import (zip archives)."""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime

import profiles
import storage

BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
PROFILE_ARTIFACTS = ("data.json", "fitness.db")


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


def export_backup(dest_path: str, profile_id: str | None = None) -> dict:
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
    }

    with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.json", json.dumps(config, indent=2, ensure_ascii=False))
        for pid in profile_ids:
            manifest["files"].extend(_write_profile_files(zf, pid))
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))

    return manifest


def validate_backup(zip_path: str) -> dict:
    """Verify backup structure. Raises ValueError if invalid."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("Backup missing manifest.json")
        if "config.json" not in names:
            raise ValueError("Backup missing config.json")

        manifest = json.loads(zf.read(MANIFEST_NAME))
        if manifest.get("backup_version") != BACKUP_VERSION:
            raise ValueError(f"Unsupported backup version: {manifest.get('backup_version')}")

        for pid in manifest.get("profiles", []):
            data_arc = f"profiles/{pid}/data.json"
            if data_arc not in names:
                raise ValueError(f"Backup missing required file: {data_arc}")

        return manifest


def import_backup(zip_path: str, merge_profiles: bool = True) -> dict:
    """Restore profiles from a validated backup zip."""
    manifest = validate_backup(zip_path)
    profiles.ensure_app_structure()

    with zipfile.ZipFile(zip_path, "r") as zf:
        imported_config = json.loads(zf.read("config.json"))

        for pid in manifest.get("profiles", []):
            dest_dir = profiles.get_profile_dir(pid)
            os.makedirs(dest_dir, exist_ok=True)
            prefix = f"profiles/{pid}/"
            for name in zf.namelist():
                if not name.startswith(prefix) or name.endswith("/"):
                    continue
                filename = name[len(prefix) :]
                if filename not in PROFILE_ARTIFACTS:
                    continue
                target = os.path.join(dest_dir, filename)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())

        if merge_profiles:
            current = profiles.load_config()
            existing_ids = {p["id"] for p in current["profiles"]}
            for profile in imported_config.get("profiles", []):
                if profile["id"] not in existing_ids:
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
