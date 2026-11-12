"""End-to-end restore rollback when profile journal did not exist before (#275)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import personal_dev_tracker
import profile_journal_sync
import profiles
import storage
from backup_dialog_ui import GENERIC_REENCRYPT_ERROR
import paths
import personal_dev_tracker as pdt_mod
from tests.conftest import pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(pdt_mod, "DATA_FILE", paths.data_file())


@pytest.fixture
def immediate_threads(monkeypatch):
    class _ImmediateThread:
        def __init__(self, target=None, daemon=None, args=(), kwargs=None):
            self._target = target

        def start(self) -> None:
            if self._target:
                self._target()

    monkeypatch.setattr(backup_dialog_ui.threading, "Thread", _ImmediateThread)


@pytest.fixture
def tk_root():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_restore_reencrypt_failure_removes_new_profile_journal_ui(
    tk_root, temp_app, tmp_path, immediate_threads,
):
    """UI restore: import succeeds, re-encrypt fails, profile data.json created during restore is removed."""
    enc = str(tmp_path / "vault-restore.enc")
    profiles.set_active_profile("default")
    profile_path = profile_journal_sync.active_profile_journal_path_for_rollback()
    assert profile_path
    if os.path.lexists(profile_path):
        os.remove(profile_path)
    assert not os.path.lexists(profile_path)

    payload = _minimal_v2_payload()
    _seed_data_file(payload)
    backup.export_backup(enc, passphrase="twelve-char-pp")

    with patch("personal_dev_tracker.prompt_vault_unlock") as unlock:

        def _unlock(tr):
            tr.vault_passphrase = "twelve-char-pp"
            return True

        unlock.side_effect = _unlock
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = "twelve-char-pp"
    banner = tracker.ensure_status_banner()

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    with (
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc),
        patch(
            "backup_dialog_ui.reencrypt_restored_journal_from_disk",
            return_value=(False, GENERIC_REENCRYPT_ERROR),
        ),
    ):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 30)
        restore_entry = None
        for w in _walk(dialog):
            if not isinstance(w, ttk.Entry):
                continue
            for sib in w.master.winfo_children():
                if isinstance(sib, ttk.Label) and "Restore passphrase" in str(sib.cget("text")):
                    restore_entry = w
                    break
        assert restore_entry is not None
        restore_entry.delete(0, tk.END)
        restore_entry.insert(0, "twelve-char-pp")
        _find_button(dialog, "Continue").invoke()
        pump_tk(tk_root, 20)
        pump_tk_until(
            tk_root,
            lambda: "backup from" in " ".join(_label_texts(dialog)).lower(),
            timeout_s=3.0,
        )
        _find_button(dialog, "Restore", exclude="from").invoke()
        pump_tk_until(
            tk_root,
            lambda: GENERIC_REENCRYPT_ERROR in (banner._message_var.get() or ""),
            timeout_s=5.0,
        )

    assert GENERIC_REENCRYPT_ERROR in banner._message_var.get()
    assert not os.path.lexists(profile_path)


def test_restore_import_failure_removes_new_profile_journal_ui(
    tk_root, temp_app, tmp_path, immediate_threads,
):
    """UI restore: import fails after creating profile artifacts; rollback removes new profile journal."""
    enc = str(tmp_path / "fail-import.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    profiles.set_active_profile("default")
    profile_path = profile_journal_sync.active_profile_journal_path_for_rollback()
    assert profile_path
    if os.path.lexists(profile_path):
        os.remove(profile_path)
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    banner = tracker.ensure_status_banner()

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    manifest = {"exported_at": "2026-01-01T00:00:00", "profiles": ["default"]}

    call_count = 0

    def import_then_fail(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        backup.import_backup(enc, merge_profiles=True, passphrase="twelve-char-pp")
        raise OSError("simulated post-import failure")

    with (
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc),
        patch("backup_dialog_ui.backup.validate_backup", return_value=manifest),
        patch("backup_dialog_ui.backup.import_backup", side_effect=import_then_fail),
        patch("backup_dialog_ui.prepare_restore_apply", return_value=True),
    ):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 30)
        restore_entry = None
        for w in _walk(dialog):
            if not isinstance(w, ttk.Entry):
                continue
            for sib in w.master.winfo_children():
                if isinstance(sib, ttk.Label) and "Restore passphrase" in str(sib.cget("text")):
                    restore_entry = w
                    break
        restore_entry.delete(0, tk.END)
        restore_entry.insert(0, "twelve-char-pp")
        _find_button(dialog, "Continue").invoke()
        pump_tk(tk_root, 20)
        _find_button(dialog, "Restore", exclude="from").invoke()
        pump_tk_until(tk_root, lambda: call_count > 0, timeout_s=3.0)

    assert not os.path.lexists(profile_path)
