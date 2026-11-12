"""UI-path regression tests for backup dialog worker callbacks (#275 tester)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import personal_dev_tracker
from backup_dialog_ui import (
    BACKUP_WRONG_FILE_MSG,
    GENERIC_BACKUP_ERROR,
    _safe_user_error,
)
import paths

import personal_dev_tracker as pdt_mod
from tests.conftest import pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import WrongPassphraseError


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
    _real_after = tk.Misc.after

    def _immediate_after(self, ms, func=None, *args):
        if ms == 0 and func is not None:
            return func(*args)
        return _real_after(self, ms, func, *args)

    monkeypatch.setattr(tk.Misc, "after", _immediate_after)


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


def test_worker_error_callback_survives_after_except_block():
    callbacks: list = []

    def after(_ms, fn):
        callbacks.append(fn)

    root = MagicMock()
    root.after = after

    def worker():
        try:
            raise OSError("simulated")
        except BaseException as exc:
            root.after(0, lambda e=exc: e)

    worker()
    assert len(callbacks) == 1
    assert isinstance(callbacks[0](), OSError)


def test_safe_user_error_is_generic_for_oserror():
    assert _safe_user_error(OSError("/secret/path"), context="backup") == GENERIC_BACKUP_ERROR


def test_finish_decrypt_wrong_passphrase_message():
    msg = _safe_user_error(
        WrongPassphraseError("That passphrase didn't work for this backup."),
        context="restore",
    )
    assert msg == "That passphrase didn't work for this backup."


def _label_texts(dialog) -> list[str]:
    texts: list[str] = []
    for w in _walk(dialog):
        if isinstance(w, (tk.Label, ttk.Label)):
            try:
                text = str(w.cget("text"))
            except tk.TclError:
                continue
            if text.strip():
                texts.append(text)
    return texts


def _find_button(dialog, substring: str, *, exclude: str | None = None):
    needle = substring.replace("&", "")
    for w in _walk(dialog):
        if w.winfo_class() != "TButton":
            continue
        text = str(w.cget("text")).replace("&", "")
        if exclude and exclude in text:
            continue
        if needle in text:
            return w
    raise AssertionError(f"No button matching {substring!r}")


def test_encrypted_export_success_banner_extra_actions(tk_root, temp_app, tmp_path, immediate_threads):  # noqa: F811
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = False
    tracker.vault_passphrase = None
    banner = tracker.ensure_status_banner()

    out_enc = str(tmp_path / "out.integral-backup.enc")
    export_mock = MagicMock(return_value={"encrypted": True})
    with (
        patch("backup_dialog_ui.filedialog.asksaveasfilename", return_value=out_enc),
        patch("backup_dialog_ui.backup.export_backup", export_mock),
        patch("backup_dialog_ui.profile_journal_sync.sync_tracker_journal_to_active_profile"),
        patch("backup_dialog_ui.integral_io.write_full_backup", side_effect=AssertionError("plain export")),
    ):
        backup_dialog_ui.show_backup_dialog(tracker)
        pump_tk(tk_root)
        dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
        encrypt_chk = next(
            w for w in _walk(dialog) if w.winfo_class() == "TCheckbutton" and "Encrypt" in str(w.cget("text"))
        )
        if not encrypt_chk.instate(["selected"]):
            encrypt_chk.invoke()
        pump_tk(tk_root, 10)
        for chk in _walk(dialog):
            if chk.winfo_class() == "TCheckbutton" and "Use my vault" in str(chk.cget("text")) and chk.instate(["selected"]):
                chk.invoke()
        pump_tk(tk_root, 5)
        typed = [w for w in _walk(dialog) if isinstance(w, ttk.Entry)]
        for entry in typed[:2]:
            entry.delete(0, tk.END)
            entry.insert(0, "twelve-char-pp")
        _find_button(dialog, "Backup", exclude="unencrypted").invoke()
        pump_tk(tk_root, 20)

    export_mock.assert_called_once()
    assert banner._kind == "success"
    assert "Backup saved (encrypted)" in banner._message_var.get()
    for frame in [banner._frame]:
        if frame is None:
            continue
        for widget in _walk(frame):
            if widget.winfo_class() == "TButton" and widget.cget("text") == "Open folder":
                return
    pytest.fail("Open folder action missing from success banner")


def test_vault_autotry_wrong_passphrase_packs_restore_panel(tk_root, tmp_path, temp_app, immediate_threads):  # noqa: F811
    enc = str(tmp_path / "vault.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    _seed_data_file(_minimal_v2_payload())
    passphrase = "vault-secret-twelve"
    with patch("personal_dev_tracker.prompt_vault_unlock") as unlock:

        def _set_pass(tr):
            tr.vault_passphrase = passphrase
            return True

        unlock.side_effect = _set_pass
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = passphrase
    tracker.ensure_status_banner()
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    for chk in _walk(dialog):
        if chk.winfo_class() == "TCheckbutton" and "Use my vault" in str(chk.cget("text")):
            if not chk.instate(["selected"]):
                chk.invoke()
    pump_tk(tk_root, 5)
    val_calls: list[int] = []
    real_validate = backup.validate_backup

    def _counting_validate(*args, **kwargs):
        val_calls.append(1)
        return real_validate(*args, **kwargs)

    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc):
        with patch("backup_dialog_ui.backup.validate_backup", side_effect=_counting_validate):
            _find_button(dialog, "Restore from").invoke()
            pump_tk(tk_root, 20)

    assert val_calls, "vault auto-try should call validate_backup"
    joined = " ".join(_label_texts(dialog))
    assert "Restore passphrase" in joined
    assert (
        "That passphrase didn't work for this backup." in joined
        or BACKUP_WRONG_FILE_MSG in joined
    )


def test_truncated_encrypted_shows_generic_restore_error(tk_root, tmp_path, immediate_threads):
    bad = tmp_path / "trunc.enc"
    bad.write_bytes(backup.ENCRYPTED_BACKUP_MAGIC + b"\x01\x00\x00\x00\x00")
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = False
    tracker.vault_passphrase = None
    banner = tracker.ensure_status_banner()
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    for chk in _walk(dialog):
        if chk.winfo_class() == "TCheckbutton" and "Use my vault" in str(chk.cget("text")) and chk.instate(["selected"]):
            chk.invoke()
        if chk.winfo_class() == "TCheckbutton" and "Encrypt" in str(chk.cget("text")) and chk.instate(["selected"]):
            chk.invoke()

    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=str(bad)):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 40)

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
    restore_entry.focus_set()
    val_calls: list[int] = []

    def _raise_invalid(*_args, **_kwargs):
        val_calls.append(1)
        raise ValueError("Not a valid Integral backup file.")

    with patch("backup_dialog_ui.backup.validate_backup", side_effect=_raise_invalid):
        _find_button(dialog, "Continue").invoke()
        pump_tk(tk_root, 20)
    assert val_calls, "Continue should submit restore passphrase and call validate_backup"
    pump_tk_until(
        tk_root,
        lambda: BACKUP_WRONG_FILE_MSG in (banner._message_var.get() or ""),
        timeout_s=3.0,
    )
    assert BACKUP_WRONG_FILE_MSG in banner._message_var.get()


def test_encrypted_export_worker_error_shows_generic_banner(tk_root, temp_app, tmp_path, immediate_threads):  # noqa: F811
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = False
    tracker.vault_passphrase = None
    banner = tracker.ensure_status_banner()
    out_enc = str(tmp_path / "fail.enc")
    with (
        patch("backup_dialog_ui.filedialog.asksaveasfilename", return_value=out_enc),
        patch("backup_dialog_ui.backup.export_backup", side_effect=OSError("simulated")),
        patch("backup_dialog_ui.integral_io.write_full_backup", side_effect=AssertionError("plain export")),
    ):
        backup_dialog_ui.show_backup_dialog(tracker)
        pump_tk(tk_root)
        dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
        encrypt_chk = next(
            w for w in _walk(dialog) if w.winfo_class() == "TCheckbutton" and "Encrypt" in str(w.cget("text"))
        )
        if not encrypt_chk.instate(["selected"]):
            encrypt_chk.invoke()
        for entry in [w for w in _walk(dialog) if isinstance(w, ttk.Entry)][:2]:
            entry.insert(0, "twelve-char-pp")
        _find_button(dialog, "Backup", exclude="unencrypted").invoke()
        pump_tk(tk_root, 20)
    assert banner._kind == "error"
    assert GENERIC_BACKUP_ERROR in banner._message_var.get()


def test_encrypted_import_worker_error_shows_generic_banner(tk_root, tmp_path, temp_app, immediate_threads):  # noqa: F811
    from backup_dialog_ui import GENERIC_RESTORE_ERROR

    enc = str(tmp_path / "good.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    banner = tracker.ensure_status_banner()
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    for chk in _walk(dialog):
        if chk.winfo_class() == "TCheckbutton" and "Use my vault" in str(chk.cget("text")) and chk.instate(["selected"]):
            chk.invoke()
        if chk.winfo_class() == "TCheckbutton" and "Encrypt" in str(chk.cget("text")) and chk.instate(["selected"]):
            chk.invoke()
    manifest = {"exported_at": "2026-01-01T00:00:00", "profiles": ["default"]}
    with (
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc),
        patch("backup_dialog_ui.backup.validate_backup", return_value=manifest),
        patch("backup_dialog_ui.backup.import_backup", side_effect=OSError("simulated")),
        patch("backup_dialog_ui.prepare_restore_apply", return_value=True),
        patch("backup_dialog_ui._snapshot_journal_if_present", return_value=None),
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
        assert "backup from" in " ".join(_label_texts(dialog)).lower()
        _find_button(dialog, "Restore", exclude="from").invoke()
        pump_tk_until(
            tk_root,
            lambda: GENERIC_RESTORE_ERROR in (banner._message_var.get() or ""),
            timeout_s=3.0,
        )
    assert GENERIC_RESTORE_ERROR in banner._message_var.get()


def test_escape_on_restore_passphrase_cancels_only_that_flow(tk_root, temp_app, tmp_path):  # noqa: F811
    enc = str(tmp_path / "e.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 20)
    assert "Restore passphrase" in " ".join(_label_texts(dialog))
    dialog.event_generate("<Escape>")
    pump_tk(tk_root, 10)
    assert dialog.winfo_exists()
    restore_entries = [w for w in _walk(dialog) if isinstance(w, ttk.Entry) and w.winfo_ismapped()]
    assert not restore_entries
