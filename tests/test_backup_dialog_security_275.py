"""Security fixes for backup dialog restore/save ordering (#275)."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography")

import backup_dialog_ui
import paths
import personal_dev_tracker
import storage
from backup_dialog_ui import (
    GENERIC_REENCRYPT_ERROR,
    prepare_restore_apply,
    reencrypt_restored_journal_from_disk,
    resolve_export_passphrase,
    typed_passphrase_error,
)
from tests.conftest import pump_tk
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import is_encrypted_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _walk(parent):
    for child in parent.winfo_children():
        yield child
        yield from _walk(child)


def test_resolve_export_passphrase_prefers_typed_when_vault_unchecked():
    assert (
        resolve_export_passphrase(
            use_vault=False,
            vault_unlocked=True,
            vault_passphrase="vault-secret-twelve",
            typed_passphrase="typed-export-twelve",
        )
        == "typed-export-twelve"
    )


def test_resolve_export_passphrase_uses_vault_when_checked():
    assert (
        resolve_export_passphrase(
            use_vault=True,
            vault_unlocked=True,
            vault_passphrase="vault-secret-twelve",
            typed_passphrase="ignored",
        )
        == "vault-secret-twelve"
    )


def test_typed_passphrase_twelve_character_floor():
    assert typed_passphrase_error("short") is not None
    assert typed_passphrase_error("twelve-char-ok") is None


def test_cancel_pending_save_before_restore_apply(tk_root, temp_app):
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.save_data()
    assert tracker._pending_save_payload is not None
    assert prepare_restore_apply(tracker)
    assert tracker._pending_save_payload is None
    assert tracker._save_after_id is None
    tracker._flush_save(sync=True)
    # No new write scheduled after cancel cleared payload.


def test_reencrypt_reads_disk_not_memory(temp_app):
    import os
    import profiles

    profiles.set_active_profile("default")
    _seed_data_file(_minimal_v2_payload())
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    disk_payload = storage.empty_data()
    disk_payload["entries"]["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "from-disk"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(disk_payload, handle)

    tracker = MagicMock()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = "vault-passphrase-12"
    tracker.data_path = data_path
    tracker._payload = MagicMock(return_value={"entries": {}})

    assert reencrypt_restored_journal_from_disk(tracker)[0] is True
    assert is_encrypted_file(data_path)
    tracker._payload.assert_not_called()


def test_reencrypt_failure_returns_error_not_success(temp_app):
    import os
    import profiles

    profiles.set_active_profile("default")
    _seed_data_file(_minimal_v2_payload())
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    plain = storage.empty_data()
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(plain, handle)

    tracker = MagicMock()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = "vault-passphrase-12"
    tracker.data_path = data_path

    with patch("backup_dialog_ui.save_data_file", side_effect=OSError("fail")):
        ok, msg = reencrypt_restored_journal_from_disk(tracker)
    assert ok is False
    assert msg == GENERIC_REENCRYPT_ERROR


def test_stale_memory_save_not_flushed_after_restore_cancel(temp_app, tk_root):
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.entries = {"stale": {"marker": True}}
    tracker.save_data()
    prepare_restore_apply(tracker)
    written = []

    def capture_save(*_args, **_kwargs):
        written.append("save")

    with patch.object(tracker, "_flush_save", side_effect=capture_save):
        tracker.root.after(300, lambda: tracker._flush_save(sync=False))
        tracker.root.update()
        pump_tk(tk_root, 5)
    assert not written


def test_use_vault_checkbox_bound(tk_root):
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.vault_passphrase = "vault-secret-twelve"
    tracker.settings["encryption_enabled"] = True
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    checks = [w for w in _walk(dialog) if w.winfo_class() == "TCheckbutton"]
    vault_checks = [w for w in checks if "vault passphrase" in str(w.cget("text"))]
    assert vault_checks
    vault_checks[0].invoke()
    assert not vault_checks[0].instate(["selected"])


def test_window_close_clears_passphrases(tk_root):
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    entries = [w for w in _walk(dialog) if isinstance(w, ttk.Entry)]
    for entry in entries:
        entry.insert(0, "clear-me-on-close")
    close_btn = next(
        w
        for w in _walk(dialog)
        if w.winfo_class() == "TButton" and "Close" in str(w.cget("text")).replace("&", "")
    )
    with patch.object(dialog, "destroy"):
        close_btn.invoke()
    pump_tk(tk_root)
    for entry in entries:
        assert entry.get() == ""
