"""Vault unlock step layout on restore panel (#293 / #278)."""

from __future__ import annotations

import os
import tkinter as tk
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
from tests.test_backup_dialog_layout_275 import (
    _apply_geometry,
    _assert_button_width_at_least_reqwidth,
    _assert_widget_visible_in_dialog,
    _dialog,
    _gh_windows_exe_ci,
    _set_tk_scaling,
    _widget_placed_in_layout,
    _widget_rect_in_window,
)
from tests.test_backup_dialog_pr275_ui import _find_button, _walk
from tests.test_backup_dialog_restore_vault_278 import _vault_unlock_entries
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file

_DIALOG_GEOMETRIES = ("580x520", "560x420")
_DIALOG_SCALINGS = (1.333, 2.0)


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(pdt_mod, "DATA_FILE", paths.data_file())


@pytest.fixture(autouse=True)
def _restore_apply_ready(monkeypatch):
    monkeypatch.setattr(backup_dialog_ui, "prepare_restore_apply", lambda _tracker: True)


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


def _assert_entry_width_at_least_reqwidth(entry: ttk.Entry, dialog: tk.Toplevel) -> None:
    entry.update_idletasks()
    dialog.update_idletasks()
    req = entry.winfo_reqwidth()
    _, _, ew, _ = _widget_rect_in_window(entry, dialog)
    if _gh_windows_exe_ci() and ew < 10:
        assert _widget_placed_in_layout(entry)
        assert req > 0
        return
    assert ew >= req, f"entry width {ew} < reqwidth {req}"


def _assert_vault_field_visible(widget: tk.Misc, dialog: tk.Toplevel) -> None:
    if _gh_windows_exe_ci():
        _assert_widget_visible_in_dialog(widget, dialog)
        return
    assert widget.winfo_ismapped()


def _rects_overlap(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    *,
    margin: int = 2,
) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw <= bx + margin
        or bx + bw <= ax + margin
        or ay + ah <= by + margin
        or by + bh <= ay + margin
    )


def _assert_no_overlap(dialog: tk.Toplevel, widgets: list[tk.Misc]) -> None:
    rects = [_widget_rect_in_window(w, dialog) for w in widgets]
    for i, rect_a in enumerate(rects):
        for rect_b in rects[i + 1 :]:
            assert not _rects_overlap(rect_a, rect_b), f"widgets overlap: {rect_a!r} vs {rect_b!r}"


def _open_vault_unlock_panel(tk_root, dialog: tk.Toplevel, zip_path: str) -> None:
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=zip_path):
        with patch("backup_dialog_ui.messagebox.askyesno", return_value=True):
            _find_button(dialog, "Restore from").invoke()
    pump_tk_until(
        tk_root,
        lambda: any("Vault passphrase" in str(w.cget("text")) for w in _walk(dialog) if w.winfo_class() == "TLabel"),
        timeout_s=3.0,
    )


def _vault_action_buttons(dialog: tk.Toplevel) -> tuple[tk.Misc, tk.Misc]:
    vault_entry, _ = _vault_unlock_entries(dialog)
    assert vault_entry is not None
    panel = vault_entry.master.master
    back = cont = None
    for child in panel.winfo_children():
        for w in child.winfo_children():
            if w.winfo_class() != "TButton":
                continue
            text = str(w.cget("text")).replace("&", "")
            if text == "Back" and (_widget_placed_in_layout(w) or w.winfo_ismapped()):
                back = w
            if text == "Continue" and (_widget_placed_in_layout(w) or w.winfo_ismapped()):
                cont = w
    assert back is not None and cont is not None
    assert back.master is cont.master
    return back, cont


def _vault_show_toggle(dialog: tk.Toplevel) -> tk.Misc | None:
    for w in _walk(dialog):
        if w.winfo_class() != "TCheckbutton":
            continue
        if str(w.cget("text")).replace("&", "") == "Show" and w.winfo_ismapped():
            parent = w.master
            labels = [
                str(c.cget("text"))
                for c in parent.winfo_children()
                if isinstance(c, (tk.Label, ttk.Label))
            ]
            if any("Vault passphrase" in text for text in labels):
                return w
    return None


@pytest.mark.parametrize("geometry", _DIALOG_GEOMETRIES)
@pytest.mark.parametrize("scaling", _DIALOG_SCALINGS)
def test_vault_unlock_layout_entry_and_actions_at_scaling(
    tk_root, temp_app, tmp_path, geometry, scaling, immediate_threads,
):
    plain_zip = str(tmp_path / "plain.zip")
    backup.export_backup(plain_zip, profile_id="default")
    data_path = paths.data_file()
    for path in (data_path, f"{data_path}.bak"):
        if os.path.isfile(path):
            os.remove(path)
    _seed_data_file(_minimal_v2_payload(), encrypted=False, passphrase=None)
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    tracker.settings["encryption_enabled"] = True
    tracker.vault_passphrase = None
    assert backup_dialog_ui.vault_restore_needs_passphrase_confirmation(tracker) is True

    dialog = _dialog(tk_root, tracker)
    _set_tk_scaling(tk_root, scaling)
    _apply_geometry(tk_root, dialog, geometry)
    _open_vault_unlock_panel(tk_root, dialog, plain_zip)
    pump_tk(tk_root, 12)

    vault_entry, vault_confirm = _vault_unlock_entries(dialog)
    assert vault_entry is not None
    _assert_vault_field_visible(vault_entry, dialog)
    assert vault_confirm is not None
    if backup_dialog_ui.vault_restore_needs_passphrase_confirmation(tracker):
        _assert_vault_field_visible(vault_confirm, dialog)

    back, cont = _vault_action_buttons(dialog)
    _assert_vault_field_visible(back, dialog)
    _assert_vault_field_visible(cont, dialog)
    show = _vault_show_toggle(dialog)

    _assert_entry_width_at_least_reqwidth(vault_entry, dialog)
    if vault_confirm.winfo_ismapped() or _widget_placed_in_layout(vault_confirm):
        _assert_entry_width_at_least_reqwidth(vault_confirm, dialog)
    _assert_button_width_at_least_reqwidth(back)
    _assert_button_width_at_least_reqwidth(cont)
    if show is not None:
        show.update_idletasks()
        assert show.winfo_width() >= show.winfo_reqwidth()

    if not _gh_windows_exe_ci():
        widgets = [vault_entry, vault_confirm, back, cont]
        if show is not None:
            widgets.append(show)
        _assert_no_overlap(dialog, widgets)

        _, ey, _, eh = _widget_rect_in_window(vault_entry, dialog)
        bx, by, _, _ = _widget_rect_in_window(back, dialog)
        assert ey + eh <= by + 2, (
            f"vault entry row should sit above Back/Continue action row "
            f"(entry_bottom={ey + eh}, back_top={by})"
        )