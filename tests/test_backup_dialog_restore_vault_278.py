"""Vault-on restore without session passphrase (#278)."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import integral_io
import paths
import personal_dev_tracker
import profile_journal_sync
import profiles
import storage
from backup_dialog_ui import (
    GENERIC_REENCRYPT_ERROR,
    VAULT_WRONG_PASSPHRASE_MSG,
    reencrypt_restored_journal_from_disk,
    verify_vault_passphrase_for_restore,
)
from tests.conftest import create_tk_root, pump_tk, pump_tk_until
from vault import encrypt_payload
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import is_encrypted_file, save_data_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


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
    root = create_tk_root(withdraw=True)
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _vault_on_locked_tracker(tk_root, *, passphrase: str = "vault-secret-12"):
    payload = _minimal_v2_payload()
    payload["settings"]["encryption_enabled"] = True
    _seed_data_file(payload, encrypted=False, passphrase=None)
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = None
    tracker.ensure_status_banner()
    return tracker


def test_reencrypt_fails_without_passphrase_when_vault_on_plaintext(temp_app):
    profiles.set_active_profile("default")
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(storage.empty_data(), handle)

    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = None
    tracker.data_path = data_path

    ok, msg = reencrypt_restored_journal_from_disk(tracker)  # type: ignore[arg-type]
    assert ok is False
    assert msg == GENERIC_REENCRYPT_ERROR
    assert not is_encrypted_file(data_path)


def test_verify_vault_passphrase_wrong_against_encrypted_bak(temp_app):
    passphrase = "vault-secret-12"
    wrong = "wrong-pass-xx"
    profiles.set_active_profile("default")
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    plain = storage.empty_data()
    save_data_file(data_path, plain, encrypted=True, passphrase=passphrase)

    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.data_path = data_path

    ok, msg = verify_vault_passphrase_for_restore(tracker, wrong)  # type: ignore[arg-type]
    assert ok is False
    assert msg == VAULT_WRONG_PASSPHRASE_MSG
    assert passphrase not in (msg or "")


def test_verify_vault_passphrase_accepts_when_all_plaintext(temp_app):
    profiles.set_active_profile("default")
    data_path = paths.data_file()
    _seed_data_file(_minimal_v2_payload())
    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.data_path = data_path
    ok, msg = verify_vault_passphrase_for_restore(tracker, "vault-secret-12")  # type: ignore[arg-type]
    assert ok is True
    assert msg is None


def test_plaintext_legacy_restore_prompts_vault_before_apply(
    tk_root, temp_app, tmp_path, immediate_threads,
):
    prior_marker = "prior-journal-marker"
    payload = _minimal_v2_payload()
    payload["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": prior_marker}
    }
    _seed_data_file(payload, encrypted=False, passphrase=None)
    data_path = paths.data_file()

    plain_zip = str(tmp_path / "plain.zip")
    backup.export_backup(plain_zip, profile_id="default")

    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = None
    banner = tracker.ensure_status_banner()
    prior_text = open(data_path, encoding="utf-8").read()
    prior_payload = json.loads(prior_text)
    bak_envelope = encrypt_payload(prior_payload, "vault-secret-12")
    with open(f"{data_path}.bak", "w", encoding="utf-8") as handle:
        json.dump(bak_envelope, handle, indent=2)

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=plain_zip):
        with patch("tkinter.messagebox.askyesno", return_value=True):
            _find_button(dialog, "Restore from").invoke()
            pump_tk(tk_root, 15)

    joined = " ".join(_label_texts(dialog))
    assert "Vault passphrase" in joined

    vault_entry = None
    for w in _walk(dialog):
        if not isinstance(w, ttk.Entry):
            continue
        for sib in w.master.winfo_children():
            if isinstance(sib, ttk.Label) and "Vault passphrase" in str(sib.cget("text")):
                vault_entry = w
                break
    assert vault_entry is not None
    assert prior_marker in prior_text
    assert prior_marker in open(data_path, encoding="utf-8").read()

    vault_continue = next(
        w
        for w in vault_entry.master.winfo_children()
        if w.winfo_class() == "TButton" and str(w.cget("text")) == "Continue"
    )
    vault_entry.insert(0, "wrong-pass-xx")
    vault_continue.invoke()
    pump_tk(tk_root, 10)
    assert VAULT_WRONG_PASSPHRASE_MSG in " ".join(_label_texts(dialog))
    assert prior_marker in open(data_path, encoding="utf-8").read()
    assert banner._kind != "success"

    vault_entry.delete(0, tk.END)
    vault_entry.insert(0, "vault-secret-12")
    vault_continue.invoke()
    pump_tk(tk_root, 30)

    pump_tk_until(tk_root, lambda: is_encrypted_file(data_path), timeout_s=5.0)
    assert is_encrypted_file(data_path)
    pump_tk_until(tk_root, lambda: banner._kind == "success", timeout_s=5.0)
    assert "Journal restored from backup." in (banner._message_var.get() or "")
    assert "vault-secret-12" not in (banner._message_var.get() or "")


def test_plaintext_restore_no_success_leaves_journal_plain_when_vault_unlock_cancelled(
    tk_root, temp_app, tmp_path,
):
    plain_json = tmp_path / "legacy.json"
    integral_io.write_backup(storage.empty_data(), str(plain_json))
    tracker = _vault_on_locked_tracker(tk_root)
    banner = tracker.ensure_status_banner()
    data_path = paths.data_file()
    assert not is_encrypted_file(data_path)

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=str(plain_json)):
        with patch("tkinter.messagebox.askyesno", return_value=True):
            _find_button(dialog, "Restore from").invoke()
            pump_tk(tk_root, 15)

    _find_button(dialog, "Back").invoke()
    pump_tk(tk_root, 10)

    assert not is_encrypted_file(data_path)
    assert banner._kind != "success"


def test_vault_unlocked_plaintext_restore_still_reencrypts(temp_app, tmp_path):
    """Regression: #268 rule — unlocked vault still re-encrypts plaintext restore."""
    passphrase = "vault-secret-12"
    plain_zip = str(tmp_path / "plain.zip")
    backup.export_backup(plain_zip, profile_id="default")
    data_path = paths.data_file()
    _seed_data_file(_minimal_v2_payload(), encrypted=False, passphrase=None)

    profiles.set_active_profile("default")
    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = passphrase
    tracker.data_path = data_path

    backup.import_backup(plain_zip, merge_profiles=True)
    assert not is_encrypted_file(data_path)
    ok, msg = reencrypt_restored_journal_from_disk(tracker)  # type: ignore[arg-type]
    assert ok is True
    assert msg is None
    assert is_encrypted_file(data_path)