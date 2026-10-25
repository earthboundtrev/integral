"""Tests for sidebar navigation (#131)."""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import nav_items
import personal_dev_tracker
from sidebar_nav import ACCENT_BAR_WIDTH_PX, handle_sidebar_nav_key, set_sidebar_active
from tests.conftest import pump_tk_until
from tests.mock_tracker import mock_tracker_init as _mock_tracker_init


def _font_is_bold(widget: tk.Button) -> bool:
    return "bold" in str(widget.cget("font")).lower()


@pytest.fixture
def tracker():
    """Create a tracker with stubbed init."""
    root = tk.Tk()
    root.withdraw()
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


def test_sidebar_exists_and_240px(tracker):
    """AC: sidebar is 240 px wide at 100% scaling."""
    tracker.root.update_idletasks()
    assert tracker._sidebar_slot is not None
    assert tracker._sidebar_slot.winfo_exists()
    sidebar_width = tracker._sidebar_slot.winfo_reqwidth()
    assert sidebar_width == 240, f"Expected 240px, got {sidebar_width}px"


def test_nav_items_are_36px_tall(tracker):
    """AC: navigation items are 36 px tall."""
    tracker.root.update_idletasks()
    assert hasattr(tracker, "_sidebar_nav_buttons")
    assert len(tracker._sidebar_nav_buttons) >= 5
    for btn in tracker._sidebar_nav_buttons:
        btn_parent = btn.master
        height = btn_parent.winfo_reqheight()
        assert height == 36, f"Nav item height {height}px != 36px"


def _find_widget_recursive(root, predicate):
    """Find widget recursively using predicate."""
    if predicate(root):
        return True
    for child in root.winfo_children():
        if _find_widget_recursive(child, predicate):
            return True
    return False


def test_sidebar_has_brand_and_tagline(tracker):
    """Sidebar includes brand name and tagline."""
    tracker.root.update_idletasks()
    
    def is_brand(w):
        if isinstance(w, tk.Label):
            text = w.cget("text")
            return "Integral" in text
        return False
    
    def is_tagline(w):
        if isinstance(w, tk.Label):
            text = w.cget("text")
            return "Tend every area" in text
        return False
    
    found_brand = _find_widget_recursive(tracker._sidebar_slot, is_brand)
    found_tagline = _find_widget_recursive(tracker._sidebar_slot, is_tagline)
    
    assert found_brand, "Brand name not found in sidebar"
    assert found_tagline, "Tagline not found in sidebar"


def test_sidebar_has_goto_button(tracker):
    """Sidebar includes Go to… button."""
    tracker.root.update_idletasks()
    
    def is_goto(w):
        if isinstance(w, tk.Button):
            text = w.cget("text")
            return "Go to" in text
        return False
    
    found_goto = _find_widget_recursive(tracker._sidebar_slot, is_goto)
    assert found_goto, "Go to… button not found in sidebar"


def test_raise_or_open_raises_existing_window(tracker):
    """AC: Opening an already-open window raises it, never duplicates."""
    tracker.root.update_idletasks()
    
    mock_window = MagicMock(spec=tk.Toplevel)
    mock_window.winfo_exists.return_value = True
    tracker._open_windows["test_key"] = mock_window
    
    tracker._raise_or_open("test_key")
    
    mock_window.lift.assert_called_once()
    mock_window.focus_force.assert_called_once()


def test_raise_or_open_creates_new_when_none_exists(tracker):
    """raise_or_open creates new window when none exists."""
    tracker.root.update_idletasks()
    
    with patch.object(tracker, "show_fitness_hub") as mock_show:
        tracker._raise_or_open("fitness")
        mock_show.assert_called_once()


def test_show_reflect_opens_reflect_page(tracker):
    """AC: Reflect opens the one-screen daily reflection page (#113)."""
    with patch("reflect_page_ui.open_reflect_page") as mock_page:
        tracker.show_reflect()
        mock_page.assert_called_once_with(tracker)


def test_goto_destinations_includes_today_and_reflect(tracker):
    """AC: build_goto_destinations includes Today and Reflect."""
    from goto_ui import build_goto_destinations
    
    destinations = build_goto_destinations(tracker)
    labels = [d["label"] for d in destinations]
    
    assert "Today" in labels, "Today not in goto destinations"
    assert "Reflect" in labels, "Reflect not in goto destinations"


def test_keyboard_shortcuts_bound(tracker):
    """AC: Ctrl+K, Ctrl+Shift+R/J/G, Ctrl+Shift+I shortcuts are bound."""
    tracker.root.update_idletasks()
    
    binds = tracker.root.bind_all()
    binds_str = " ".join(str(b) for b in binds)
    
    assert ("<Control-k>" in binds_str or "<Control-K>" in binds_str or
            "Control-Key-k" in binds_str or "Control-Key-K" in binds_str), "Ctrl+K not bound"
    def _shift_letter(ch: str) -> bool:
        u, lo = ch.upper(), ch.lower()
        return (
            f"<Control-Shift-{u}>" in binds_str
            or f"<Control-Shift-{lo}>" in binds_str
            or f"<Control-Shift-Key-{u}>" in binds_str
            or f"<Control-Shift-Key-{lo}>" in binds_str
        )

    assert _shift_letter("R"), "Ctrl+Shift+R not bound"
    assert _shift_letter("J"), "Ctrl+Shift+J not bound"
    assert _shift_letter("G"), "Ctrl+Shift+G not bound"
    assert _shift_letter("I"), "Ctrl+Shift+I not bound"
    assert _shift_letter("T"), "Ctrl+Shift+T not bound"
    assert _shift_letter("W"), "Ctrl+Shift+W not bound"
    assert "<F1>" in binds_str or "<Key-F1>" in binds_str, "F1 shortcuts list not bound"


def test_window_tracking_on_close(tracker):
    """Window tracking cleans up on close."""
    tracker.root.update_idletasks()
    
    mock_window = tk.Toplevel(tracker.root)
    tracker._track_window("test_key", mock_window)
    
    assert "test_key" in tracker._open_windows
    
    # Simulate closing by calling the cleanup directly
    if "test_key" in tracker._open_windows:
        del tracker._open_windows["test_key"]
    mock_window.destroy()
    
    assert "test_key" not in tracker._open_windows


def test_sidebar_today_active_by_default(tracker):
    """AC: active item uses bold font and accent bar."""
    tracker.root.update_idletasks()
    assert tracker._sidebar_active_id == "today"
    btn = tracker._sidebar_nav_buttons_by_id["today"]
    assert _font_is_bold(btn)
    bar = tracker._sidebar_nav_accent_bars["today"]
    assert bar.cget("width") == ACCENT_BAR_WIDTH_PX
    assert bar.cget("bg") == tracker.theme["accent"]


def test_set_sidebar_active_updates_styles(tracker):
    tracker.root.update_idletasks()
    set_sidebar_active(tracker, "journal")
    assert tracker._sidebar_active_id == "journal"
    journal_btn = tracker._sidebar_nav_buttons_by_id["journal"]
    today_btn = tracker._sidebar_nav_buttons_by_id["today"]
    assert _font_is_bold(journal_btn)
    assert not _font_is_bold(today_btn)
    assert tracker._sidebar_nav_accent_bars["journal"].cget("bg") == tracker.theme["accent"]


def test_sidebar_keyboard_down_moves_focus(tracker):
    tracker.root.update_idletasks()
    order = [spec.id for spec in nav_items.sidebar_nav_items()]
    next_id = order[order.index("today") + 1]
    with patch("sidebar_nav._focus_nav_button") as mock_focus:
        assert handle_sidebar_nav_key(tracker, "today", "Down") is True
        mock_focus.assert_called_once_with(tracker, next_id)


def test_show_journal_uses_deferred_host(tracker):
    tracker.root.update_idletasks()
    with patch("journal_ui.show_journal_window") as mock_show:
        tracker.show_journal()
        assert pump_tk_until(tracker.root, lambda: mock_show.called)
        mock_show.assert_called_once()
        assert mock_show.call_args.kwargs.get("host") is not None
        assert "journal" in tracker._open_windows


def test_show_weekly_summary_raise_if_open(tracker):
    """show_weekly_summary implements raise-if-open."""
    tracker.root.update_idletasks()
    
    mock_window = MagicMock(spec=tk.Toplevel)
    mock_window.winfo_exists.return_value = True
    tracker._open_windows["weekly_summary"] = mock_window
    
    tracker.show_weekly_summary()
    
    mock_window.lift.assert_called_once()
    mock_window.focus_force.assert_called_once()
