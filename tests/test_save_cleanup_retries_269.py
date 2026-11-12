"""Save temp / mismatched .bak cleanup retries (issue #269)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import integral_logging
import paths
import personal_dev_tracker
import profiles
import vault
from integral_dialogs import show_security_dialog
from tests.conftest import pump_tk, pump_tk_until
from tests.test_data_payload_registry_177 import _minimal_v2_payload
from vault import (
    _LEFTOVER_SAVE_TEMP_WARNING,
    _MISMATCHED_JOURNAL_BACKUP_WARNING,
    _STARTUP_DEFER_BACKUP_CLEANUP_WARNING,
    _SWEEP_PATH_SKIPPED_WARNING,
    save_data_file,
    save_temp_path,
    sweep_journal_save_artifacts_at_startup,
    try_remove_leftover_save_temp,
)


def _configure_integral_log(monkeypatch, tmp_path: Path) -> Path:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "integral.log"

    def _log_path() -> str:
        return str(log_file)

    monkeypatch.setattr(paths, "app_log_file", _log_path)
    monkeypatch.setattr(integral_logging, "app_log_file", _log_path)
    integral_logging.reset_logger_cache()
    return log_file


def _read_log(log_file: Path) -> str:
    logger = integral_logging.get_logger()
    for handler in logger.handlers:
        try:
            handler.flush()
        except OSError:
            pass
    if not log_file.is_file():
        return ""
    return log_file.read_text(encoding="utf-8")


@pytest.fixture
def tk_root():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_failed_temp_unlink_warns_and_retries_on_next_save(tmp_path, monkeypatch):
    log_file = _configure_integral_log(monkeypatch, tmp_path)
    data_file = tmp_path / "data.json"
    payload = {"v": 1}
    save_data_file(str(data_file), payload, encrypted=False, passphrase=None)

    temp_file = Path(save_temp_path(str(data_file)))
    temp_file.write_text('{"stale": true}', encoding="utf-8")

    real_remove = os.remove
    fail_next = {"left": 1}

    def guarded_remove(path, *args, **kwargs):
        if os.path.normpath(str(path)) == os.path.normpath(str(temp_file)) and fail_next["left"] > 0:
            fail_next["left"] -= 1
            raise OSError("file locked")
        return real_remove(path, *args, **kwargs)

    with patch("vault.os.remove", side_effect=guarded_remove):
        ok = try_remove_leftover_save_temp(str(data_file))
    assert ok is False
    assert temp_file.exists()
    assert _LEFTOVER_SAVE_TEMP_WARNING in _read_log(log_file)

    payload2 = {"v": 2}
    save_data_file(str(data_file), payload2, encrypted=False, passphrase=None)
    assert not temp_file.exists()
    with open(data_file, encoding="utf-8") as handle:
        assert json.load(handle) == payload2


def test_save_in_other_profile_does_not_remove_foreign_temp(tmp_path):
    profile_a = tmp_path / "profiles" / "alpha"
    profile_b = tmp_path / "profiles" / "beta"
    profile_a.mkdir(parents=True)
    profile_b.mkdir(parents=True)
    data_a = profile_a / "data.json"
    data_b = profile_b / "data.json"
    save_data_file(str(data_a), {"profile": "a"}, encrypted=False, passphrase=None)
    foreign_temp = Path(save_temp_path(str(data_b)))
    foreign_temp.write_text("{}", encoding="utf-8")

    save_data_file(str(data_a), {"profile": "a", "n": 2}, encrypted=False, passphrase=None)
    assert foreign_temp.exists()


def test_startup_sweep_removes_leftover_temp_before_first_save(tmp_path, monkeypatch):
    _configure_integral_log(monkeypatch, tmp_path)
    app_dir = tmp_path / "integral-home"
    app_dir.mkdir()
    profiles_root = app_dir / "profiles" / "default"
    profiles_root.mkdir(parents=True)
    config = {
        "active_profile_id": "default",
        "profiles": [{"id": "default", "name": "Default"}],
    }
    with open(app_dir / "config.json", "w", encoding="utf-8") as handle:
        json.dump(config, handle)
    data_path = profiles_root / "data.json"
    save_data_file(str(data_path), _minimal_v2_payload(), encrypted=False, passphrase=None)
    temp_path = Path(save_temp_path(str(data_path)))
    temp_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(paths, "user_data_dir", lambda: str(app_dir))
    monkeypatch.setattr(profiles, "get_app_dir", lambda: str(app_dir))
    monkeypatch.setattr(paths, "data_file", lambda: str(app_dir / "data.json"))
    profiles.ensure_app_structure()

    sweep_journal_save_artifacts_at_startup()
    assert not temp_path.exists()


def test_failed_mismatched_bak_remove_warns_and_retries(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    log_file = _configure_integral_log(monkeypatch, tmp_path)
    data_file = tmp_path / "data.json"
    save_data_file(str(data_file), {"plain": 1}, encrypted=False, passphrase=None)
    bak_file = tmp_path / "data.json.bak"
    save_data_file(str(bak_file), {"enc": 1}, encrypted=True, passphrase="secret")
    assert bak_file.exists()

    real_remove = os.remove
    fail_once = {"pending": True}

    def guarded_remove(path, *args, **kwargs):
        if (
            fail_once["pending"]
            and os.path.normpath(str(path)) == os.path.normpath(str(bak_file))
        ):
            fail_once["pending"] = False
            raise OSError("locked bak")
        return real_remove(path, *args, **kwargs)

    with patch("vault.os.remove", side_effect=guarded_remove):
        vault.drop_opposite_format_journal_backup(str(data_file), encrypted=False)
    assert bak_file.exists()
    assert _MISMATCHED_JOURNAL_BACKUP_WARNING in _read_log(log_file)

    vault.drop_opposite_format_journal_backup(str(data_file), encrypted=False)
    assert not bak_file.exists()


def test_matching_backup_not_deleted_on_save(tmp_path):
    pytest.importorskip("cryptography")
    data_file = tmp_path / "data.json"
    passphrase = "same-format"
    save_data_file(str(data_file), {"n": 1}, encrypted=True, passphrase=passphrase)
    save_data_file(str(data_file), {"n": 2}, encrypted=True, passphrase=passphrase)
    bak_file = tmp_path / "data.json.bak"
    assert bak_file.exists()
    save_data_file(str(data_file), {"n": 3}, encrypted=True, passphrase=passphrase)
    assert bak_file.exists()


def test_wait_for_in_flight_save_uses_sleep_not_tight_update(tk_root):
    from integral_dialogs import wait_for_tracker_save_idle

    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker._save_write_in_progress = True
    poll_count = {"n": 0}
    real_update = tk_root.update

    def counting_update(*args, **kwargs):
        poll_count["n"] += 1
        return real_update(*args, **kwargs)

    sleeps: list[float] = []

    def track_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        tracker._save_write_in_progress = False

    tk_root.update = counting_update  # type: ignore[method-assign]
    with patch("time.sleep", side_effect=track_sleep):
        assert wait_for_tracker_save_idle(tracker) is True

    assert sleeps, "expected sleep between in-flight save polls"
    assert poll_count["n"] <= len(sleeps) + 1


@pytest.fixture(autouse=True)
def _sync_tracker_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


def test_change_passphrase_confirm_cancel_is_silent(tk_root, request):
    pytest.importorskip("cryptography")
    from tests.test_encryption_dialog_255 import _load_tracker_encrypted, _click_button

    tracker = _load_tracker_encrypted(tk_root, "old-pass")
    tracker.vault_passphrase = "old-pass"
    prev_pass = tracker.vault_passphrase

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=["old-pass", "new-pass", None],
    ):
        show_security_dialog(tracker)
        pump_tk(tk_root, steps=5)
        _click_button(tk_root, "Change passphrase")

    assert tracker.vault_passphrase == prev_pass
    calls = getattr(request.node, "_integral_messagebox_calls", [])
    assert not any(
        name == "showerror" and args and args[0] == "Mismatch" for name, args, _kwargs in calls
    )


def test_presave_retry_keeps_bak_when_primary_unreadable(tmp_path):
    pytest.importorskip("cryptography")
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    save_data_file(str(bak_file), {"backup": 1}, encrypted=True, passphrase="secret")
    with open(data_file, "w", encoding="utf-8") as handle:
        handle.write('{"integral_encrypted": true, "truncated')

    with patch("vault.open", side_effect=OSError("write blocked")):
        with pytest.raises(OSError, match="write blocked"):
            save_data_file(str(data_file), {"n": 1}, encrypted=False, passphrase=None)

    assert bak_file.exists()


def test_startup_skips_invalid_profile_id(tmp_path, monkeypatch):
    log_file = _configure_integral_log(monkeypatch, tmp_path)
    app_dir = tmp_path / "integral-home"
    app_dir.mkdir()
    profiles_root = app_dir / "profiles"
    profiles_root.mkdir(parents=True)
    config = {
        "active_profile_id": "default",
        "profiles": [
            {"id": "default", "name": "Default"},
            {"id": "../escape", "name": "Invalid"},
        ],
    }
    with open(app_dir / "config.json", "w", encoding="utf-8") as handle:
        json.dump(config, handle)

    monkeypatch.setattr(paths, "user_data_dir", lambda: str(app_dir))
    monkeypatch.setattr(profiles, "get_app_dir", lambda: str(app_dir))

    sweep_journal_save_artifacts_at_startup()
    assert _SWEEP_PATH_SKIPPED_WARNING in _read_log(log_file)


def test_startup_keeps_bak_when_primary_unreadable(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    log_file = _configure_integral_log(monkeypatch, tmp_path)
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    save_data_file(str(bak_file), {"from": "backup"}, encrypted=True, passphrase="secret")
    with open(data_file, "w", encoding="utf-8") as handle:
        handle.write('{"integral_encrypted": true, "truncated')

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_journal_save_artifacts_at_startup()

    assert bak_file.exists()
    assert _STARTUP_DEFER_BACKUP_CLEANUP_WARNING in _read_log(log_file)


def test_sweep_skips_traversal_escape_path(tmp_path, monkeypatch):
    log_file = _configure_integral_log(monkeypatch, tmp_path)
    container = tmp_path / "profiles" / "default"
    container.mkdir(parents=True)
    escaped = tmp_path / "escaped"
    escaped.mkdir()
    escaped_journal = escaped / "data.json"
    save_data_file(str(escaped_journal), {"escaped": True}, encrypted=False, passphrase=None)
    escaped_temp = Path(save_temp_path(str(escaped_journal)))
    escaped_temp.write_text("{}", encoding="utf-8")

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(escaped_journal), str(container))],
    ):
        sweep_journal_save_artifacts_at_startup()

    assert escaped_temp.exists()
    assert _SWEEP_PATH_SKIPPED_WARNING in _read_log(log_file)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unsupported")
def test_sweep_skips_symlink_escape(tmp_path, monkeypatch):
    try:
        outside = tmp_path / "outside"
        profile_dir = tmp_path / "profiles" / "default"
        outside.mkdir()
        profile_dir.mkdir(parents=True)
        outside_journal = outside / "data.json"
        save_data_file(str(outside_journal), {"v": 1}, encrypted=False, passphrase=None)
        outside_temp = Path(save_temp_path(str(outside_journal)))
        outside_temp.write_text("{}", encoding="utf-8")
        link = profile_dir / "data.json"
        link.symlink_to(outside_journal, target_is_directory=False)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported on this platform")

    log_file = _configure_integral_log(monkeypatch, tmp_path)
    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(link), str(profile_dir))],
    ):
        sweep_journal_save_artifacts_at_startup()

    assert outside_temp.exists()
    assert _SWEEP_PATH_SKIPPED_WARNING in _read_log(log_file)


def test_tracker_startup_invokes_startup_sweep(tmp_path, monkeypatch, tk_root):
    _configure_integral_log(monkeypatch, tmp_path)
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    save_data_file(data_path, _minimal_v2_payload(), encrypted=False, passphrase=None)
    temp_path = Path(save_temp_path(data_path))
    temp_path.write_text("{}", encoding="utf-8")

    called = {"n": 0}
    real_sweep = sweep_journal_save_artifacts_at_startup

    def tracking_sweep() -> None:
        called["n"] += 1
        return real_sweep()

    with patch("vault.sweep_journal_save_artifacts_at_startup", side_effect=tracking_sweep):
        personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    pump_tk(tk_root, steps=3)
    assert called["n"] == 1
    assert not temp_path.exists()
