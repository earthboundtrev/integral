"""Keep tracker journal paths and per-profile data.json in sync for backup/export."""

from __future__ import annotations

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


def _is_link_or_junction(path: str) -> bool:
    if os.path.islink(path):
        return True
    if sys.platform == "win32":
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None:
            return bool(is_junction(path))
    return False


def _refuse_link(path: str) -> None:
    if os.path.lexists(path) and _is_link_or_junction(path):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)


def _profiles_root_real() -> str:
    profiles_root = profiles.get_profiles_root()
    if os.path.isdir(profiles_root):
        return os.path.normcase(os.path.realpath(profiles_root))
    return os.path.normcase(os.path.abspath(profiles_root))


def _assert_contained(child: str, root_real: str) -> str:
    child_real = os.path.normcase(os.path.realpath(child))
    sep = os.path.normcase(os.sep)
    if child_real != root_real and not child_real.startswith(root_real + sep):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    return child_real


def _layout_paths(safe_id: str) -> tuple[str, str, str]:
    profiles_root = profiles.get_profiles_root()
    profile_dir = os.path.join(profiles_root, safe_id)
    journal_path = os.path.join(profile_dir, storage.DATA_FILE_NAME)
    return profiles_root, profile_dir, journal_path


def _validate_layout_before_io(safe_id: str) -> tuple[str, str, str]:
    """Validate id, containment, and links/junctions before migration or file writes."""
    profiles_root, profile_dir, journal_path = _layout_paths(safe_id)
    for path in (profile_dir, journal_path):
        _refuse_link(path)
    root_real = _profiles_root_real()
    _assert_contained(profile_dir, root_real)
    _assert_contained(journal_path, root_real)
    return profiles_root, profile_dir, journal_path


def resolved_active_profile_data_path() -> str:
    """Active profile data.json path after id validation and containment checks."""
    safe_id = _validated_active_profile_id()
    _profiles_root, _profile_dir, journal_path = _validate_layout_before_io(safe_id)
    return journal_path


def active_profile_journal_path() -> str:
    return resolved_active_profile_data_path()


def _same_file(path_a: str, path_b: str) -> bool:
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def _safe_copy(src: str, dest: str) -> None:
    safe_id = _validated_active_profile_id()
    root_real = _profiles_root_real()
    _profiles_root, profile_dir, journal_path = _validate_layout_before_io(safe_id)
    if os.path.normcase(os.path.abspath(dest)) != os.path.normcase(os.path.abspath(journal_path)):
        raise ProfileJournalSyncError(GENERIC_PROFILE_SYNC_ERROR)
    _refuse_link(src)
    _assert_contained(dest, root_real)
    os.makedirs(profile_dir, exist_ok=True)
    _refuse_link(profile_dir)
    if os.path.lexists(dest):
        _refuse_link(dest)
    shutil.copy2(src, dest)


def sync_tracker_journal_to_active_profile(tracker_journal_path: str) -> None:
    """Copy the journal file the tracker saves into the active profile artifact path."""
    dest = resolved_active_profile_data_path()
    if _same_file(tracker_journal_path, dest):
        return
    if not os.path.isfile(tracker_journal_path):
        return
    _refuse_link(tracker_journal_path)
    _safe_copy(tracker_journal_path, dest)


def sync_active_profile_journal_to_tracker(tracker_journal_path: str) -> None:
    """After profile backup import, mirror restored profile data.json to the tracker path."""
    src = resolved_active_profile_data_path()
    if _same_file(src, tracker_journal_path):
        return
    if not os.path.isfile(src):
        return
    os.makedirs(os.path.dirname(tracker_journal_path), exist_ok=True)
    shutil.copy2(src, tracker_journal_path)
