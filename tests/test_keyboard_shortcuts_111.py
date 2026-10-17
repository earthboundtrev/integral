"""Global keyboard shortcuts (#111)."""

from __future__ import annotations

import sys
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import keyboard_shortcuts
import personal_dev_tracker
from tests.test_sidebar_131 import _mock_tracker_init


@pytest.fixture
def tracker():
    root = tk.Tk()
    # Shortcuts use bind_all; synthesized events do not run while the root is withdrawn.
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        _mock_tracker_init,
    ):
        t = personal_dev_tracker.PersonalDevelopmentTracker(root)
        t._ensure_shell()
        yield t
        try:
            root.destroy()
        except tk.TclError:
            pass


def _text_with_focus(tracker: personal_dev_tracker.PersonalDevelopmentTracker) -> tk.Text:
    text = tk.Text(tracker.root, height=3, width=40)
    text.insert("1.0", "keep this line intact")
    text.pack()
    text.focus_force()
    tracker.root.update_idletasks()
    tracker.root.update()
    return text


def test_ctrl_shift_t_in_text_unchanged_and_runs(tracker):
    with patch.object(tracker, "_raise_or_open", MagicMock()) as raise_open, patch.object(
        tracker, "set_quick_capture_enabled", MagicMock()
    ):
        text = _text_with_focus(tracker)
        before = text.get("1.0", "end")
        text.event_generate("<Control-Shift-T>")
        tracker.root.update()
        raise_open.assert_called_once_with("today")
        assert text.get("1.0", "end") == before


def test_ctrl_k_in_text_unchanged_opens_goto(tracker):
    with patch.object(tracker, "show_goto", MagicMock()) as show_goto:
        text = _text_with_focus(tracker)
        before = text.get("1.0", "end")
        text.event_generate("<Control-k>")
        tracker.root.update()
        show_goto.assert_called_once()
        assert text.get("1.0", "end") == before


def test_modal_grab_blocks_shortcut(tracker):
    modal = tk.Toplevel(tracker.root)
    modal.grab_set()
    tracker.root.update()
    with patch.object(tracker, "show_goto", MagicMock()) as show_goto:
        tracker.root.event_generate("<Control-k>")
        tracker.root.update()
        show_goto.assert_not_called()
    modal.grab_release()
    modal.destroy()


def test_alt_in_state_rejects_shortcut(tracker):
    with patch.object(tracker, "show_goto", MagicMock()) as show_goto:
        tracker.root.event_generate("<Control-k>", state=0x20000)
        tracker.root.update()
        show_goto.assert_not_called()


def test_alt_in_event_state_platform_masks():
    assert keyboard_shortcuts.alt_in_event_state(0x20000) is True
    if sys.platform == "win32":
        # Num Lock defaults on; Tk maps VK_NUMLOCK to Mod1Mask 0x0008 — must not block shortcuts.
        assert keyboard_shortcuts.alt_in_event_state(0x0008) is False
    else:
        assert keyboard_shortcuts.alt_in_event_state(0x0008) is True


def test_effective_control_shift_caps_lock_uppercase_no_shift_bit():
    """Caps Lock upper-case keysym without Shift bit must not count as Ctrl+Shift."""
    event = MagicMock(state=0, keysym="T")
    assert keyboard_shortcuts.effective_control_shift(event) is False


def test_effective_control_shift_with_shift_bit():
    event = MagicMock(state=keyboard_shortcuts._SHIFT_MASK, keysym="t")
    assert keyboard_shortcuts.effective_control_shift(event) is True


def test_shift_chord_rejects_caps_lock_ctrl_no_shift(tracker):
    action = MagicMock()
    handler = keyboard_shortcuts._wrap_shift_chord(tracker, action)
    event = MagicMock(
        state=keyboard_shortcuts._CONTROL_MASK,
        keysym="T",
    )
    assert handler(event) is None
    action.assert_not_called()


def test_modal_grab_blocks_ctrl_shift_shortcut(tracker):
    modal = tk.Toplevel(tracker.root)
    modal.grab_set()
    tracker.root.update()
    with patch.object(tracker, "_raise_or_open", MagicMock()) as raise_open:
        tracker.root.event_generate("<Control-Shift-T>")
        tracker.root.update()
        raise_open.assert_not_called()
    modal.grab_release()
    modal.destroy()


def test_ctrl_shift_k_does_not_open_goto(tracker):
    with patch.object(tracker, "show_goto", MagicMock()) as show_goto:
        tracker.root.event_generate("<Control-Shift-K>")
        tracker.root.update()
        show_goto.assert_not_called()


def test_show_shortcuts_list_f1(tracker):
    tracker.root.focus_force()
    tracker.root.update()
    tracker.root.event_generate("<F1>")
    tracker.root.update()
    assert getattr(tracker, "_shortcuts_window", None) is not None
    win = tracker._shortcuts_window
    assert win.winfo_exists()
    win.destroy()


def test_show_shortcuts_f1_raises_existing_window(tracker):
    tracker.root.focus_force()
    tracker.root.update()
    tracker.root.event_generate("<F1>")
    tracker.root.update()
    first = tracker._shortcuts_window
    assert first is not None and first.winfo_exists()
    tracker.root.event_generate("<F1>")
    tracker.root.update()
    assert tracker._shortcuts_window is first
    first.destroy()


def test_goto_ui_still_imports():
    import tests.test_goto_ui  # noqa: F401

