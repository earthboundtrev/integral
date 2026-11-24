"""Pre-restore safety backup restore dialog flows (#271)."""

from __future__ import annotations

import os
import stat
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import paths
import personal_dev_tracker
import profiles
import safety_backup
import storage
from backup_dialog_ui import apply_undo_from_safety_backup
from tests.conftest import create_tk_root, pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_layout_275 import (
    _assert_button_width_at_least_reqwidth,
    _dialog,
    _dialog_client_size,
    _set_tk_scaling,
)
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import is_encrypted_file, load_data_file

_DIALOG_GEOMETRIES = ("580x520", "560x420")
_DIALOG_SCALINGS = (1.0, 1.5)

MARKER_CURRENT = "current-live-marker"
MARKER_BACKUP = "backup-marker-271"


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


@pytest.fixture(autouse=True)
def _restore_apply_ready(monkeypatch):
    monkeypatch.setattr(backup_dialog_ui, "prepare_restore_apply", lambda _tracker: True)


@pytest.fixture(autouse=True)
def _skip_dashboard_rebuild(monkeypatch):
    import profile_journal_sync as pjs

    monkeypatch.setattr(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "create_dashboard",
        lambda self: None,
    )
    monkeypatch.setattr(backup_dialog_ui, "reencrypt_restored_journal_from_disk", lambda _t: (True, None))
    monkeypatch.setattr(pjs, "sync_active_profile_journal_to_tracker", lambda *_a: None)
    monkeypatch.setattr(pjs, "sync_tracker_journal_to_active_profile", lambda *_a: None)


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


@pytest.fixture(autouse=True)
def _destroy_backup_dialogs(tk_root):
    yield
    for child in list(tk_root.winfo_children()):
        if isinstance(child, tk.Toplevel):
            try:
                child.destroy()
            except tk.TclError:
                pass
    pump_tk(tk_root, 3)


def _tracker_vault_off(tk_root):
    _seed_data_file(_payload_with_marker(MARKER_CURRENT))
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.ensure_status_banner()
    return tracker


def _tracker_vault_on_unlocked(tk_root, passphrase: str = "vault-secret-12"):
    payload = _minimal_v2_payload()
    payload["settings"]["encryption_enabled"] = True
    payload["entries"]["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": MARKER_CURRENT}
    }
    _seed_data_file(payload, encrypted=True, passphrase=passphrase)
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = passphrase
    tracker.ensure_status_banner()
    return tracker


def _tracker_vault_on_locked(tk_root):
    payload = _minimal_v2_payload()
    payload["settings"]["encryption_enabled"] = True
    _seed_data_file(payload, encrypted=False, passphrase=None)
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = None
    tracker.ensure_status_banner()
    return tracker


def _payload_with_marker(marker: str) -> dict:
    payload = _minimal_v2_payload()
    payload["entries"]["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": marker}
    }
    return payload


def _make_backup_zip(tmp_path, marker: str = MARKER_BACKUP) -> str:
    profiles.set_active_profile("default")
    saved = storage.load()
    data = storage.load()
    data["entries"]["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 2, "checklist": {}, "metrics": {}, "notes": marker}
    }
    storage.save(data)
    zip_path = str(tmp_path / "restore-source.zip")
    backup.export_backup(zip_path, profile_id="default")
    storage.save(saved)
    return zip_path


def _confirm_restore(dialog: tk.Toplevel, tk_root) -> None:
    restore_btn = _find_button(dialog, "Restore")
    assert _find_button(dialog, "Cancel") is not None
    restore_btn.invoke()
    pump_tk(tk_root, 20)


def test_vault_locked_blocks_before_passphrase(tk_root, temp_app, tmp_path):
    tracker = _tracker_vault_on_locked(tk_root)
    zip_path = _make_backup_zip(tmp_path)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=zip_path):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 10)
    assert safety_backup.UNLOCK_VAULT_FIRST_MSG in _label_texts(dialog)
    assert not safety_backup._safety_backup_filenames()


def test_cancel_confirm_writes_no_safety_copy(tk_root, temp_app, tmp_path):
    tracker = _tracker_vault_off(tk_root)
    zip_path = _make_backup_zip(tmp_path)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=zip_path):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 15)
    _find_button(dialog, "Cancel").invoke()
    pump_tk(tk_root, 8)
    assert not safety_backup._safety_backup_filenames()
    assert _day_notes(tracker) == MARKER_CURRENT


def test_undo_from_safety_backup(tk_root, temp_app, tmp_path, monkeypatch):
    import profile_journal_sync as pjs

    tracker = _tracker_vault_off(tk_root)
    safety_path = str(tmp_path / "safety.zip")
    backup.export_backup(safety_path, profile_id="default")
    def undo_import(*_a, **_k):
        tracker.entries["2099-01-01"] = _payload_with_marker(MARKER_CURRENT)["entries"]["2099-01-01"]
        return {"profiles": ["default"]}

    monkeypatch.setattr(backup, "import_backup", undo_import)
    monkeypatch.setattr(pjs, "sync_active_profile_journal_to_tracker", lambda *_a: None)
    monkeypatch.setattr(backup_dialog_ui, "reencrypt_restored_journal_from_disk", lambda _t: (True, None))
    banner = tracker.ensure_status_banner()
    apply_undo_from_safety_backup(tracker, safety_path)
    pump_tk(tk_root, 10)
    assert _day_notes(tracker) == MARKER_CURRENT
    assert "Undo complete" in (banner._message_var.get() or "")


def test_confirm_bar_shows_saved_first_line(tk_root, temp_app, tmp_path):
    tracker = _tracker_vault_off(tk_root)
    zip_path = _make_backup_zip(tmp_path)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=zip_path):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 12)
    texts = _label_texts(dialog)
    assert "Your current data will be saved first." in texts
    assert "1 profile" in " ".join(texts)


def test_vault_on_safety_copy_is_encrypted(temp_app, tmp_path):
    passphrase = "vault-secret-12"
    profiles.set_active_profile("default")
    storage.save(_payload_with_marker(MARKER_CURRENT))
    tracker = MagicMock()
    tracker.save_data = MagicMock()
    tracker.data_path = os.path.join(profiles.get_profile_dir(), "data.json")
    tracker.vault_passphrase = passphrase
    path = safety_backup.write_pre_restore_safety_backup(
        tracker=tracker,
        vault_on=True,
        passphrase=passphrase,
        creative_root=os.path.join(temp_app["app_dir"], "creative"),
    )
    assert backup.is_encrypted_backup_file(path)


def _day_notes(tracker) -> str:
    tracker.load_data()
    return tracker.entries["2099-01-01"]["Emotional Wellbeing"]["notes"]


@pytest.mark.parametrize("geometry", _DIALOG_GEOMETRIES)
@pytest.mark.parametrize("scaling", _DIALOG_SCALINGS)
def test_success_banner_buttons_layout(tk_root, temp_app, geometry, scaling, tmp_path):
    tracker = _tracker_vault_off(tk_root)
    _set_tk_scaling(tk_root, scaling)
    long_path = os.path.join(safety_backup.safety_backups_dir(), "before-restore-20260101-1200.zip")
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root, 10)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    dialog.geometry(geometry)
    dialog.minsize(560, 420)
    pump_tk(tk_root, 12)
    zip_path = _make_backup_zip(tmp_path)
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=zip_path):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 10)
    for widget in _walk(dialog):
        if widget.winfo_class() == "TButton" and str(widget.cget("text")).replace("&", "") in (
            "Restore",
            "Cancel",
        ):
            _assert_button_width_at_least_reqwidth(widget)
    backup_dialog_ui._show_restore_success_banner(
        tracker,
        long_path,
        vault_on=True,
        undo_callback=lambda: None,
    )
    pump_tk(tk_root, 12)
    banner = tracker.ensure_status_banner()
    button_texts = [
        str(widget.cget("text"))
        for widget in _walk(banner._frame)
        if widget.winfo_class() == "TButton"
    ]
    assert "Undo restore" in button_texts
    assert "Open folder" in button_texts