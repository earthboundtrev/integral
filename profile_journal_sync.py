"""Keep tracker journal paths and per-profile data.json in sync for backup/export."""

from __future__ import annotations

import os
import shutil

import profiles
import storage


def active_profile_journal_path() -> str:
    profiles.ensure_app_structure()
    return storage.get_data_path()


def _same_file(path_a: str, path_b: str) -> bool:
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def sync_tracker_journal_to_active_profile(tracker_journal_path: str) -> None:
    """Copy the journal file the tracker saves into the active profile artifact path."""
    dest = active_profile_journal_path()
    if _same_file(tracker_journal_path, dest):
        return
    if not os.path.isfile(tracker_journal_path):
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(tracker_journal_path, dest)


def sync_active_profile_journal_to_tracker(tracker_journal_path: str) -> None:
    """After profile backup import, mirror restored profile data.json to the tracker path."""
    src = active_profile_journal_path()
    if _same_file(src, tracker_journal_path):
        return
    if not os.path.isfile(src):
        return
    os.makedirs(os.path.dirname(tracker_journal_path), exist_ok=True)
    shutil.copy2(src, tracker_journal_path)
