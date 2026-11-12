"""Keep tracker journal paths and per-profile data.json in sync for backup/export."""

from __future__ import annotations

import os
import shutil

import profiles
import storage

GENERIC_PROFILE_SYNC_ERROR = (
    "Backup could not sync journal data safely. Try again or check the application log."
)


class ProfileJournalSyncError(Exception):
    """Active profile journal path failed safety checks."""


def _profiles_root_real() -> str:
    profiles.ensure_app_structure()
    return os.path.normcase(os.path.realpath(profiles.get_profiles_root()))


def _assert_contained(child: str, root_real: str) -> str:
    child_real = os.path.normcase(os.path.realpath(child))
    sep = os.path.normcase(os.sep)
    if child_real != root_real and not child_real.startswith(root_real + sep):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    return child_real


def _refuse_symlink(path: str) -> None:
    if os.path.islink(path):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)


def _validated_active_profile_id() -> str:
    active = profiles.get_active_profile_id()
    try:
        safe_id = profiles.require_safe_profile_id(active)
    except ValueError as exc:
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR) from exc
    config = profiles.load_config()
    known = {p.get("id") for p in config.get("profiles") or []}
    if safe_id not in known:
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    return safe_id


def resolved_active_profile_data_path() -> str:
    """Active profile data.json path after id validation and containment checks."""
    safe_id = _validated_active_profile_id()
    profiles_root = profiles.get_profiles_root()
    profile_dir = os.path.join(profiles_root, safe_id)
    _refuse_symlink(profiles_root)
    _refuse_symlink(profile_dir)
    journal_path = os.path.join(profile_dir, storage.DATA_FILE_NAME)
    root_real = _profiles_root_real()
    _assert_contained(profile_dir, root_real)
    _assert_contained(journal_path, root_real)
    if os.path.lexists(journal_path):
        _refuse_symlink(journal_path)
    return journal_path


def active_profile_journal_path() -> str:
    return resolved_active_profile_data_path()


def _same_file(path_a: str, path_b: str) -> bool:
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def _safe_copy(src: str, dest: str) -> None:
    dest_dir = os.path.dirname(dest)
    root_real = _profiles_root_real()
    _assert_contained(dest, root_real)
    _refuse_symlink(dest_dir)
    if os.path.lexists(dest):
        _refuse_symlink(dest)
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src, dest)


def sync_tracker_journal_to_active_profile(tracker_journal_path: str) -> None:
    """Copy the journal file the tracker saves into the active profile artifact path."""
    dest = resolved_active_profile_data_path()
    if _same_file(tracker_journal_path, dest):
        return
    if not os.path.isfile(tracker_journal_path):
        return
    _refuse_symlink(tracker_journal_path)
    _safe_copy(tracker_journal_path, dest)


def sync_active_profile_journal_to_tracker(tracker_journal_path: str) -> None:
    """After profile backup import, mirror restored profile data.json to the tracker path."""
    src = resolved_active_profile_data_path()
    if _same_file(src, tracker_journal_path):
        return
    if not os.path.isfile(src):
        return
    _refuse_symlink(src)
    tracker_dir = os.path.dirname(tracker_journal_path)
    if os.path.lexists(tracker_dir):
        _refuse_symlink(tracker_dir)
    if os.path.lexists(tracker_journal_path):
        _refuse_symlink(tracker_journal_path)
    os.makedirs(tracker_dir, exist_ok=True)
    shutil.copy2(src, tracker_journal_path)
