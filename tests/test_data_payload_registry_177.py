"""Regression tests for data.json top-level key registry (#177)."""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import paths
import personal_dev_tracker
from data_payload_registry import (
    assert_payload_registry_parity,
    clear_ephemeral_top_level_keys,
    extract_extra_top_level,
    register_ephemeral_top_level_key,
    validate_registry_key_name,
)
from fitness.engine import load_program_definitions, migrate_data
from integral_io import backup_payload, load_backup, restore_backup_to_path, write_backup
from tests.conftest import pump_tk
from vault import load_data_file, load_data_file_with_recovery, save_data_file


def _unknown_extras() -> dict:
    return {
        "sleep_log": {
            "2026-10-14": {"bed": "23:30", "unicode": "über"},
            "empty_day": {},
        },
        "numeric_edge": 1.0,
    }


def _minimal_v2_payload(**extra: object) -> dict:
    base = {
        "schema_version": 2,
        "categories": {},
        "entries": {},
        "settings": {
            "dark_mode": False,
            "onboarding_complete": True,
            "encryption_enabled": False,
        },
        "sessions": [],
        "milestones": [],
        "journal": {"prompts": [], "entries": []},
        "creative_projects": {"schema_version": 1, "projects": []},
        "youtube_history": {},
        "day_plans": {},
        "todos": {"items": []},
        "practices": {"items": []},
        "program_state": {},
        "user_levels": {"x": 1},
    }
    base.update(extra)
    return base


def _seed_data_file(payload: dict, *, encrypted: bool = False, passphrase: str | None = None) -> str:
    path = paths.data_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_data_file(path, payload, encrypted=encrypted, passphrase=passphrase)
    return path


@pytest.fixture(autouse=True)
def _clear_ephemeral_registry():
    clear_ephemeral_top_level_keys()
    yield
    clear_ephemeral_top_level_keys()


@pytest.fixture(autouse=True)
def _sync_tracker_data_file(monkeypatch):
    """Keep personal_dev_tracker.DATA_FILE aligned with isolated paths.data_file()."""
    monkeypatch.setattr(
        personal_dev_tracker,
        "DATA_FILE",
        paths.data_file(),
    )


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_registry_parity():
    assert_payload_registry_parity()


def test_backup_prefix_cannot_be_registered():
    with pytest.raises(ValueError, match="backup_"):
        validate_registry_key_name("backup_custom")


def test_restore_backup_drops_backup_prefixed_keys(tmp_path):
    """Unknown keys named backup_* are stripped on JSON restore (integral_io edge case)."""
    target = tmp_path / "data.json"
    backup = {
        "schema_version": 2,
        "entries": {},
        "backup_shadow": {"lost": True},
        "sleep_log": {"kept": True},
    }
    restore_backup_to_path(backup, str(target), make_copy=False)
    restored = json.loads(target.read_text(encoding="utf-8"))
    assert "backup_shadow" not in restored
    assert restored["sleep_log"] == {"kept": True}


def test_migrate_v1_carries_unknown_keys():
    programs = load_program_definitions()
    legacy = {
        "categories": {},
        "entries": {},
        "settings": {"dark_mode": False},
        "sleep_log": _unknown_extras()["sleep_log"],
    }
    migrated = migrate_data(legacy, programs)
    assert migrated["schema_version"] == 2
    assert migrated["sleep_log"] == legacy["sleep_log"]


def test_extract_extra_top_level():
    data = _minimal_v2_payload(**_unknown_extras())
    extra = extract_extra_top_level(data)
    assert extra == _unknown_extras()


def test_unknown_keys_survive_save_and_reload(tk_root):
    expected_extra = _unknown_extras()
    payload = _minimal_v2_payload(**expected_extra)
    _seed_data_file(payload)

    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    assert tracker._extra_top_level == expected_extra

    tracker.entries = {"2026-10-25": {}}
    tracker.save_data(flush=True)

    reloaded = json.loads(open(paths.data_file(), encoding="utf-8").read())
    for key, value in expected_extra.items():
        assert reloaded[key] == value

    root2 = tk.Tk()
    root2.withdraw()
    try:
        tracker2 = personal_dev_tracker.PersonalDevelopmentTracker(root2)
        assert tracker2._extra_top_level == expected_extra
    finally:
        root2.destroy()


def test_frozen_user_data_path_same_behavior(monkeypatch, tmp_path, tk_root):
    appdata = tmp_path / "AppData" / "Roaming" / "Integral"
    appdata.mkdir(parents=True)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths, "user_data_dir", lambda: str(appdata))
    assert paths.data_file() == os.path.join(str(appdata), "data.json")

    expected_extra = _unknown_extras()
    _seed_data_file(_minimal_v2_payload(**expected_extra))
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["dark_mode"] = not tracker.settings.get("dark_mode", False)
    tracker.save_data(flush=True)
    reloaded = json.loads(open(paths.data_file(), encoding="utf-8").read())
    assert reloaded["sleep_log"] == expected_extra["sleep_log"]


def test_encrypted_file_preserves_unknown_keys(tk_root):
    passphrase = "test-pass-phrase"
    expected_extra = _unknown_extras()
    payload = _minimal_v2_payload(**expected_extra)
    payload["settings"]["encryption_enabled"] = True
    _seed_data_file(payload, encrypted=True, passphrase=passphrase)

    def _unlock(tracker):
        tracker.vault_passphrase = passphrase
        return True

    with patch("personal_dev_tracker.prompt_vault_unlock", side_effect=_unlock):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    assert tracker._extra_top_level == expected_extra
    tracker.save_data(flush=True)
    reloaded = load_data_file(paths.data_file(), passphrase)
    assert reloaded["sleep_log"] == expected_extra["sleep_log"]
    assert "sleep_log" in reloaded


def test_bak_recovery_preserves_extras(tmp_path, monkeypatch):
    data_path = tmp_path / "data.json"
    bak_path = tmp_path / "data.json.bak"
    expected_extra = _unknown_extras()
    good = _minimal_v2_payload(**expected_extra)
    save_data_file(str(bak_path), good, encrypted=False, passphrase=None)
    data_path.write_text("{not valid json", encoding="utf-8")

    loaded = load_data_file_with_recovery(
        str(data_path),
        None,
        on_recovery_prompt=lambda _p, _t: True,
        on_both_corrupt_prompt=lambda: False,
    )
    assert loaded["sleep_log"] == expected_extra["sleep_log"]
    save_data_file(str(data_path), loaded, encrypted=False, passphrase=None)
    again = json.loads(data_path.read_text(encoding="utf-8"))
    assert again["sleep_log"] == expected_extra["sleep_log"]


def test_user_levels_survive_save(tk_root):
    payload = _minimal_v2_payload(user_levels={"push": 3, "pull": 1.0})
    _seed_data_file(payload)
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    assert tracker.user_levels == {"push": 3, "pull": 1.0}
    tracker.save_data(flush=True)
    reloaded = json.loads(open(paths.data_file(), encoding="utf-8").read())
    assert reloaded["user_levels"] == {"push": 3, "pull": 1.0}


def test_flush_save_async_writes_extras(tk_root):
    expected_extra = _unknown_extras()
    _seed_data_file(_minimal_v2_payload(**expected_extra))
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.entries = {"2026-10-25": {"Body & Presence": {"rating": 5}}}
    tracker.save_data(flush=False)
    pump_tk(tk_root, steps=40)
    time.sleep(0.3)
    pump_tk(tk_root, steps=10)
    reloaded = json.loads(open(paths.data_file(), encoding="utf-8").read())
    assert reloaded["sleep_log"] == expected_extra["sleep_log"]


def test_locked_file_keeps_extras_in_memory_and_writes_after_release(tk_root):
    if sys.platform == "win32":
        pytest.skip("fcntl file locking test is for POSIX CI")

    expected_extra = _unknown_extras()
    data_path = _seed_data_file(_minimal_v2_payload(**expected_extra))
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    lock_handle = open(data_path, "r+")
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    try:
        with patch("personal_dev_tracker.save_data_file", side_effect=OSError("locked")):
            tracker.save_data(flush=True)
        assert tracker._extra_top_level == expected_extra
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()

    tracker.save_data(flush=True)
    reloaded = json.loads(open(data_path, encoding="utf-8").read())
    assert reloaded["sleep_log"] == expected_extra["sleep_log"]


def test_backup_export_restore_roundtrip_unknown_key(tk_root, tmp_path):
    expected_extra = _unknown_extras()
    _seed_data_file(_minimal_v2_payload(**expected_extra))
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    backup_path = tmp_path / "backup.json"
    write_backup(tracker._payload(), str(backup_path))
    backup = load_backup(str(backup_path))
    assert backup["sleep_log"] == expected_extra["sleep_log"]

    target = tmp_path / "restored.json"
    restore_backup_to_path(backup, str(target), make_copy=False)
    restored = json.loads(target.read_text(encoding="utf-8"))
    assert restored["sleep_log"] == expected_extra["sleep_log"]


def test_ephemeral_registry_key_roundtrip(tk_root):
    register_ephemeral_top_level_key("__pytest_registry_fixture__", "_pytest_registry_fixture")
    payload = _minimal_v2_payload(
        __pytest_registry_fixture__={"registered": True},
        **_unknown_extras(),
    )
    _seed_data_file(payload)
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    assert tracker._pytest_registry_fixture == {"registered": True}
    tracker.save_data(flush=True)
    reloaded = json.loads(open(paths.data_file(), encoding="utf-8").read())
    assert reloaded["__pytest_registry_fixture__"] == {"registered": True}


def test_parity_fails_when_build_emits_unregistered_key(monkeypatch):
    import data_payload_registry as reg

    real_build = reg.build_known_top_level_payload

    def drifted(tracker, **kwargs):
        payload = real_build(tracker, **kwargs)
        payload["__not_registered__"] = True
        return payload

    monkeypatch.setattr(reg, "build_known_top_level_payload", drifted)
    with pytest.raises(AssertionError, match="Registry parity"):
        reg.assert_payload_registry_parity()


def test_migrated_to_fitness_db_unchanged_after_load_save(tk_root):
    sessions = [
        {
            "date": "2026-10-01",
            "program_id": "CC1",
            "migrated_to_fitness_db": True,
        }
    ]
    _seed_data_file(_minimal_v2_payload(sessions=sessions))
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    assert tracker.sessions[0]["migrated_to_fitness_db"] is True
    tracker.save_data(flush=True)
    reloaded = json.loads(open(paths.data_file(), encoding="utf-8").read())
    assert reloaded["sessions"][0]["migrated_to_fitness_db"] is True


def test_payload_keys_match_registry_set():
    from data_payload_registry import REGISTERED_TOP_LEVEL_KEYS, build_known_top_level_payload

    stub = SimpleNamespace(
        categories={},
        entries={},
        settings={},
        sessions=[],
        milestones=[],
        journal={},
        creative_projects={},
        youtube_history={},
        day_plans={},
        todos={},
        practices={},
        program_state={},
        user_levels={},
    )
    assert set(build_known_top_level_payload(stub).keys()) == set(REGISTERED_TOP_LEVEL_KEYS)


def test_manual_downgrade_documented():
    """Manual: old build may drop keys; new build preserves via _extra_top_level after upgrade."""
    pytest.skip("Manual packaged downgrade check per issue #177 AC")
