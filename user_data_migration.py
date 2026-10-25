"""One-time safe copy of user data from legacy app folders into the canonical store.

Never moves or deletes source data. Never overwrites an existing destination file.
Idempotent: safe to run on every launch.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import paths

STATE_FILE_NAME = "folder_migration.json"
_STATE_VERSION = 1
_startup_lock = False
_user_notices: list[str] = []


@dataclass
class MigrationResult:
    outcome: str  # none | copied | merged | skipped | conflict
    source: str | None = None
    files_copied: int = 0
    conflicts: list[str] = field(default_factory=list)
    message: str | None = None


def consume_user_notices() -> list[str]:
    """Return and clear UI messages from the last migration run."""
    global _user_notices
    notes = list(_user_notices)
    _user_notices.clear()
    return notes


def _state_path(canonical: str) -> str:
    return os.path.join(canonical, STATE_FILE_NAME)


def _load_state(canonical: str) -> dict[str, Any]:
    path = _state_path(canonical)
    if not os.path.isfile(path):
        return {"version": _STATE_VERSION, "sources": {}}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"version": _STATE_VERSION, "sources": {}}
    if not isinstance(data, dict):
        return {"version": _STATE_VERSION, "sources": {}}
    data.setdefault("version", _STATE_VERSION)
    data.setdefault("sources", {})
    return data


def _save_state(canonical: str, state: dict[str, Any]) -> None:
    os.makedirs(canonical, exist_ok=True)
    path = _state_path(canonical)
    temp = f"{path}.tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def legacy_user_data_directories() -> list[str]:
    """Known prior user-data roots (excluding the canonical dir)."""
    home = os.path.expanduser("~")
    candidates: list[str] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", home)
        candidates.append(os.path.join(appdata, "personal_dev_tracker"))
    candidates.append(os.path.join(home, ".personal_dev_tracker"))

    if not paths.is_frozen():
        repo_data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if os.path.isdir(repo_data):
            candidates.append(repo_data)

    canonical = os.path.normcase(os.path.normpath(paths.user_data_dir()))
    unique: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        norm = os.path.normcase(os.path.normpath(raw))
        if norm == canonical or norm in seen:
            continue
        seen.add(norm)
        unique.append(raw)
    return unique


def _payload_has_user_data(data: dict[str, Any]) -> bool:
    if data.get("entries") or data.get("sessions"):
        return True
    journal = data.get("journal")
    if isinstance(journal, dict) and journal.get("entries"):
        return True
    todos = data.get("todos")
    if isinstance(todos, dict) and todos.get("items"):
        return True
    if data.get("day_plans"):
        return True
    practices = data.get("practices")
    if isinstance(practices, dict) and practices.get("items"):
        return True
    creative = data.get("creative_projects")
    if isinstance(creative, dict) and creative.get("projects"):
        return True
    youtube = data.get("youtube_history")
    if isinstance(youtube, dict) and youtube.get("items"):
        return True
    settings = data.get("settings")
    if isinstance(settings, dict) and settings.get("onboarding_complete"):
        return True
    return False


def _data_json_is_empty_placeholder(path: str) -> bool:
    """True when data.json is a fresh-install stub (safe to sideline, not real history)."""
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("integral_encrypted"):
        return False
    if _payload_has_user_data(data):
        return False
    return True


def _replace_placeholder_data_json(src_file: str, dest_file: str) -> bool:
    """Copy src over a placeholder dest without leaving dest missing if copy fails."""
    if os.path.basename(dest_file) != "data.json":
        return False
    if not _data_json_is_empty_placeholder(dest_file):
        return False
    from integral_io import atomic_copy_file

    temp = f"{dest_file}.migration-incoming.tmp"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    preserved = f"{dest_file}.preserved-before-migration-{stamp}"
    try:
        atomic_copy_file(src_file, temp)
        os.replace(dest_file, preserved)
        os.replace(temp, dest_file)
        return True
    except OSError:
        if os.path.exists(temp):
            try:
                os.remove(temp)
            except OSError:
                pass
        return False


def _file_digest(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _path_has_user_artifacts(root: str) -> bool:
    if not root or not os.path.isdir(root):
        return False
    markers = (
        "config.json",
        "data.json",
        "fitness.db",
        STATE_FILE_NAME,
    )
    for name in markers:
        if os.path.isfile(os.path.join(root, name)):
            return True
    profiles = os.path.join(root, "profiles")
    if os.path.isdir(profiles):
        for _dirpath, _dirnames, filenames in os.walk(profiles):
            for name in filenames:
                lower = name.lower()
                if lower == "data.json" or lower == "fitness.db" or lower.endswith(".bak"):
                    return True
                if lower.endswith(".zip") and "integral" in lower:
                    return True
    creative = os.path.join(root, "creative")
    if os.path.isdir(creative):
        for _dirpath, _dirnames, filenames in os.walk(creative):
            if filenames:
                return True
    try:
        for name in os.listdir(root):
            if ".migration_backup_" in name:
                return True
            if name.endswith(".zip") and "integral" in name.lower():
                return True
    except OSError:
        return False
    return False


def _resolve_dest_under_root(dest_root: str, *rel_parts: str) -> str | None:
    dest_root_real = os.path.realpath(dest_root)
    joined = os.path.join(dest_root, *rel_parts)
    dest_real = os.path.realpath(os.path.normpath(joined))
    if dest_real != dest_root_real and not dest_real.startswith(dest_root_real + os.sep):
        return None
    return dest_real


def _copy_file_if_absent(src_file: str, dest_file: str, conflicts: list[str]) -> bool:
    if os.path.exists(dest_file):
        if _file_digest(src_file) == _file_digest(dest_file):
            return False
        if _replace_placeholder_data_json(src_file, dest_file):
            return True
        conflicts.append(dest_file)
        return False
    os.makedirs(os.path.dirname(dest_file) or ".", exist_ok=True)
    from integral_io import atomic_copy_file

    atomic_copy_file(src_file, dest_file)
    return True


def _copy_tree_non_destructive(src_root: str, dest_root: str) -> tuple[int, list[str]]:
    copied = 0
    conflicts: list[str] = []
    src_root = os.path.normpath(src_root)
    dest_root = os.path.normpath(dest_root)
    for dirpath, _dirnames, filenames in os.walk(src_root, followlinks=False):
        rel = os.path.relpath(dirpath, src_root)
        if rel != "." and (rel.startswith("..") or os.path.isabs(rel)):
            continue
        rel_parts = () if rel == "." else tuple(rel.split(os.sep))
        dest_dir = _resolve_dest_under_root(dest_root, *rel_parts)
        if dest_dir is None:
            continue
        os.makedirs(dest_dir, exist_ok=True)
        for name in filenames:
            if name == STATE_FILE_NAME and dirpath == src_root:
                continue
            src_file = os.path.join(dirpath, name)
            if os.path.islink(src_file):
                continue
            dest_file = _resolve_dest_under_root(dest_root, *rel_parts, name)
            if dest_file is None:
                continue
            if _copy_file_if_absent(src_file, dest_file, conflicts):
                copied += 1
    return copied, conflicts


def _record_source(
    state: dict[str, Any],
    source: str,
    outcome: str,
    files_copied: int,
    conflicts: list[str],
) -> None:
    state["sources"][source] = {
        "outcome": outcome,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_copied": files_copied,
        "conflicts": conflicts,
    }


def _migrate_from_source(canonical: str, source: str, state: dict[str, Any]) -> MigrationResult:
    source = os.path.normpath(source)
    prior = state.get("sources", {}).get(source)
    if prior and prior.get("outcome") in ("copied", "merged"):
        return MigrationResult(outcome="none", source=source)

    if not os.path.isdir(source):
        _record_source(state, source, "skipped_missing", 0, [])
        return MigrationResult(outcome="skipped", source=source)

    if not _path_has_user_artifacts(source):
        _record_source(state, source, "skipped_empty", 0, [])
        return MigrationResult(outcome="skipped", source=source)

    dest_has = _path_has_user_artifacts(canonical)
    try:
        copied, conflicts = _copy_tree_non_destructive(source, canonical)
    except OSError:
        return MigrationResult(outcome="skipped", source=source, message=None)

    if not dest_has and copied > 0 and not conflicts:
        outcome = "copied"
        message = (
            f"Your existing data was copied from {source} into {canonical}. "
            "The original folder was left unchanged."
        )
    elif copied > 0 and conflicts:
        outcome = "merged"
        message = (
            f"Some files were copied from {source} into {canonical}. "
            f"{len(conflicts)} file(s) already existed and were not changed. "
            f"Your original data remains at {source}."
        )
    elif dest_has and not copied and conflicts:
        outcome = "conflict"
        message = (
            f"Data exists in both {canonical} and {source}. "
            "Nothing was overwritten. Open Settings → Backup to export or merge manually."
        )
    elif dest_has and copied == 0 and not conflicts:
        outcome = "none"
        message = None
    elif copied > 0:
        outcome = "merged"
        message = (
            f"Copied {copied} file(s) from {source} into {canonical}. "
            "The original folder was left unchanged."
        )
    else:
        outcome = "none"
        message = None

    recorded = outcome if outcome != "none" else "skipped_empty"
    if copied == 0 and not conflicts and dest_has and prior is None:
        recorded = "identical"
    _record_source(state, source, recorded, copied, conflicts)
    return MigrationResult(
        outcome=outcome,
        source=source,
        files_copied=copied,
        conflicts=conflicts,
        message=message,
    )


def run_at_startup() -> list[MigrationResult]:
    """Run folder migration once per process before profile layout setup."""
    global _startup_lock, _user_notices
    if _startup_lock:
        return []
    _startup_lock = True

    canonical = paths.user_data_dir()
    os.makedirs(canonical, exist_ok=True)
    state = _load_state(canonical)
    results: list[MigrationResult] = []

    for legacy in legacy_user_data_directories():
        result = _migrate_from_source(canonical, legacy, state)
        if result.message:
            _user_notices.append(result.message)
        if result.outcome not in ("none", "skipped"):
            results.append(result)

    _save_state(canonical, state)
    return results
