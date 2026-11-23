"""Restore dialog layout: Continue label fit and footer buttons visible (#275)."""

from __future__ import annotations

import os
import tkinter as tk
from typing import cast
from tkinter import font as tkfont
from tkinter import ttk
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import paths
import personal_dev_tracker
import personal_dev_tracker as pdt_mod
from tests.conftest import pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file

_DIALOG_GEOMETRIES = ("580x520", "560x420")


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
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _dialog(tk_root, tracker) -> tk.Toplevel:
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root, 8)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    try:
        dialog.deiconify()
        dialog.lift()
        dialog.update_idletasks()
    except tk.TclError:
        pass
    pump_tk(tk_root, 8)
    return dialog


def _dialog_client_size(dialog: tk.Toplevel) -> tuple[int, int]:
    dialog.update_idletasks()
    ww, wh = dialog.winfo_width(), dialog.winfo_height()
    if ww >= 100 and wh >= 100:
        return ww, wh
    stored = getattr(dialog, "_test_client_size", None)
    if stored:
        return stored
    try:
        size_part = str(dialog.wm_geometry()).split("+", 1)[0]
        parsed_w, parsed_h = (int(part) for part in size_part.lower().split("x"))
        if parsed_w >= 100 and parsed_h >= 100:
            return parsed_w, parsed_h
    except (ValueError, tk.TclError):
        pass
    return ww, wh


def _apply_geometry(tk_root, dialog: tk.Toplevel, geometry: str) -> None:
    width, height = (int(part) for part in geometry.lower().split("x"))
    dialog._test_client_size = (width, height)  # type: ignore[attr-defined]
    dialog.minsize(width, height)
    dialog.geometry(geometry)
    dialog.update_idletasks()
    pump_tk(tk_root, 20)
    if os.environ.get("INTEGRAL_WINDOWS_EXE_CI") == "1":
        return
    ww, wh = _dialog_client_size(dialog)
    assert ww >= width - 8, f"dialog width {ww} < expected {width}"
    assert wh >= height - 8, f"dialog height {wh} < expected {height}"


def _coords_in_ancestor(widget: tk.Misc, ancestor: tk.Misc) -> tuple[int, int, int, int]:
    widget.update_idletasks()
    x = y = 0
    current: tk.Misc | None = widget
    while current is not None and current != ancestor:
        x += current.winfo_x()
        y += current.winfo_y()
        current = current.master
    return x, y, widget.winfo_width(), widget.winfo_height()


def _mapped_inside_window(widget: tk.Misc, window: tk.Misc) -> bool:
    window.update_idletasks()
    if not widget.winfo_ismapped():
        return False
    ww, wh = _dialog_client_size(cast(tk.Toplevel, window))
    rel_x, rel_y, bw, bh = _coords_in_ancestor(widget, window)
    margin = 4
    return (
        rel_x >= -margin
        and rel_y >= -margin
        and rel_x + max(bw, widget.winfo_reqwidth()) <= ww + margin
        and rel_y + max(bh, widget.winfo_reqheight()) <= wh + margin
    )


def _continue_button_text_width(btn: tk.Misc) -> int:
    family = tkfont.nametofont("TkDefaultFont")
    sample = str(btn.cget("text")).replace("&", "")
    return family.measure(sample)


def _open_restore_passphrase_panel(tk_root, tracker, dialog: tk.Toplevel, enc_path: str) -> tk.Misc:
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc_path):
        _find_button(dialog, "Restore from").invoke()
    pump_tk(tk_root, 12)

    def _mapped_continue() -> bool:
        for w in _walk(dialog):
            if w.winfo_class() != "TButton":
                continue
            if "Continue" not in str(w.cget("text")).replace("&", ""):
                continue
            if w.winfo_ismapped():
                return True
        return False

    pump_tk_until(tk_root, _mapped_continue, timeout_s=2.0)
    for w in _walk(dialog):
        if w.winfo_class() != "TButton":
            continue
        if "Continue" in str(w.cget("text")).replace("&", ""):
            return w
    return _find_button(dialog, "Continue")


def _open_restore_confirm_bar(tk_root, tracker, dialog: tk.Toplevel, enc_path: str) -> tuple[tk.Misc, tk.Misc]:
    manifest = {"exported_at": "2026-01-01T00:00:00", "profiles": ["default"]}
    with (
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc_path),
        patch("backup_dialog_ui.backup.validate_backup", return_value=manifest),
    ):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 12)
        vault_auto = tracker.settings.get("encryption_enabled") and bool(tracker.vault_passphrase)
        if not vault_auto:
            for w in _walk(dialog):
                if not isinstance(w, ttk.Entry):
                    continue
                for sib in w.master.winfo_children():
                    if isinstance(sib, ttk.Label) and "Restore passphrase" in str(sib.cget("text")):
                        w.delete(0, tk.END)
                        w.insert(0, "twelve-char-pp")
                        break
            _find_button(dialog, "Continue").invoke()
            pump_tk(tk_root, 12)
        pump_tk_until(
            tk_root,
            lambda: "backup from" in " ".join(_label_texts(dialog)).lower(),
            timeout_s=3.0,
        )
    restore_btn = _find_button(dialog, "Restore", exclude="from")
    cancel_btn = _find_button(dialog, "Cancel")
    return restore_btn, cancel_btn


@pytest.mark.parametrize("geometry", _DIALOG_GEOMETRIES)
def test_continue_button_fits_label_at_dialog_sizes(tk_root, temp_app, tmp_path, geometry):
    enc = str(tmp_path / "layout.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    dialog = _dialog(tk_root, tracker)
    _apply_geometry(tk_root, dialog, geometry)
    continue_btn = _open_restore_passphrase_panel(tk_root, tracker, dialog, enc)
    pump_tk(tk_root, 8)
    needed = _continue_button_text_width(continue_btn) + 16
    assert continue_btn.winfo_reqwidth() >= needed
    assert _mapped_inside_window(continue_btn, dialog)


@pytest.mark.parametrize("geometry", _DIALOG_GEOMETRIES)
def test_restore_cancel_visible_with_vault_at_dialog_sizes(
    tk_root, temp_app, tmp_path, geometry, immediate_threads,
):
    enc = str(tmp_path / "layout2.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock") as unlock:

        def _unlock(tr):
            tr.vault_passphrase = "twelve-char-pp"
            return True

        unlock.side_effect = _unlock
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = "twelve-char-pp"
    dialog = _dialog(tk_root, tracker)
    _apply_geometry(tk_root, dialog, geometry)
    restore_btn, cancel_btn = _open_restore_confirm_bar(tk_root, tracker, dialog, enc)
    pump_tk(tk_root, 8)
    assert _mapped_inside_window(restore_btn, dialog)
    assert _mapped_inside_window(cancel_btn, dialog)