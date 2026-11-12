"""Backup & Restore dialog — encrypted export/import UI (#267, #268)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography", reason="cryptography required for encrypted backup UI tests")

import backup
import backup_dialog_ui
import paths
import personal_dev_tracker
import storage
from backup_dialog_ui import BACKUP_WRONG_FILE_MSG, MARKER_LOG_SCAN, show_backup_dialog
from tests.conftest import pump_tk
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import WrongPassphraseError, is_encrypted_file


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


def _walk_widgets(parent: tk.Misc):
    yield parent
    for child in parent.winfo_children():
        yield from _walk_widgets(child)


def _button_label(text: str) -> str:
    return text.replace("&", "")


def _find_button(root: tk.Misc, text_fragment: str) -> ttk.Button:
    for widget in _walk_widgets(root):
        if widget.winfo_class() == "TButton":
            try:
                label = _button_label(str(widget.cget("text")))
                if text_fragment in label:
                    return widget  # type: ignore[return-value]
            except tk.TclError:
                continue
    raise AssertionError(f"button {text_fragment!r} not found")


def _find_toplevel(root: tk.Misc) -> tk.Toplevel:
    for widget in root.winfo_children():
        if isinstance(widget, tk.Toplevel):
            return widget
    raise AssertionError("backup dialog toplevel not found")


def _tracker(tk_root: tk.Tk, *, encryption_enabled: bool = False, passphrase: str | None = None):
    payload = _minimal_v2_payload()
    payload["settings"]["encryption_enabled"] = encryption_enabled
    _seed_data_file(
        payload,
        encrypted=bool(encryption_enabled and passphrase),
        passphrase=passphrase,
    )

    def _unlock(tracker):
        if passphrase:
            tracker.vault_passphrase = passphrase
            return True
        return not encryption_enabled

    with patch("personal_dev_tracker.prompt_vault_unlock", side_effect=_unlock):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    if passphrase and not tracker.vault_passphrase:
        tracker.vault_passphrase = passphrase
    tracker.ensure_status_banner()
    return tracker


def test_plain_zip_rejects_passphrase_argument(temp_app, tmp_path):
    plain = str(tmp_path / "plain.zip")
    backup.export_backup(plain, profile_id="default")
    with pytest.raises(ValueError, match="unencrypted"):
        backup.validate_backup(plain, passphrase="extra")


def test_encrypted_backup_roundtrip_api(temp_app, tmp_path):
    profiles = __import__("profiles")
    profiles.set_active_profile("default")
    data = storage.load()
    data["entries"]["2026-11-10"] = {
        "Emotional Wellbeing": {"rating": 5, "checklist": {}, "metrics": {}, "notes": "ui-roundtrip"}
    }
    storage.save(data)
    enc = str(tmp_path / f"save{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    storage.save(storage.empty_data())
    backup.import_backup(enc, merge_profiles=True, passphrase="twelve-char-pp")
    restored = storage.load()
    assert restored["entries"]["2026-11-10"]["Emotional Wellbeing"]["notes"] == "ui-roundtrip"


def test_encrypted_detected_without_matching_extension(temp_app, tmp_path):
    profiles = __import__("profiles")
    profiles.set_active_profile("default")
    enc = str(tmp_path / "backup.dat")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    assert backup.is_encrypted_backup_file(enc)
    manifest = backup.validate_backup(enc, passphrase="twelve-char-pp")
    assert manifest.get("profiles")


def test_wrong_passphrase_exact_message(temp_app, tmp_path):
    enc = str(tmp_path / "bad-pass.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    with pytest.raises(WrongPassphraseError, match="That passphrase didn't work for this backup."):
        backup.validate_backup(enc, passphrase="wrong-pass-phrase")


def test_marker_passphrase_not_in_log_or_settings(tk_root, tmp_path, temp_app, monkeypatch):
    log_path = tmp_path / "integral.log"
    monkeypatch.setattr(paths, "app_log_file", lambda: str(log_path))
    tracker = _tracker(tk_root)
    show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = _find_toplevel(tk_root)
    export_btn = _find_button(dialog, "Export Backup")

    dest = str(tmp_path / f"out{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}")

    def fake_save(**_kwargs):
        return None

    with patch.object(tracker, "save_data", side_effect=fake_save):
        with patch("backup_dialog_ui.filedialog.asksaveasfilename", return_value=dest):
            with patch("backup.export_backup", side_effect=ValueError(MARKER_LOG_SCAN)):
                export_btn.invoke()
                pump_tk(tk_root, 40)

    if log_path.is_file():
        assert MARKER_LOG_SCAN not in log_path.read_text(encoding="utf-8", errors="replace")
    settings_text = str(tracker.settings)
    assert MARKER_LOG_SCAN not in settings_text
    for path in tmp_path.rglob("*"):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            assert MARKER_LOG_SCAN not in text


def test_plain_export_still_uses_write_full_backup(tk_root):
    tracker = _tracker(tk_root)
    show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = _find_toplevel(tk_root)
    export_btn = _find_button(dialog, "Export Backup")

    with patch("backup_dialog_ui.filedialog.asksaveasfilename", return_value="/tmp/plain.zip"):
        with patch("backup_dialog_ui.integral_io.write_full_backup", return_value={"creative_file_count": 0, "has_fitness": False}) as mock_write:
            with patch.object(tracker, "save_data"):
                export_btn.invoke()
                pump_tk(tk_root)
    mock_write.assert_called_once()


def test_is_encrypted_backup_shown_in_restore_filetypes(tk_root):
    tracker = _tracker(tk_root)
    show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = _find_toplevel(tk_root)
    captured: dict = {}

    def _askopen(**kwargs):
        captured.update(kwargs)
        return ""

    with patch("backup_dialog_ui.filedialog.askopenfilename", side_effect=_askopen):
        _find_button(dialog, "from Backup").invoke()
    filetypes = str(captured.get("filetypes", ""))
    assert backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX in filetypes


def test_wrong_file_message_constant():
    assert BACKUP_WRONG_FILE_MSG == "This file isn't an Integral backup."


def _mnemonic_letters(dialog: tk.Misc) -> list[str]:
    letters: list[str] = []
    for widget in _walk_widgets(dialog):
        try:
            text = str(widget.cget("text"))
        except tk.TclError:
            continue
        if "&" not in text:
            continue
        idx = text.index("&")
        if idx + 1 < len(text):
            letters.append(text[idx + 1].lower())
    return letters


def test_dialog_alt_accelerators_unique(tk_root):
    tracker = _tracker(tk_root)
    show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = _find_toplevel(tk_root)
    letters = _mnemonic_letters(dialog)
    assert letters
    assert len(letters) == len(set(letters))


def test_vault_on_restore_reencrypts_plaintext_data(tmp_path, temp_app):
    passphrase = "vault-passphrase-12"
    plain_enc = str(tmp_path / "plain-in-backup.enc")
    profiles = __import__("profiles")
    profiles.set_active_profile("default")
    backup.export_backup(plain_enc, passphrase="twelve-char-pp")
    backup.import_backup(plain_enc, merge_profiles=True, passphrase="twelve-char-pp")
    data_path = paths.data_file()
    assert not is_encrypted_file(data_path)
    from vault import save_data_file

    save_data_file(data_path, storage.load(), encrypted=True, passphrase=passphrase)
    assert is_encrypted_file(data_path)
