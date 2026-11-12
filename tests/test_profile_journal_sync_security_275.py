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


def test_rejects_symlinked_profile_dir(temp_app, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "data.json"
    marker.write_text("{}", encoding="utf-8")

    profiles.ensure_app_structure()
    config = profiles.load_config()
    prior_active = config["active_profile_id"]
    prior_profiles = list(config.get("profiles") or [])
    profiles_root = profiles.get_profiles_root()
    link_name = "linked-prof"
    profile_dir = os.path.join(profiles_root, link_name)
    try:
        if os.path.lexists(profile_dir):
            if os.path.islink(profile_dir):
                os.unlink(profile_dir)
            elif os.path.isdir(profile_dir):
                os.rmdir(profile_dir)
        os.symlink(str(outside), profile_dir, target_is_directory=True)

        if not any(p["id"] == link_name for p in config["profiles"]):
            config["profiles"].append({"id": link_name, "name": "Linked"})
        config["active_profile_id"] = link_name
        profiles.save_config(config)

        src = tmp_path / "tracker.json"
        src.write_text('{"entries":{"x":1}}', encoding="utf-8")
        before = marker.read_text(encoding="utf-8")
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.sync_tracker_journal_to_active_profile(str(src))
        assert marker.read_text(encoding="utf-8") == before
    finally:
        config = profiles.load_config()
        config["active_profile_id"] = prior_active
        config["profiles"] = [p for p in config.get("profiles") or [] if p.get("id") != link_name]
        if not any(p.get("id") == prior_active for p in config["profiles"]):
            config["profiles"] = prior_profiles
        profiles.save_config(config)
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)
