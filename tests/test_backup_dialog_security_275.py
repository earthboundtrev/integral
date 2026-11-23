"""Security fixes for backup dialog restore/save ordering (#275)."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography")

import backup_dialog_ui
import paths
import personal_dev_tracker
import profile_journal_sync
import profiles
import storage
from backup_dialog_ui import (
    GENERIC_REENCRYPT_ERROR,
    _rollback_journal_copies,
    _rollback_journal_from_snapshot,
    _snapshot_journal_if_present,
    prepare_restore_apply,
    reencrypt_restored_journal_from_disk,
    resolve_export_passphrase,
    save_data_file,
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


def test_reencrypt_encrypts_tracker_and_profile_journal(temp_app):
    import os

    profiles.set_active_profile("default")
    _seed_data_file(_minimal_v2_payload())
    tracker_path = paths.data_file()
    profile_path = profile_journal_sync.resolved_active_profile_data_path()
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    plain = storage.empty_data()
    plain["entries"]["2099-03-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "both"}
    }
    payload = json.dumps(plain)
    for path in (tracker_path, profile_path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(payload)

    tracker = MagicMock()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = "vault-passphrase-12"
    tracker.data_path = tracker_path

    assert reencrypt_restored_journal_from_disk(tracker)[0] is True
    assert is_encrypted_file(tracker_path)
    assert is_encrypted_file(profile_path)


def test_reencrypt_failure_leaves_profile_without_restored_plaintext(temp_app):
    import os

    profiles.set_active_profile("default")
    _seed_data_file(_minimal_v2_payload())
    tracker_path = paths.data_file()
    profile_path = profile_journal_sync.resolved_active_profile_data_path()
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    prior = storage.empty_data()
    prior["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 3, "checklist": {}, "metrics": {}, "notes": "prior"}
    }
    restored = storage.empty_data()
    restored["entries"]["2099-02-01"] = {
        "Emotional Wellbeing": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "restored-plain"}
    }
    for path in (tracker_path, profile_path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(prior, handle)
    journal_snap = _snapshot_journal_if_present(tracker_path)
    profile_snap = _snapshot_journal_if_present(profile_path)
    for path in (tracker_path, profile_path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(restored, handle)

    tracker = MagicMock()
    tracker.settings = {"encryption_enabled": True}
    tracker.vault_passphrase = "vault-passphrase-12"
    tracker.data_path = tracker_path

    call_paths: list[str] = []

    def flaky_save(path, payload, **kwargs):
        call_paths.append(path)
        if len(call_paths) >= 2:
            raise OSError("fail second file")
        return save_data_file(path, payload, **kwargs)
    with patch("backup_dialog_ui.save_data_file", side_effect=flaky_save):
        ok, msg = reencrypt_restored_journal_from_disk(tracker)
    assert ok is False
    assert msg == GENERIC_REENCRYPT_ERROR
    _rollback_journal_from_snapshot(tracker_path, journal_snap)
    _rollback_journal_from_snapshot(profile_path, profile_snap)
    assert not is_encrypted_file(tracker_path)
    with open(profile_path, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert "2099-02-01" not in on_disk.get("entries", {})
    assert on_disk["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "prior"
    assert not is_encrypted_file(profile_path)


def test_reencrypt_failure_removes_profile_journal_without_prior_file(temp_app):
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
    var_name = vault_checks[0].cget("variable")
    assert var_name
    dialog.setvar(var_name, False)
    pump_tk(tk_root)
    assert not vault_checks[0].instate(["selected"])
    dialog.setvar(var_name, True)
    pump_tk(tk_root)
    assert vault_checks[0].instate(["selected"])


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
