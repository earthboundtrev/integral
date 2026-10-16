"""Grouped More menu (#130)."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

import deep_work
from more_menu_ui import (
    LEGACY_FOOTER_LABELS,
    MORE_GROUPS,
    MORE_ITEM_SHORTCUT_HINTS,
    TODAY_MORE_MENU_LABELS,
    MoreMenuPopup,
    assert_legacy_features_reachable,
    build_more_menu_rows,
    close_more_menu,
    labels_for_surface,
    theme_menu_label,
    toggle_more_menu,
    typeahead_advance,
)


def _make_tracker(root: tk.Tk) -> MagicMock:
    from theme import get_theme

    tracker = MagicMock()
    tracker.root = root
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = None
    tracker._more_menu_popup = None
    tracker.theme = get_theme(False)
    tracker.categories = {
        "Money/Freedom": {},
        "Body & Presence": {},
    }
    for name in (
        "refresh_dashboard",
        "show_guidance",
        "show_history",
        "show_search",
        "show_milestones",
        "_show_ai_insight",
        "toggle_quick_capture",
        "show_writing_projects",
        "show_deep_work",
        "show_export",
        "show_backup",
        "show_settings",
        "show_security",
        "toggle_dark_mode",
    ):
        setattr(tracker, name, MagicMock())
    return tracker


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


def test_MORE_GROUPS_has_three_sections_and_fifteen_actions():
    assert len(MORE_GROUPS) == 3
    titles = [g["title"] for g in MORE_GROUPS]
    assert titles == ["VIEW", "WORK MODES", "DATA & SETTINGS"]
    action_count = sum(len(g["items"]) for g in MORE_GROUPS)
    assert action_count == 15


def test_legacy_footer_and_today_more_reachability():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = None
    tracker.categories = {"Money/Freedom": {}}
    for name in (
        "refresh_dashboard",
        "show_guidance",
        "show_history",
        "show_search",
        "show_milestones",
        "_show_ai_insight",
        "toggle_quick_capture",
        "show_writing_projects",
        "show_deep_work",
        "show_export",
        "show_backup",
        "show_settings",
        "show_security",
        "toggle_dark_mode",
        "show_plan_tomorrow",
        "show_log_exercise",
        "show_fitness_hub",
        "show_goto",
        "show_reflect",
        "show_journal",
        "show_graphs",
        "show_weekly_summary",
        "open_log_dialog",
    ):
        setattr(tracker, name, MagicMock())
    assert_legacy_features_reachable(tracker)
    more_labels = labels_for_surface("more", tracker)
    assert "Guidance" in more_labels
    assert "Quick Capture" in more_labels
    assert "Go to…" in labels_for_surface("sidebar")
    assert "Plan Tomorrow" in labels_for_surface("today_more")


def test_theme_menu_label_follows_mode():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    assert theme_menu_label(tracker) == "Dark Mode"
    tracker.settings = {"dark_mode": True}
    assert theme_menu_label(tracker) == "Light Mode"


def test_deep_work_hides_distractions_in_more_menu():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = MagicMock()
    tracker._deep_work_session.running = True
    labels = [row.label for row in build_more_menu_rows(tracker)]
    assert "Refresh" in labels
    assert "AI Insight" in labels
    assert "Guidance" not in labels
    assert "Export" not in labels
    assert theme_menu_label(tracker) not in labels


def test_typeahead_finds_next_matching_row():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = None
    rows = build_more_menu_rows(tracker)
    idx = typeahead_advance(rows, 0, "gu")
    assert idx is not None
    assert rows[idx].label == "Guidance"


def test_deep_work_more_label_sets():
    assert "Guidance" in deep_work.DEEP_WORK_HIDDEN_MORE_LABELS
    assert "Refresh" in deep_work.DEEP_WORK_KEEP_MORE_LABELS


def test_quick_capture_row_shows_shortcut_hint(more_menu_env):
    tracker, anchor, root = more_menu_env
    assert MORE_ITEM_SHORTCUT_HINTS.get("quick_capture")
    toggle_more_menu(tracker, anchor)
    root.update_idletasks()
    popup = tracker._more_menu_popup
    assert popup is not None
    hints = [
        w.cget("text")
        for w in popup._hint_widgets
        if w is not None and w.winfo_exists()
    ]
    assert MORE_ITEM_SHORTCUT_HINTS["quick_capture"] in hints


def test_esc_closes_and_returns_focus_to_anchor(more_menu_env):
    tracker, anchor, root = more_menu_env
    toggle_more_menu(tracker, anchor)
    root.update()
    popup: MoreMenuPopup = tracker._more_menu_popup
    popup.window.event_generate("<Escape>")
    root.update()
    assert tracker._more_menu_popup is None
    focus = root.focus_get()
    if focus is not None:
        assert focus == anchor


def test_outside_click_closes_menu(more_menu_env):
    tracker, anchor, root = more_menu_env
    outside = tk.Frame(root, width=40, height=40)
    outside.place(relx=1.0, rely=1.0, anchor="se")
    toggle_more_menu(tracker, anchor)
    root.update()
    popup: MoreMenuPopup = tracker._more_menu_popup
    px = popup.window.winfo_rootx()
    py = popup.window.winfo_rooty()
    pw = popup.window.winfo_width()
    ph = popup.window.winfo_height()
    event = tk.Event()
    event.widget = outside
    event.x_root = px + pw + 50
    event.y_root = py + ph + 50
    popup._on_global_click(event)
    assert tracker._more_menu_popup is None


def test_global_click_with_grab_uses_pointer_not_widget(more_menu_env):
    tracker, anchor, root = more_menu_env
    toggle_more_menu(tracker, anchor)
    root.update()
    popup: MoreMenuPopup = tracker._more_menu_popup
    assert popup._had_grab
    px = popup.window.winfo_rootx()
    py = popup.window.winfo_rooty()
    pw = popup.window.winfo_width()
    ph = popup.window.winfo_height()
    event = tk.Event()
    event.widget = popup.window
    event.x_root = px + pw + 50
    event.y_root = py + ph + 50
    popup._on_global_click(event)
    assert tracker._more_menu_popup is None


def test_global_click_on_anchor_closes_with_grab(more_menu_env):
    tracker, anchor, root = more_menu_env
    toggle_more_menu(tracker, anchor)
    root.update()
    popup: MoreMenuPopup = tracker._more_menu_popup
    event = tk.Event()
    event.widget = popup.window
    event.x_root = anchor.winfo_rootx() + 2
    event.y_root = anchor.winfo_rooty() + 2
    popup._on_global_click(event)
    assert tracker._more_menu_popup is None


def test_popup_x_clamped_to_root_window(more_menu_env):
    tracker, anchor, root = more_menu_env
    root.geometry("800x600+0+50")
    anchor.pack_forget()
    anchor.place(x=0, y=0)
    root.update_idletasks()
    toggle_more_menu(tracker, anchor)
    root.update_idletasks()
    popup: MoreMenuPopup = tracker._more_menu_popup
    root_x = root.winfo_rootx()
    assert popup.window.winfo_rootx() >= root_x


def test_toggle_more_menu_singleton(more_menu_env):
    tracker, anchor, root = more_menu_env
    toggle_more_menu(tracker, anchor)
    root.update()
    first = tracker._more_menu_popup
    toggle_more_menu(tracker, anchor)
    root.update()
    assert tracker._more_menu_popup is None
    toggle_more_menu(tracker, anchor)
    root.update()
    second = tracker._more_menu_popup
    assert second is not None
    assert second is not first


def test_home_end_move_focus(more_menu_env):
    tracker, anchor, root = more_menu_env
    toggle_more_menu(tracker, anchor)
    root.update()
    popup: MoreMenuPopup = tracker._more_menu_popup
    popup.window.event_generate("<End>")
    root.update()
    assert popup._focus_index == len(popup.rows) - 1
    popup.window.event_generate("<Home>")
    root.update()
    assert popup._focus_index == 0
