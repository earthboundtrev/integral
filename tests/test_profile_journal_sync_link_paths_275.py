"""Link/junction and path-ordering tests for profile journal sync (#275 security #4)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import profile_journal_sync
import profiles
import storage
from profile_journal_sync import ProfileJournalSyncError
from tests.test_backup import temp_app  # noqa: F401

_OUTSIDE_SENTINEL = "SENTINEL"


def _outside_tree(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / _OUTSIDE_SENTINEL
    sentinel.write_text("untouched", encoding="utf-8")
    return outside, sentinel


def _restore_config(prior_active: str, prior_profiles: list) -> None:
    config = profiles.load_config()
    config["active_profile_id"] = prior_active
    config["profiles"] = list(prior_profiles)
    profiles.save_config(config)


def _tracker_src(tmp_path):
    src = tmp_path / "tracker.json"
    src.write_text('{"entries":{"x":1}}', encoding="utf-8")
    return str(src)


@pytest.fixture(autouse=True)
def _restore_config_after(temp_app):
    config = profiles.load_config()
    prior_active = config["active_profile_id"]
    prior_profiles = list(config.get("profiles") or [])
    yield
    _restore_config(prior_active, prior_profiles)


def _assert_outside_untouched(sentinel) -> None:
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    assert not any(sentinel.parent.glob("data.json"))


@pytest.mark.skipif(sys.platform == "win32", reason="Unix symlink tests")
def test_linked_default_profile_folder_blocks_sync(temp_app, tmp_path):
    """(a) default profile directory is a symlink: no write, generic error."""
    outside, sentinel = _outside_tree(tmp_path)
    profiles.set_active_profile("default")
    profiles_root = profiles.get_profiles_root()
    profile_dir = os.path.join(profiles_root, "default")
    if os.path.lexists(profile_dir):
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)
        elif os.path.isdir(profile_dir):
            for name in os.listdir(profile_dir):
                os.remove(os.path.join(profile_dir, name))
            os.rmdir(profile_dir)
    os.symlink(str(outside), profile_dir, target_is_directory=True)
    try:
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.sync_tracker_journal_to_active_profile(_tracker_src(tmp_path))
        _assert_outside_untouched(sentinel)
    finally:
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix symlink tests")
def test_linked_profiles_root_blocks_sync(temp_app, tmp_path, monkeypatch):
    """(b) profiles/ root is a symlink: must refuse, not treat as allowed root."""
    outside, sentinel = _outside_tree(tmp_path)
    app_dir = profiles.get_app_dir()
    real_profiles = os.path.join(app_dir, "profiles")
    linked_profiles = os.path.join(app_dir, "profiles-link")
    if os.path.lexists(linked_profiles):
        if os.path.islink(linked_profiles):
            os.unlink(linked_profiles)
    os.symlink(str(outside), linked_profiles, target_is_directory=True)
    try:
        if os.path.isdir(real_profiles) and not os.path.islink(real_profiles):
            default_dir = os.path.join(real_profiles, "default")
            if os.path.isdir(default_dir):
                for name in list(os.listdir(default_dir)):
                    os.remove(os.path.join(default_dir, name))
        profiles.set_active_profile("default")

        monkeypatch.setattr(profiles, "get_profiles_root", lambda: linked_profiles)
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.sync_tracker_journal_to_active_profile(_tracker_src(tmp_path))
        _assert_outside_untouched(sentinel)
    finally:
        if os.path.islink(linked_profiles):
            os.unlink(linked_profiles)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix symlink tests")
def test_linked_custom_profile_folder_blocks_sync(temp_app, tmp_path):
    """(c) existing custom profile folder is a symlink."""
    outside, sentinel = _outside_tree(tmp_path)
    custom_id = "custom-link-me"
    profiles_root = profiles.get_profiles_root()
    config = profiles.load_config()
    if not any(p["id"] == custom_id for p in config["profiles"]):
        config["profiles"].append({"id": custom_id, "name": "Custom"})
        profiles.save_config(config)
    profile_dir = os.path.join(profiles_root, custom_id)
    if os.path.lexists(profile_dir):
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)
        elif os.path.isdir(profile_dir):
            os.rmdir(profile_dir)
    os.symlink(str(outside), profile_dir, target_is_directory=True)
    profiles.set_active_profile(custom_id)
    try:
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.sync_tracker_journal_to_active_profile(_tracker_src(tmp_path))
        _assert_outside_untouched(sentinel)
    finally:
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_windows_junction_profile_dir_blocks_sync(temp_app, tmp_path):
    """Real directory junction on profile folder (Windows CI)."""
    outside, sentinel = _outside_tree(tmp_path)
    profiles_root = profiles.get_profiles_root()
    junction_name = "junction-default"
    profile_dir = os.path.join(profiles_root, junction_name)
    config = profiles.load_config()
    if not any(p["id"] == junction_name for p in config["profiles"]):
        config["profiles"].append({"id": junction_name, "name": "Junction"})
    config["active_profile_id"] = junction_name
    profiles.save_config(config)
    if os.path.lexists(profile_dir):
        if os.path.isdir(profile_dir):
            subprocess.run(["cmd", "/c", "rmdir", profile_dir], check=False, capture_output=True)
        else:
            os.unlink(profile_dir)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", profile_dir, str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"mklink failed: {result.stderr or result.stdout}"
    try:
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.sync_tracker_journal_to_active_profile(_tracker_src(tmp_path))
        _assert_outside_untouched(sentinel)
    finally:
        if os.path.isdir(profile_dir):
            subprocess.run(["cmd", "/c", "rmdir", profile_dir], check=False, capture_output=True)


def test_sync_validates_before_ensure_app_structure(temp_app, monkeypatch, tmp_path):
    """Layout migration must not run before id + path component validation on sync."""
    order: list[str] = []

    real_ensure = profiles.ensure_app_structure

    def tracked_ensure():
        order.append("ensure")
        return real_ensure()

    monkeypatch.setattr(profiles, "ensure_app_structure", tracked_ensure)

    original_refuse = profile_journal_sync._refuse_link

    def tracked_refuse(path: str) -> None:
        order.append("refuse")
        return original_refuse(path)

    monkeypatch.setattr(profile_journal_sync, "_refuse_link", tracked_refuse)

    profile_journal_sync.sync_tracker_journal_to_active_profile(_tracker_src(tmp_path))
    first_refuse = order.index("refuse")
    first_ensure_in_sync = next(i for i, tag in enumerate(order) if tag == "ensure" and i >= first_refuse)
    assert first_refuse < first_ensure_in_sync, f"order was {order}"


def test_linked_profiles_root_refused_by_resolved_path(temp_app, tmp_path, monkeypatch):
    """resolved path must reject a linked profiles/ root before I/O."""
    if sys.platform == "win32":
        pytest.skip("covered by junction test on Windows")
    outside, _ = _outside_tree(tmp_path)
    app_dir = profiles.get_app_dir()
    linked_profiles = os.path.join(app_dir, "profiles-link-root")
    os.symlink(str(outside), linked_profiles, target_is_directory=True)
    try:
        import profiles as profiles_mod

        monkeypatch.setattr(profiles_mod, "get_profiles_root", lambda: linked_profiles)
        profiles.set_active_profile("default")
        with pytest.raises(ProfileJournalSyncError):
            profile_journal_sync.resolved_active_profile_data_path()
    finally:
        if os.path.islink(linked_profiles):
            os.unlink(linked_profiles)
