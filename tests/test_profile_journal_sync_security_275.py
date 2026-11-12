"""Security tests for profile journal sync path validation (#275)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

import profile_journal_sync
import profiles
import storage
from backup_dialog_ui import _rollback_journal_copies, _rollback_journal_from_snapshot
from profile_journal_sync import ProfileJournalSyncError
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file


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


def _restore_config(prior_active: str, prior_profiles: list) -> None:
    config = profiles.load_config()
    config["active_profile_id"] = prior_active
    config["profiles"] = list(prior_profiles)
    profiles.save_config(config)


def test_linked_profile_dir_blocks_sync(temp_app, tmp_path):
    """Refuse sync through a real symlink (Unix) or junction (Windows)."""
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
            if os.path.islink(profile_dir) or (sys.platform == "win32" and os.path.isdir(profile_dir)):
                if sys.platform == "win32":
                    subprocess.run(["cmd", "/c", "rmdir", profile_dir], check=False, capture_output=True)
                else:
                    os.unlink(profile_dir)
            elif os.path.isdir(profile_dir):
                os.rmdir(profile_dir)

        if sys.platform == "win32":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", profile_dir, str(outside)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip("junction creation unsupported in this environment")
        else:
            os.symlink(str(outside), profile_dir, target_is_directory=True)

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
        if sys.platform == "win32":
            if os.path.isdir(profile_dir):
                subprocess.run(["cmd", "/c", "rmdir", profile_dir], check=False, capture_output=True)
        elif os.path.islink(profile_dir):
            os.unlink(profile_dir)
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


def test_failed_reencrypt_rollback_without_prior_profile_file(temp_app, tmp_path):
    import paths
    from unittest.mock import MagicMock, patch

    from backup_dialog_ui import (
        GENERIC_REENCRYPT_ERROR,
        _snapshot_journal_if_present,
        reencrypt_restored_journal_from_disk,
        save_data_file,
    )

    profiles.set_active_profile("default")
    _seed_data_file(_minimal_v2_payload())
    tracker_path = paths.data_file()
    profile_path = profile_journal_sync.resolved_active_profile_data_path()
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    if os.path.lexists(profile_path):
        os.remove(profile_path)
    assert not os.path.lexists(profile_path)

    prior = storage.empty_data()
    with open(tracker_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    journal_snap = _snapshot_journal_if_present(tracker_path)
    profile_snap = _snapshot_journal_if_present(profile_path)

    restored = storage.empty_data()
    restored["entries"]["2099-08-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "new-profile"}
    }
    with open(tracker_path, "w", encoding="utf-8") as handle:
        json.dump(restored, handle)
    with open(profile_path, "w", encoding="utf-8") as handle:
        json.dump(restored, handle)

    tracker = MagicMock()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = "vault-passphrase-12"
    tracker.data_path = tracker_path

    calls: list[str] = []

    def flaky_save(path, payload, **kwargs):
        calls.append(path)
        if len(calls) >= 2:
            raise OSError("fail re-encrypt")
        return save_data_file(path, payload, **kwargs)

    with patch("backup_dialog_ui.save_data_file", side_effect=flaky_save):
        ok, msg = reencrypt_restored_journal_from_disk(tracker)
    assert ok is False
    assert msg == GENERIC_REENCRYPT_ERROR
    _rollback_journal_copies(tracker_path, journal_snap, profile_snap, profile_path)
    assert not os.path.lexists(profile_path)
