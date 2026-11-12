"""Startup journal .bak retention until open (issue #281) — security item (private)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import tkinter as tk

import personal_dev_tracker
from integral_dialogs import wait_for_tracker_save_idle
from tests.conftest import pump_tk
from tests.test_data_payload_registry_177 import _minimal_v2_payload
from vault import (
    drop_mismatched_journal_backup_after_journal_open,
    encrypt_payload,
    load_data_file,
    save_data_file,
    sweep_journal_save_artifacts_at_startup,
)


def _corrupt_live_envelope_ciphertext(data_file: Path, passphrase: str, payload: dict) -> None:
    """Keep a readable encrypted envelope on disk that will not decrypt with ``passphrase``."""
    save_data_file(str(data_file), payload, encrypted=True, passphrase=passphrase)
    other = encrypt_payload({"decoy": True}, "other-pass")
    with open(data_file, encoding="utf-8") as handle:
        envelope = json.load(handle)
    envelope["ciphertext"] = other["ciphertext"]
    with open(data_file, "w", encoding="utf-8") as handle:
        json.dump(envelope, handle, indent=2)


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_startup_sweep_keeps_mismatched_bak_when_live_envelope_unreadable_decrypt(tmp_path):
    pytest.importorskip("cryptography")
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    good = _minimal_v2_payload()
    _corrupt_live_envelope_ciphertext(data_file, "live-pass", good)
    save_data_file(str(bak_file), good, encrypted=False, passphrase=None)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_journal_save_artifacts_at_startup()

    assert bak_file.is_file()


def test_startup_sweep_keeps_mismatched_bak_plain_live_encrypted_bak(tmp_path):
    pytest.importorskip("cryptography")
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    save_data_file(str(data_file), {"n": 1}, encrypted=False, passphrase=None)
    save_data_file(str(bak_file), {"n": 0}, encrypted=True, passphrase="secret")

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_journal_save_artifacts_at_startup()

    assert bak_file.is_file()


def test_after_journal_open_drops_mismatched_bak(tmp_path):
    pytest.importorskip("cryptography")
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    passphrase = "open-me"
    payload = _minimal_v2_payload()
    save_data_file(str(data_file), payload, encrypted=True, passphrase=passphrase)
    save_data_file(str(bak_file), {"plain": True}, encrypted=False, passphrase=None)

    load_data_file(str(data_file), passphrase)
    drop_mismatched_journal_backup_after_journal_open(str(data_file))
    assert not bak_file.exists()


def test_after_journal_open_keeps_matching_format_bak(tmp_path):
    pytest.importorskip("cryptography")
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    passphrase = "same"
    save_data_file(str(data_file), {"n": 1}, encrypted=True, passphrase=passphrase)
    save_data_file(str(data_file), {"n": 2}, encrypted=True, passphrase=passphrase)
    assert bak_file.is_file()
    load_data_file(str(data_file), passphrase)
    drop_mismatched_journal_backup_after_journal_open(str(data_file))
    assert bak_file.is_file()


def test_cancelled_unlock_leaves_mismatched_bak(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    data_path = tmp_path / "profiles" / "default" / "data.json"
    data_path.parent.mkdir(parents=True)
    bak_file = data_path.parent / "data.json.bak"
    app_dir = tmp_path / "integral-home"
    app_dir.mkdir()
    config = {
        "active_profile_id": "default",
        "profiles": [{"id": "default", "name": "Default"}],
    }
    with open(app_dir / "config.json", "w", encoding="utf-8") as handle:
        json.dump(config, handle)

    import paths
    import profiles

    monkeypatch.setattr(paths, "user_data_dir", lambda: str(app_dir))
    monkeypatch.setattr(profiles, "get_app_dir", lambda: str(app_dir))
    monkeypatch.setattr(paths, "data_file", lambda: str(data_path))
    personal_dev_tracker.DATA_FILE = str(data_path)

    good = _minimal_v2_payload()
    _corrupt_live_envelope_ciphertext(data_path, "live-pass", good)
    save_data_file(str(bak_file), good, encrypted=False, passphrase=None)

    sweep_journal_save_artifacts_at_startup()
    assert bak_file.is_file()

    root = tk.Tk()
    root.withdraw()
    try:
        with patch("personal_dev_tracker.prompt_vault_unlock", return_value=False):
            personal_dev_tracker.PersonalDevelopmentTracker(root)
            pump_tk(root, steps=3)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

    assert bak_file.is_file()


def test_failed_unlock_leaves_mismatched_bak(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    data_path = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    good = _minimal_v2_payload()
    _corrupt_live_envelope_ciphertext(data_path, "correct", good)
    save_data_file(str(bak_file), good, encrypted=False, passphrase=None)

    import paths

    monkeypatch.setattr(paths, "data_file", lambda: str(data_path))
    personal_dev_tracker.DATA_FILE = str(data_path)

    root = tk.Tk()
    root.withdraw()
    try:
        with patch("personal_dev_tracker.prompt_vault_unlock", return_value=False):
            personal_dev_tracker.PersonalDevelopmentTracker(root)
            pump_tk(root, steps=3)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

    assert bak_file.is_file()


def test_second_launch_without_unlock_still_has_bak(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    data_path = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    good = _minimal_v2_payload()
    _corrupt_live_envelope_ciphertext(data_path, "correct", good)
    save_data_file(str(bak_file), good, encrypted=False, passphrase=None)

    import paths

    monkeypatch.setattr(paths, "data_file", lambda: str(data_path))
    personal_dev_tracker.DATA_FILE = str(data_path)

    def _quit_unlock(_tracker):
        return False

    for _ in range(2):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch("personal_dev_tracker.prompt_vault_unlock", side_effect=_quit_unlock):
                personal_dev_tracker.PersonalDevelopmentTracker(root)
                pump_tk(root, steps=3)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass
        sweep_journal_save_artifacts_at_startup()
        assert bak_file.is_file()


def test_after_save_backstop_still_drops_mismatched_bak(tmp_path):
    pytest.importorskip("cryptography")
    from vault import drop_opposite_format_journal_backup

    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    save_data_file(str(data_file), {"plain": 1}, encrypted=False, passphrase=None)
    save_data_file(str(bak_file), {"enc": 1}, encrypted=True, passphrase="secret")
    assert bak_file.is_file()

    drop_opposite_format_journal_backup(str(data_file), encrypted=False)
    assert not bak_file.exists()


def test_tracker_open_drops_mismatched_bak_after_unlock(tmp_path, monkeypatch, tk_root):
    pytest.importorskip("cryptography")
    passphrase = "tracker-open"
    data_path = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    payload = _minimal_v2_payload()
    payload["settings"]["encryption_enabled"] = True
    save_data_file(str(data_path), payload, encrypted=True, passphrase=passphrase)
    with open(bak_file, "w", encoding="utf-8") as handle:
        json.dump({"orphan": True}, handle, indent=2)

    import paths

    monkeypatch.setattr(paths, "data_file", lambda: str(data_path))
    personal_dev_tracker.DATA_FILE = str(data_path)

    def _unlock(tracker):
        tracker.vault_passphrase = passphrase
        return True

    with patch("personal_dev_tracker.prompt_vault_unlock", side_effect=_unlock):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    pump_tk(tk_root, steps=5)
    wait_for_tracker_save_idle(tracker)
    if bak_file.is_file():
        with open(bak_file, encoding="utf-8") as handle:
            assert json.load(handle) != {"orphan": True}
