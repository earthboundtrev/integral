"""Security tests for profile journal sync path validation (#275)."""

from __future__ import annotations

import json
import os
import sys

import pytest

import profile_journal_sync
import profiles
import storage
from backup_dialog_ui import _rollback_journal_from_snapshot
from profile_journal_sync import ProfileJournalSyncError
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload


def test_rejects_invalid_active_profile_id(temp_app):
    config = profiles.load_config()
    config["active_profile_id"] = "../escape"
    profiles.save_config(config)
    with pytest.raises(ProfileJournalSyncError):
        profile_journal_sync.resolved_active_profile_data_path()


def test_rejects_unknown_active_profile_id(temp_app):
    config = profiles.load_config()
    config["active_profile_id"] = "not-in-list"
    profiles.save_config(config)
    with pytest.raises(ProfileJournalSyncError):
        profile_journal_sync.resolved_active_profile_data_path()


def _restore_config(prior_active: str, prior_profiles: list) -> None:
    config = profiles.load_config()
    config["active_profile_id"] = prior_active
    config["profiles"] = list(prior_profiles)
    profiles.save_config(config)


def test_linked_profile_dir_blocks_sync(temp_app, tmp_path):
    """Refuse sync through a real symlinked profile directory."""
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "SENTINEL"
    sentinel.write_text("untouched", encoding="utf-8")

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
        try:
            os.symlink(str(outside), profile_dir, target_is_directory=True)
        except OSError:
            pytest.skip("directory symlink creation unsupported in this environment")

        if not any(p["id"] == link_name for p in config["profiles"]):
            config["profiles"].append({"id": link_name, "name": "Linked"})
        config["active_profile_id"] = link_name
        profiles.save_config(config)

        src = tmp_path / "tracker.json"
        src.write_text('{"entries":{"x":1}}', encoding="utf-8")
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.sync_tracker_journal_to_active_profile(str(src))
        assert sentinel.read_text(encoding="utf-8") == "untouched"
    finally:
        _restore_config(prior_active, prior_profiles)
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)


@pytest.fixture(autouse=True)
def _restore_default_profile_after_test(temp_app):
    config = profiles.load_config()
    prior_active = config["active_profile_id"]
    prior_profiles = list(config.get("profiles") or [])
    yield
    _restore_config(prior_active, prior_profiles)


def test_rollback_removes_profile_journal_when_no_prior_snap(temp_app):
    profiles.set_active_profile("default")
    profile_path = profile_journal_sync.resolved_active_profile_data_path()
    if os.path.lexists(profile_path):
        os.remove(profile_path)
    assert not os.path.lexists(profile_path)
    with open(profile_path, "w", encoding="utf-8") as handle:
        json.dump(storage.empty_data(), handle)
    _rollback_journal_from_snapshot(profile_path, None)
    assert not os.path.lexists(profile_path)

