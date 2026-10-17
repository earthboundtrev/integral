"""Inline todo placeholder and whitespace handling (#155)."""

from __future__ import annotations

import inspect
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import personal_dev_tracker
from tests.test_sidebar_131 import _mock_tracker_init
from theme import DARK, LIGHT
from ui_accent import contrast_ratio


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
        t.save_data = MagicMock()
        t.refresh_dashboard = MagicMock()
        t.sync_quick_capture_panel = MagicMock()
        t.set_quick_capture_enabled = MagicMock()
        t.create_todays_log_bar()
        root.update_idletasks()
        yield t
        try:
            root.destroy()
        except tk.TclError:
            pass


def _todo_count(tracker) -> int:
    return len(tracker.todos.get("items", []))


def _begin_inline_todo_edit(tracker) -> None:
    """Focus inline todo and clear placeholder (FocusIn is unreliable on withdrawn roots)."""
    entry = tracker._inline_todo_entry
    entry.focus_set()
    entry.event_generate("<FocusIn>")
    tracker.root.update_idletasks()
    if tracker._inline_todo_placeholder_shown:
        tracker._inline_todo_var.set("")
        tracker._inline_todo_placeholder_shown = False
        entry.config(foreground=tracker.theme["fg"])


def _invoke_entry_bind(entry: tk.Widget, sequence: str) -> None:
    """Run a Tk bind script (event_generate misses ttk.Entry Return/Escape in CI)."""
    bind = entry.bind(sequence)
    if not bind:
        raise AssertionError(f"No binding for {sequence!r}")
    inner = bind.split("[")[1].split("]")[0].split()[0]
    entry.tk.call(inner)


def _press_return_inline_todo(tracker) -> None:
    _invoke_entry_bind(tracker._inline_todo_entry, "<Return>")
    tracker.root.update_idletasks()


def _press_escape_inline_todo(tracker) -> None:
    _invoke_entry_bind(tracker._inline_todo_entry, "<Escape>")
    tracker.root.update_idletasks()


def test_placeholder_literal_is_single_module_constant():
    src = inspect.getsource(personal_dev_tracker.PersonalDevelopmentTracker.create_todays_log_bar)
    literal = personal_dev_tracker.INLINE_TODO_PLACEHOLDER
    assert src.count(f'"{literal}"') == 0
    assert "INLINE_TODO_PLACEHOLDER" in src
    module_src = inspect.getsource(personal_dev_tracker)
    assert module_src.count(f'"{literal}"') == 1


def test_placeholder_muted_contrast_on_field_background():
    for theme in (LIGHT, DARK):
        ratio = contrast_ratio(theme["muted"], theme["field_bg"])
        assert ratio >= 4.5, f"{theme['name']}: muted on field_bg {ratio:.2f}"


def test_whitespace_only_enter_clears_without_adding(tracker):
    entry = tracker._inline_todo_entry
    var = tracker._inline_todo_var
    before = _todo_count(tracker)

    _begin_inline_todo_edit(tracker)
    var.set("   \t  ")
    _press_return_inline_todo(tracker)

    assert _todo_count(tracker) == before
    assert var.get() == ""
    assert tracker._inline_todo_placeholder_shown is False

    tracker._inline_todo_entry.event_generate("<FocusOut>")
    assert tracker._inline_todo_placeholder_shown is True
    assert var.get() == personal_dev_tracker.INLINE_TODO_PLACEHOLDER


def test_placeholder_showing_enter_does_not_add(tracker):
    before = _todo_count(tracker)
    _press_return_inline_todo(tracker)
    assert _todo_count(tracker) == before


def test_real_text_matching_placeholder_adds_after_focus_in(tracker):
    entry = tracker._inline_todo_entry
    var = tracker._inline_todo_var
    text = personal_dev_tracker.INLINE_TODO_PLACEHOLDER

    _begin_inline_todo_edit(tracker)
    var.set(text)
    _press_return_inline_todo(tracker)

    assert _todo_count(tracker) == 1
    assert tracker.todos["items"][0]["text"] == text


def test_successful_add_trims_text(tracker):
    entry = tracker._inline_todo_entry
    var = tracker._inline_todo_var

    _begin_inline_todo_edit(tracker)
    var.set("  Buy milk  ")
    _press_return_inline_todo(tracker)

    assert tracker.todos["items"][-1]["text"] == "Buy milk"


def test_escape_clears_placeholder_text_then_moves_to_button(tracker):
    entry = tracker._inline_todo_entry
    var = tracker._inline_todo_var
    text = personal_dev_tracker.INLINE_TODO_PLACEHOLDER
    btn = tracker._add_todo_button

    _begin_inline_todo_edit(tracker)
    var.set(text)
    _press_escape_inline_todo(tracker)
    assert var.get() == personal_dev_tracker.INLINE_TODO_PLACEHOLDER
    assert tracker._inline_todo_placeholder_shown is True

    with patch.object(btn, "focus_set", wraps=btn.focus_set) as focus_mock:
        _press_escape_inline_todo(tracker)
        focus_mock.assert_called_once()


def test_more_options_skips_prefill_when_placeholder_showing(tracker):
    tracker._inline_todo_placeholder_shown = True
    tracker._inline_todo_var.set(personal_dev_tracker.INLINE_TODO_PLACEHOLDER)
    if hasattr(tracker, "_qc_prefill_text"):
        del tracker._qc_prefill_text

    todo_row = tracker._inline_todo_entry.master
    for widget in todo_row.winfo_children():
        try:
            if widget.cget("text") == "More options…":
                widget.event_generate("<Button-1>")
                break
        except tk.TclError:
            continue

    assert not getattr(tracker, "_qc_prefill_text", "")
    tracker.set_quick_capture_enabled.assert_called()


def test_more_options_prefills_real_text_including_placeholder_sentence(tracker):
    entry = tracker._inline_todo_entry
    var = tracker._inline_todo_var
    text = personal_dev_tracker.INLINE_TODO_PLACEHOLDER

    _begin_inline_todo_edit(tracker)
    var.set(text)

    todo_row = entry.master
    for widget in todo_row.winfo_children():
        try:
            if widget.cget("text") == "More options…":
                widget.event_generate("<Button-1>")
                break
        except tk.TclError:
            continue

    assert tracker._qc_prefill_text == text


def test_inline_todo_state_survives_content_rebuild(tracker):
    entry = tracker._inline_todo_entry
    var = tracker._inline_todo_var

    _begin_inline_todo_edit(tracker)
    var.set("draft before rebuild")
    assert tracker._inline_todo_placeholder_shown is False

    tracker._build_content(recompute=False)
    tracker.root.update_idletasks()
    tracker.root.update_idletasks()

    assert tracker._inline_todo_var.get() == "draft before rebuild"
    assert tracker._inline_todo_placeholder_shown is False

    tracker._inline_todo_var.set("")
    tracker._inline_todo_placeholder_shown = True
    tracker._inline_todo_var.set(personal_dev_tracker.INLINE_TODO_PLACEHOLDER)

    tracker._build_content(recompute=False)
    tracker.root.update_idletasks()
    tracker.root.update_idletasks()

    assert tracker._inline_todo_placeholder_shown is True
    assert tracker._inline_todo_var.get() == personal_dev_tracker.INLINE_TODO_PLACEHOLDER
