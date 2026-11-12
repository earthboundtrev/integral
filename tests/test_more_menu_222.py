"""Regression tests for More menu global bind_all leak (#222)."""

from __future__ import annotations

import logging
import tkinter as tk

import pytest

from more_menu_ui import close_more_menu, toggle_more_menu, unbind_all_func
from tests.conftest import pump_tk
from tests.test_more_menu_130 import _make_tracker


@pytest.fixture
def more_menu_env():
    root = tk.Tk()
    root.withdraw()
    root.geometry("800x600+50+50")
    tracker = _make_tracker(root)
    anchor = tk.Button(root, text="More…")
    anchor.pack()
    root.update_idletasks()
    yield tracker, anchor, root
    close_more_menu(tracker)
    try:
        root.destroy()
    except tk.TclError:
        pass


def _button1_bind_script(root: tk.Tk) -> str:
    return root.bind_class("all", "<Button-1>")


def test_more_menu_repeated_open_close_preserves_bind_class(more_menu_env):
    tracker, anchor, root = more_menu_env
    baseline = _button1_bind_script(root)
    for _ in range(10):
        toggle_more_menu(tracker, anchor)
        pump_tk(root)
        assert tracker._more_menu_popup is not None
        toggle_more_menu(tracker, anchor)
        pump_tk(root)
        assert tracker._more_menu_popup is None
    assert _button1_bind_script(root) == baseline


def test_more_menu_close_preserves_sentinel_bind_all(more_menu_env):
    tracker, anchor, root = more_menu_env

    def sentinel(_event: tk.Event) -> None:
        pass

    sentinel_id = root.bind_all("<Button-1>", sentinel, add="+")
    try:
        before = _button1_bind_script(root)
        assert sentinel_id in before
        toggle_more_menu(tracker, anchor)
        pump_tk(root)
        assert tracker._more_menu_popup is not None
        close_more_menu(tracker)
        pump_tk(root)
        after = _button1_bind_script(root)
        assert sentinel_id in after
        assert after.count(sentinel_id) == before.count(sentinel_id)
    finally:
        unbind_all_func(root, "<Button-1>", sentinel_id)


def test_more_menu_outside_click_still_closes_after_many_cycles(more_menu_env):
    tracker, anchor, root = more_menu_env
    outside = tk.Frame(root, width=40, height=40)
    outside.place(relx=1.0, rely=1.0, anchor="se")
    for _ in range(3):
        toggle_more_menu(tracker, anchor)
        pump_tk(root)
        popup = tracker._more_menu_popup
        assert popup is not None
        script = _button1_bind_script(root)
        assert any(popup._binding_all_funcids[0][1] in line for line in script.splitlines())
        px = popup.window.winfo_rootx()
        py = popup.window.winfo_rooty()
        pw = popup.window.winfo_width()
        ph = popup.window.winfo_height()
        event = tk.Event()
        event.widget = outside
        event.x_root = px + pw + 50
        event.y_root = py + ph + 50
        popup._on_global_click(event)
        pump_tk(root)
        assert tracker._more_menu_popup is None


def test_unbind_all_func_logs_tcl_error(caplog):
    root = tk.Tk()
    root.withdraw()
    try:
        with caplog.at_level(logging.ERROR, logger="more_menu_ui"):
            unbind_all_func(root, "<Button-1>", "nonexistent_funcid_222")
        assert any(
            "Failed to remove global binding" in record.message for record in caplog.records
        )
    finally:
        root.destroy()
