"""At most one filled accent button per screen (#134)."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from goto_ui import build_goto_destinations
from theme import DARK, LIGHT, apply_theme, get_theme
from ui_accent import (
    count_accent_buttons,
    secondary_button_border_contrast,
    ttk_secondary_button_border_contrast,
    wire_dialog_accent_keys,
)

import personal_dev_tracker
from tests.conftest import pump_tk
from tests.test_sidebar_131 import _mock_tracker_init


@pytest.fixture
def tracker():
    root = tk.Tk()
    root.withdraw()
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        _mock_tracker_init,
    ):
        t = personal_dev_tracker.PersonalDevelopmentTracker(root)
        t._ensure_shell()
        t.create_dashboard()
        yield t
        try:
            root.destroy()
        except tk.TclError:
            pass


def _open_toplevels(root: tk.Misc) -> list[tk.Toplevel]:
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists()]


def test_main_window_at_most_one_accent(tracker):
    tracker.root.update()
    assert count_accent_buttons(tracker.root) == 1


def test_main_window_zero_accent_when_all_domains_logged(tracker):
    today = tracker.today_str()
    tracker.entries[today] = {
        cat: {"rating": 5, "checklist": {}, "metrics": {}, "notes": ""}
        for cat in tracker.categories
    }
    tracker.refresh_dashboard(full=True)
    tracker.root.update()
    assert count_accent_buttons(tracker.root) == 0


def test_main_window_sole_accent_during_deep_work(tracker):
    """#134 reopen: demote Log one when Deep Work adds End as the sole accent."""
    pump_tk(tracker.root)
    assert tracker._log_one_btn is not None
    assert tracker._log_one_btn.cget("style") == "Accent.TButton"
    assert count_accent_buttons(tracker.root) == 1

    tracker._deep_work_session = MagicMock(running=True)
    tracker._ensure_deep_work_banner()
    tracker._apply_deep_work_chrome()
    pump_tk(tracker.root)
    assert tracker._deep_work_end_btn is not None
    assert tracker._deep_work_end_btn.cget("style") == "Accent.TButton"
    assert tracker._log_one_btn.cget("style") == "TButton"
    assert count_accent_buttons(tracker.root) == 1

    tracker._deep_work_session = None
    tracker._apply_deep_work_chrome()
    pump_tk(tracker.root)
    assert tracker._deep_work_end_btn.cget("style") == "TButton"
    assert tracker._log_one_btn.cget("style") == "Accent.TButton"
    assert count_accent_buttons(tracker.root) == 1


def test_quick_capture_panel_at_most_one_accent(tracker):
    import quick_capture_ui

    win = quick_capture_ui.open_quick_capture_panel(tracker)
    win.update()
    assert count_accent_buttons(win) == 1
    win.destroy()
    tracker._quick_capture_win = None


def test_secondary_button_border_contrast_meets_wcag():
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    for dark in (False, True):
        theme = get_theme(dark)
        apply_theme(root, theme)
        style = ttk.Style(root)
        assert secondary_button_border_contrast(theme) >= 3.0
        assert ttk_secondary_button_border_contrast(style, theme) >= 3.0
    root.destroy()


def test_goto_destinations_each_toplevel_at_most_one_accent(tracker):
    destinations = build_goto_destinations(tracker)
    skip_labels = {
        "Export",
        "Backup",
        "Toggle Dark / Light Mode",
        "Dark Mode",
        "Light Mode",
        "Refresh",
    }

    for dest in destinations:
        label = dest["label"]
        if label in skip_labels:
            continue
        before = {id(w) for w in _open_toplevels(tracker.root)}
        dest["action"]()
        tracker.root.update()
        new_windows = [w for w in _open_toplevels(tracker.root) if id(w) not in before]
        targets = new_windows if new_windows else [tracker.root]
        for win in targets:
            assert count_accent_buttons(win) <= 1, f"{label!r} opened window with >1 accent"
        for win in new_windows:
            try:
                win.destroy()
            except tk.TclError:
                pass
        tracker.root.update_idletasks()


def test_log_dialog_enter_and_escape_bindings(tracker):
    cat = next(iter(tracker.categories))
    tracker.open_log_dialog(cat)
    tracker.root.update_idletasks()
    tops = _open_toplevels(tracker.root)
    assert tops, "log dialog should open"
    dialog = tops[-1]
    assert count_accent_buttons(dialog) == 1
    assert dialog.bind("<Return>"), "Enter should be bound on log dialog"
    assert dialog.bind("<Escape>"), "Escape should be bound on log dialog"
    dialog.destroy()


def test_wire_dialog_accent_keys_registers_bindings():
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    dlg = tk.Toplevel(root)
    accent = ttk.Button(dlg, text="OK")
    accent.pack()
    cancel_btn = ttk.Button(dlg, text="Cancel", command=dlg.destroy)
    cancel_btn.pack()
    wire_dialog_accent_keys(dlg, accent, cancel_btn=cancel_btn)
    assert dlg.bind("<Return>")
    assert dlg.bind("<Escape>")
    dlg.destroy()
    root.destroy()
