"""Profile vs tracker journal path sync for backup UI."""

from __future__ import annotations

import json
import os

import paths
import profile_journal_sync
import profiles
import storage
from tests.test_backup import temp_app  # noqa: F401


def test_active_profile_journal_differs_from_paths_data_file(temp_app):
    profile_path = profile_journal_sync.active_profile_journal_path()
    tracker_path = paths.data_file()
    assert os.path.normcase(profile_path) != os.path.normcase(tracker_path)


def test_sync_roundtrip_for_backup_export(temp_app):
    profiles.set_active_profile("default")
    tracker_path = paths.data_file()
    profile_path = profile_journal_sync.active_profile_journal_path()
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    marker = {"entries": {"2099-12-31": {"note": "sync-marker"}}, "settings": {}}
    with open(tracker_path, "w", encoding="utf-8") as handle:
        json.dump(marker, handle)
    profile_journal_sync.sync_tracker_journal_to_active_profile(tracker_path)
    with open(profile_path, encoding="utf-8") as handle:
        on_profile = json.load(handle)
    assert on_profile["entries"]["2099-12-31"]["note"] == "sync-marker"

    restored = {"entries": {"2099-12-30": {"note": "from-backup"}}, "settings": {}}
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    with open(profile_path, "w", encoding="utf-8") as handle:
        json.dump(restored, handle)
    profile_journal_sync.sync_active_profile_journal_to_tracker(tracker_path)
    with open(tracker_path, encoding="utf-8") as handle:
        on_tracker = json.load(handle)
    assert on_tracker["entries"]["2099-12-30"]["note"] == "from-backup"
