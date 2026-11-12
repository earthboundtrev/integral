"""Security tests for profile journal sync path validation (#275)."""

from __future__ import annotations

import json
import os

import pytest

import profile_journal_sync
import profiles
import storage
from profile_journal_sync import ProfileJournalSyncError
from tests.test_backup import temp_app  # noqa: F401


def test_rejects_invalid_active_profile_id(temp_app, monkeypatch):
    config = profiles.load_config()
    config["active_profile_id"] = "../escape"
    monkeypatch.setattr(
        profiles,
        "load_config",
        lambda: config,
    )
    with pytest.raises(ProfileJournalSyncError):
        profile_journal_sync.resolved_active_profile_data_path()


def test_rejects_unknown_active_profile_id(temp_app, monkeypatch):
    config = profiles.load_config()
    config["active_profile_id"] = "not-in-list"
    monkeypatch.setattr(profiles, "load_config", lambda: config)
    with pytest.raises(ProfileJournalSyncError):
        profile_journal_sync.resolved_active_profile_data_path()


def test_rejects_symlinked_profile_dir(temp_app, tmp_path, monkeypatch):
    profiles.set_active_profile("default")
    profile_dir = profiles.get_profile_dir("default")
    src = tmp_path / "tracker.json"
    src.write_text('{"entries":{"x":1}}', encoding="utf-8")

    real_islink = os.path.islink

    def _islink(path: str) -> bool:
        if os.path.normcase(path) == os.path.normcase(profile_dir):
            return True
        return real_islink(path)

    monkeypatch.setattr(os.path, "islink", _islink)
    with pytest.raises(ProfileJournalSyncError):
        profile_journal_sync.sync_tracker_journal_to_active_profile(str(src))
