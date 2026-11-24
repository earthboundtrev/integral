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
import safety_backup
import integral_io
import paths
import personal_dev_tracker
import profile_journal_sync
import profiles
import storage
from backup_dialog_ui import (
    GENERIC_REENCRYPT_ERROR,
    VAULT_PASSPHRASE_MISMATCH_MSG,
    VAULT_WRONG_PASSPHRASE_MSG,
    reencrypt_restored_journal_from_disk,
    vault_restore_needs_passphrase_confirmation,
    verify_vault_passphrase_for_restore,
)
from vault import load_data_file
from tests.conftest import create_tk_root, pump_tk, pump_tk_until
from vault import encrypt_payload
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import is_encrypted_file, save_data_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


@pytest.fixture(autouse=True)
def _restore_apply_ready(monkeypatch):
    monkeypatch.setattr(backup_dialog_ui, "prepare_restore_apply", lambda _tracker: True)


@pytest.fixture(autouse=True)
def _skip_dashboard_rebuild(monkeypatch):
    monkeypatch.setattr(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "create_dashboard",
        lambda self: None,
    )


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


def _day_notes(payload: dict, day: str = "2099-01-01") -> str:
    return payload["entries"][day]["Emotional Wellbeing"]["notes"]


def _payload_with_marker(marker: str, *, day: str = "2099-01-01") -> dict:
    payload = _minimal_v2_payload()
    payload["entries"][day] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": marker}
    }
    return payload


def _vault_continue_button(dialog: tk.Toplevel) -> tk.Misc:
    back_btn = None
    for w in _walk(dialog):
        if w.winfo_class() != "TButton":
            continue
        if str(w.cget("text")).replace("&", "") != "Back":
            continue
        vault_entry, _ = _vault_unlock_entries(dialog)
        if vault_entry is None:
            continue
        if w.master is vault_entry.master:
            continue
        if w.master.master is not vault_entry.master.master:
            continue
        back_btn = w
        break
    if back_btn is None:
        raise AssertionError("vault unlock Back button not found")
    for sib in back_btn.master.winfo_children():
        if sib.winfo_class() != "TButton":
            continue
        if "Continue" in str(sib.cget("text")).replace("&", ""):
            return sib
    raise AssertionError("vault unlock Continue button not found")


def _vault_unlock_entries(dialog):
    vault_entry = vault_confirm = None
    for w in _walk(dialog):
        if not isinstance(w, ttk.Entry):
            continue
        labels = [
            str(c.cget("text"))
            for c in w.master.winfo_children()
            if isinstance(c, (tk.Label, ttk.Label))
        ]
        if any("Vault passphrase" in text for text in labels):
            vault_entry = w
        if any(text == "Confirm vault passphrase" for text in labels):
            vault_confirm = w
    return vault_entry, vault_confirm


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


def test_vault_restore_needs_confirmation_when_all_plaintext(temp_app):
    profiles.set_active_profile("default")
    _seed_data_file(_minimal_v2_payload())
    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.data_path = paths.data_file()
    assert vault_restore_needs_passphrase_confirmation(tracker) is True  # type: ignore[arg-type]


def test_verify_vault_passphrase_all_plaintext_requires_matching_confirm(temp_app):
    profiles.set_active_profile("default")
    data_path = paths.data_file()
    _seed_data_file(_minimal_v2_payload())
    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.data_path = data_path

    ok, msg = verify_vault_passphrase_for_restore(  # type: ignore[arg-type]
        tracker, "vault-secret-12", confirm_passphrase="vault-secret-12"
    )
    assert ok is True
    assert msg is None

    ok, msg = verify_vault_passphrase_for_restore(  # type: ignore[arg-type]
        tracker, "vault-secret-12", confirm_passphrase="vault-secret-13"
    )
    assert ok is False
    assert msg == VAULT_PASSPHRASE_MISMATCH_MSG
    assert "vault-secret" not in (msg or "")

    ok, msg = verify_vault_passphrase_for_restore(tracker, "vault-secret-12")  # type: ignore[arg-type]
    assert ok is False
    assert msg is not None


def test_plaintext_vault_unlock_mismatch_never_reencrypts_or_sets_session(
    tk_root, temp_app, tmp_path,
):
    plain_zip = str(tmp_path / "plain.zip")
    backup.export_backup(plain_zip, profile_id="default")
    _seed_data_file(_minimal_v2_payload(), encrypted=False, passphrase=None)
    data_path = paths.data_file()

    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = None

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    with (
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=plain_zip),
        patch("backup_dialog_ui.save_data_file") as mock_save,
    ):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 15)

    assert safety_backup.UNLOCK_VAULT_FIRST_MSG in " ".join(_label_texts(dialog))
    mock_save.assert_not_called()

    tracker.vault_passphrase = "vault-secret-12"
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=plain_zip):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 12)
    _find_button(dialog, "Restore", exclude="from").invoke()
    pump_tk(tk_root, 20)
    assert tracker.vault_passphrase == "vault-secret-12"


def test_plaintext_vault_unlock_matching_confirm_restores_and_encrypts(
    tk_root, temp_app, tmp_path,
):
    plain_zip = str(tmp_path / "plain.zip")
    backup.export_backup(plain_zip, profile_id="default")
    _seed_data_file(_minimal_v2_payload(), encrypted=False, passphrase=None)
    data_path = paths.data_file()
    passphrase = "vault-secret-12"

    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = None
    banner = tracker.ensure_status_banner()

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    tracker.vault_passphrase = passphrase
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=plain_zip):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 15)
    _find_button(dialog, "Restore", exclude="from").invoke()
    pump_tk(tk_root, 30)

    pump_tk_until(tk_root, lambda: is_encrypted_file(data_path), timeout_s=5.0)
    assert is_encrypted_file(data_path)
    pump_tk_until(tk_root, lambda: banner._kind == "success", timeout_s=5.0)
    assert passphrase not in (banner._message_var.get() or "")


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
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 15)
    assert safety_backup.UNLOCK_VAULT_FIRST_MSG in " ".join(_label_texts(dialog))

    tracker.vault_passphrase = "vault-secret-12"
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=plain_zip):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 15)
    assert prior_marker in open(data_path, encoding="utf-8").read()
    _find_button(dialog, "Restore", exclude="from").invoke()
    pump_tk(tk_root, 30)

    pump_tk_until(tk_root, lambda: is_encrypted_file(data_path), timeout_s=5.0)
    assert is_encrypted_file(data_path)
    pump_tk_until(tk_root, lambda: banner._kind == "success", timeout_s=5.0)
    assert "Restored." in (banner._message_var.get() or "")
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
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 15)

    assert safety_backup.UNLOCK_VAULT_FIRST_MSG in " ".join(_label_texts(dialog))

    assert not is_encrypted_file(data_path)
    assert banner._kind != "success"


def _seed_tracker_and_profile(payload: dict) -> str:
    data_path = _seed_data_file(payload)
    profile_path = profile_journal_sync.resolved_active_profile_data_path()
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    with open(profile_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return data_path


def _write_stale_journals(stale_marker: str) -> str:
    profiles.set_active_profile("default")
    stale = _minimal_v2_payload()
    stale["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": stale_marker}
    }
    profile_path = profile_journal_sync.resolved_active_profile_data_path()
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    for path in (profile_path, data_path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(stale, handle)
    return data_path


def test_legacy_json_restore_keeps_backup_notes_with_stale_profile(temp_app, tmp_path):
    backup_marker = "legacy-json-backup-notes"
    stale_marker = "stale-profile-before-restore"
    vault_pw = "vault-secret-12"
    legacy = tmp_path / "legacy.json"
    integral_io.write_backup(_payload_with_marker(backup_marker), str(legacy))
    data_path = _write_stale_journals(stale_marker)

    integral_io.restore_backup_file(
        str(legacy),
        data_path,
        creative_root=None,
        fitness_db_path=None,
        make_copy=True,
    )
    profile_journal_sync.sync_tracker_journal_to_active_profile(data_path)

    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = vault_pw
    tracker.data_path = data_path

    ok, msg = reencrypt_restored_journal_from_disk(tracker)  # type: ignore[arg-type]
    assert ok is True
    assert msg is None
    restored = load_data_file(data_path, vault_pw)
    assert _day_notes(restored) == backup_marker
    assert stale_marker not in json.dumps(restored)


def test_legacy_json_wrong_sync_direction_restores_stale_notes(temp_app, tmp_path):
    backup_marker = "legacy-json-backup-notes"
    stale_marker = "stale-profile-before-restore"
    legacy = tmp_path / "legacy.json"
    integral_io.write_backup(_payload_with_marker(backup_marker), str(legacy))
    data_path = _write_stale_journals(stale_marker)

    integral_io.restore_backup_file(
        str(legacy),
        data_path,
        creative_root=None,
        fitness_db_path=None,
        make_copy=True,
    )
    profile_journal_sync.sync_active_profile_journal_to_tracker(data_path)

    with open(data_path, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert _day_notes(on_disk, day="2000-01-01") == stale_marker
    assert backup_marker not in json.dumps(on_disk)


def test_profile_zip_restore_keeps_backup_notes_with_stale_profile(temp_app, tmp_path):
    backup_marker = "zip-backup-notes"
    stale_marker = "stale-profile-before-restore"
    vault_pw = "vault-secret-12"
    _seed_tracker_and_profile(_payload_with_marker(backup_marker))
    plain_zip = str(tmp_path / "plain.zip")
    backup.export_backup(plain_zip, profile_id="default")
    data_path = _write_stale_journals(stale_marker)

    backup.import_backup(plain_zip, merge_profiles=True)
    profile_journal_sync.sync_active_profile_journal_to_tracker(data_path)

    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = vault_pw
    tracker.data_path = data_path

    ok, msg = reencrypt_restored_journal_from_disk(tracker)  # type: ignore[arg-type]
    assert ok is True
    assert msg is None
    restored = load_data_file(data_path, vault_pw)
    assert _day_notes(restored) == backup_marker
    assert stale_marker not in json.dumps(restored)


def test_encrypted_backup_restore_keeps_backup_notes_with_stale_profile(temp_app, tmp_path):
    backup_marker = "encrypted-backup-notes"
    stale_marker = "stale-profile-before-restore"
    vault_pw = "vault-secret-12"
    container_pw = "twelve-char-pp"
    _seed_tracker_and_profile(_payload_with_marker(backup_marker))
    enc = str(tmp_path / "vault.enc")
    backup.export_backup(enc, profile_id="default", passphrase=container_pw)
    data_path = _write_stale_journals(stale_marker)

    backup.import_backup(enc, merge_profiles=True, passphrase=container_pw)
    profile_journal_sync.sync_active_profile_journal_to_tracker(data_path)

    tracker = type("T", (), {})()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = vault_pw
    tracker.data_path = data_path

    ok, msg = reencrypt_restored_journal_from_disk(tracker)  # type: ignore[arg-type]
    assert ok is True
    assert msg is None
    restored = load_data_file(data_path, vault_pw)
    assert _day_notes(restored) == backup_marker
    assert stale_marker not in json.dumps(restored)


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