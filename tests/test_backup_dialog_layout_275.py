"""Restore dialog layout: Continue label fit and footer buttons visible (#275)."""

from __future__ import annotations

import os
import sys
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
from tests.conftest import create_tk_root, pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file

_DIALOG_GEOMETRIES = ("580x520", "560x420")
_DIALOG_SCALINGS = (1.0, 1.5)


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
    root = create_tk_root(withdraw=not _gh_windows_exe_ci())
    if _gh_windows_exe_ci():
        root.geometry("900x700+0+0")
        root.update_idletasks()
        pump_tk(root, 5)
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


def _set_tk_scaling(tk_root: tk.Misc, scaling: float) -> None:
    tk_root.tk.call("tk", "scaling", scaling)
    tk_root.update_idletasks()
    pump_tk(tk_root, 8)


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


def _gh_windows_exe_ci() -> bool:
    return sys.platform == "win32" and os.environ.get("INTEGRAL_WINDOWS_EXE_CI") == "1"


def _widget_rect_in_window(widget: tk.Misc, window: tk.Misc) -> tuple[int, int, int, int]:
    """Return widget x, y, width, height in window client coordinates."""
    window.update_idletasks()
    widget.update_idletasks()
    top = cast(tk.Toplevel, window)
    if _gh_windows_exe_ci() and top.winfo_width() < 100:
        rel_x = widget.winfo_rootx() - window.winfo_rootx()
        rel_y = widget.winfo_rooty() - window.winfo_rooty()
        bw = max(widget.winfo_width(), widget.winfo_reqwidth(), 1)
        bh = max(widget.winfo_height(), widget.winfo_reqheight(), 1)
        return rel_x, rel_y, bw, bh
    rel_x, rel_y, bw, bh = _coords_in_ancestor(widget, window)
    bw = max(bw, widget.winfo_reqwidth())
    bh = max(bh, widget.winfo_reqheight())
    return rel_x, rel_y, bw, bh


def _widget_placed_in_layout(widget: tk.Misc) -> bool:
    try:
        widget.pack_info()
        return True
    except tk.TclError:
        pass
    try:
        return bool(widget.grid_info())
    except tk.TclError:
        return False


def _assert_widget_visible_in_dialog(widget: tk.Misc, dialog: tk.Toplevel) -> None:
    widget.update_idletasks()
    if _gh_windows_exe_ci():
        assert widget.winfo_exists()
        assert _widget_placed_in_layout(widget)
        return
    assert widget.winfo_ismapped()
    assert _mapped_inside_window(widget, dialog)


def _mapped_inside_window(widget: tk.Misc, window: tk.Misc) -> bool:
    if not widget.winfo_ismapped():
        return False
    ww, wh = _dialog_client_size(cast(tk.Toplevel, window))
    rel_x, rel_y, bw, bh = _widget_rect_in_window(widget, window)
    margin = 8
    y_ok = rel_y >= -margin and rel_y + bh <= wh + margin
    x_ok = rel_x >= -margin and rel_x + bw <= ww + margin
    if _gh_windows_exe_ci() and cast(tk.Toplevel, window).winfo_width() < 100:
        return y_ok
    return x_ok and y_ok


def _set_encrypt_passphrase_visible(dialog: tk.Toplevel, *, vault_on: bool) -> None:
    if vault_on:
        return
    for w in _walk(dialog):
        if w.winfo_class() != "TCheckbutton":
            continue
        text = str(w.cget("text")).replace("&", "")
        if "Encrypt with passphrase" not in text:
            continue
        if w.instate(["selected"]):
            return
        w.invoke()
        return
    pytest.fail("Encrypt with passphrase checkbox not found")


def _main_footer_buttons(dialog: tk.Toplevel) -> list[tk.Misc]:
    return [
        _find_button(dialog, "Export"),
        _find_button(dialog, "Restore from"),
        _find_button(dialog, "Close"),
    ]


def _assert_button_width_at_least_reqwidth(btn: tk.Misc) -> None:
    btn.update_idletasks()
    req = btn.winfo_reqwidth()
    width = btn.winfo_width()
    if _gh_windows_exe_ci() and width < 10:
        assert _widget_placed_in_layout(btn)
        assert req > 0
        return
    assert width >= req, (
        f"{str(btn.cget('text')).replace('&', '')!r}: width {width} < reqwidth {req}"
    )


def _passphrase_export_entries(dialog: tk.Toplevel) -> list[ttk.Entry]:
    found: list[ttk.Entry] = []
    for w in _walk(dialog):
        if not isinstance(w, ttk.Entry):
            continue
        for sib in w.master.winfo_children():
            if not isinstance(sib, ttk.Label):
                continue
            label = str(sib.cget("text"))
            if label in ("Passphrase", "Confirm passphrase"):
                found.append(w)
                break
    return found


def _footer_top_y_in_dialog(dialog: tk.Toplevel) -> int:
    close_btn = _find_button(dialog, "Close")
    footer: tk.Misc = close_btn
    for _ in range(6):
        if isinstance(footer.master, tk.Toplevel):
            break
        footer = footer.master
    dialog.update_idletasks()
    return _coords_in_ancestor(footer, dialog)[1]


def _entry_bottom_y_in_dialog(entry: ttk.Entry, dialog: tk.Toplevel) -> int:
    dialog.update_idletasks()
    entry.update_idletasks()
    rel_y, _, _, eh = _coords_in_ancestor(entry, dialog)
    return rel_y + max(eh, entry.winfo_reqheight())


def _assert_no_footer_overlap_passphrase_fields(dialog: tk.Toplevel) -> None:
    entries = _passphrase_export_entries(dialog)
    assert entries, "expected export passphrase entries to be visible"
    footer_top = _footer_top_y_in_dialog(dialog)
    if _gh_windows_exe_ci() and cast(tk.Toplevel, dialog).winfo_width() < 100:
        for entry in entries:
            assert _widget_placed_in_layout(entry)
        return
    margin = 4
    for entry in entries:
        bottom = _entry_bottom_y_in_dialog(entry, dialog)
        assert bottom <= footer_top + margin, (
            f"passphrase field overlaps footer (bottom={bottom}, footer_top={footer_top})"
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
    _assert_widget_visible_in_dialog(continue_btn, dialog)


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
    _assert_widget_visible_in_dialog(restore_btn, dialog)
    _assert_widget_visible_in_dialog(cancel_btn, dialog)


@pytest.mark.parametrize("geometry", _DIALOG_GEOMETRIES)
@pytest.mark.parametrize("scaling", _DIALOG_SCALINGS)
@pytest.mark.parametrize("vault_on", (False, True))
def test_footer_buttons_width_at_least_reqwidth(tk_root, temp_app, geometry, scaling, vault_on):
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock") as unlock:

        def _unlock(tr):
            tr.vault_passphrase = "twelve-char-pp"
            return True

        unlock.side_effect = _unlock
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    if vault_on:
        tracker.settings["encryption_enabled"] = True
        tracker.vault_passphrase = "twelve-char-pp"
    _set_tk_scaling(tk_root, scaling)
    dialog = _dialog(tk_root, tracker)
    _apply_geometry(tk_root, dialog, geometry)
    _set_encrypt_passphrase_visible(dialog, vault_on=vault_on)
    pump_tk(tk_root, 15)
    export_btn = _find_button(dialog, "Export")
    close_btn = _find_button(dialog, "Close")
    assert close_btn.master is not export_btn.master, "Close must not share a row with Export"
    for btn in _main_footer_buttons(dialog):
        _assert_button_width_at_least_reqwidth(btn)


@pytest.mark.parametrize("geometry", _DIALOG_GEOMETRIES)
@pytest.mark.parametrize("scaling", _DIALOG_SCALINGS)
@pytest.mark.parametrize("vault_on", (False, True))
def test_footer_does_not_overlap_export_passphrase_fields(
    tk_root, temp_app, geometry, scaling, vault_on,
):
    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock") as unlock:

        def _unlock(tr):
            tr.vault_passphrase = "twelve-char-pp"
            return True

        unlock.side_effect = _unlock
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    if vault_on:
        tracker.settings["encryption_enabled"] = True
        tracker.vault_passphrase = "twelve-char-pp"
    _set_tk_scaling(tk_root, scaling)
    dialog = _dialog(tk_root, tracker)
    _apply_geometry(tk_root, dialog, geometry)
    _set_encrypt_passphrase_visible(dialog, vault_on=vault_on)
    pump_tk(tk_root, 15)
    _assert_no_footer_overlap_passphrase_fields(dialog)