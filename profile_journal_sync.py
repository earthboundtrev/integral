"""Keep tracker journal paths and per-profile data.json in sync for backup/export."""

from __future__ import annotations

import json
import os
import shutil
import sys

import profiles
import storage

GENERIC_PROFILE_SYNC_ERROR = (
    "Backup could not sync journal data safely. Try again or check the application log."
)


class ProfileJournalSyncError(Exception):
    """Active profile journal path failed safety checks."""


def _refuse_link(path: str) -> None:
    if not os.path.lexists(path):
        return
    if os.path.islink(path):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    if sys.platform == "win32":
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(path):
            raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)


def _data_root_real() -> str:
    app_dir = profiles.get_app_dir()
    if os.path.isdir(app_dir):
        return os.path.normcase(os.path.realpath(app_dir))
    return os.path.normcase(os.path.abspath(app_dir))


def _profiles_root_real(profiles_root: str) -> str:
    if os.path.isdir(profiles_root):
        return os.path.normcase(os.path.realpath(profiles_root))
    return os.path.normcase(os.path.abspath(profiles_root))


def _assert_contained(child: str, root_real: str) -> str:
    child_real = os.path.normcase(os.path.realpath(child))
    sep = os.path.normcase(os.sep)
    if child_real != root_real and not child_real.startswith(root_real + sep):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    return child_real


def _read_config_for_validation() -> dict:
    path = profiles.get_config_path()
    if not os.path.isfile(path):
        return profiles.default_config()
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    fallback = profiles.default_config()
    config.setdefault("active_profile_id", fallback["active_profile_id"])
    config.setdefault("profiles", fallback["profiles"])
    return config


def _validated_active_profile_id() -> str:
    config = _read_config_for_validation()
    active = config["active_profile_id"]
    try:
        safe_id = profiles.require_safe_profile_id(active)
    except ValueError as exc:
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR) from exc
    known = {p.get("id") for p in config.get("profiles") or []}
    if safe_id not in known:
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    return safe_id


def _validate_layout_before_io(safe_id: str) -> tuple[str, str, str]:
    """Validate id is already done; refuse links on every layout component; then containment."""
    app_dir = profiles.get_app_dir()
    profiles_root = profiles.get_profiles_root()
    profile_dir = os.path.join(profiles_root, safe_id)
    journal_path = os.path.join(profile_dir, storage.DATA_FILE_NAME)

    for component in (app_dir, profiles_root, profile_dir, journal_path):
        _refuse_link(component)

    app_real = _data_root_real()
    _assert_contained(profiles_root, app_real)
    _assert_contained(profile_dir, app_real)
    _assert_contained(journal_path, app_real)

    root_real = _profiles_root_real(profiles_root)
    _assert_contained(profile_dir, root_real)
    _assert_contained(journal_path, root_real)
    return profiles_root, profile_dir, journal_path


def _ensure_layout_after_validation(safe_id: str) -> tuple[str, str, str]:
    layout = _validate_layout_before_io(safe_id)
    profiles.ensure_app_structure()
    return _validate_layout_before_io(safe_id)


def resolved_active_profile_data_path() -> str:
    safe_id = _validated_active_profile_id()
    _profiles_root, _profile_dir, journal_path = _validate_layout_before_io(safe_id)
    return journal_path


def active_profile_journal_path() -> str:
    return resolved_active_profile_data_path()


def validate_layout_before_restore() -> None:
    """Refuse linked/invalid layout before restore snapshots or writes."""
    safe_id = _validated_active_profile_id()
    _validate_layout_before_io(safe_id)


def validated_active_profile_journal_path() -> str:
    """Profile journal path only when layout validation passes."""
    validate_layout_before_restore()
    safe_id = _validated_active_profile_id()
    return _validate_layout_before_io(safe_id)[2]


def active_profile_journal_path_for_rollback() -> str | None:
    """Validated profile journal path for rollback, or None when layout is unsafe."""
    try:
        return validated_active_profile_journal_path()
    except ProfileJournalSyncError:
        return None


def _same_file(path_a: str, path_b: str) -> bool:
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def _safe_copy(src: str, dest: str) -> None:
    safe_id = _validated_active_profile_id()
    _profiles_root, profile_dir, journal_path = _validate_layout_before_io(safe_id)
    if os.path.normcase(os.path.abspath(dest)) != os.path.normcase(os.path.abspath(journal_path)):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    _refuse_link(src)
    _profiles_root, profile_dir, journal_path = _ensure_layout_after_validation(safe_id)
    os.makedirs(profile_dir, exist_ok=True)
    _refuse_link(profile_dir)
    if os.path.lexists(journal_path):
        _refuse_link(journal_path)
    shutil.copy2(src, dest)


def sync_tracker_journal_to_active_profile(tracker_journal_path: str) -> None:
    """Copy the journal file the tracker saves into the active profile artifact path."""
    safe_id = _validated_active_profile_id()
    _profiles_root, _profile_dir, journal_path = _validate_layout_before_io(safe_id)
    dest = journal_path
    if _same_file(tracker_journal_path, dest):
        return
    if not os.path.isfile(tracker_journal_path):
        return
    _refuse_link(tracker_journal_path)
    _safe_copy(tracker_journal_path, dest)


def sync_active_profile_journal_to_tracker(tracker_journal_path: str) -> None:
    """After profile backup import, mirror restored profile data.json to the tracker path."""
    safe_id = _validated_active_profile_id()
    _validate_layout_before_io(safe_id)
    _profiles_root, _profile_dir, journal_path = _ensure_layout_after_validation(safe_id)
    src = journal_path
    if _same_file(src, tracker_journal_path):
        return
    if not os.path.isfile(src):
        return
    _refuse_link(src)
    tracker_dir = os.path.dirname(tracker_journal_path)
    os.makedirs(tracker_dir, exist_ok=True)
    shutil.copy2(src, tracker_journal_path)
