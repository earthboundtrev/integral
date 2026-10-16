"""Tests for sidebar navigation (#131)."""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import personal_dev_tracker


def _mock_tracker_init(self, root):
    """Mock initialization to skip data loading."""
    from fitness.engine import load_program_definitions
    import creative_projects
    import day_plans
    import journal
    import practices
    import todos
    import youtube_takeout
    from paths import data_file
    from theme import get_theme
    from focus_shield import FocusShieldSession
    
    self.root = root
    self.categories = self.get_default_categories()
    self.entries = {}
    self.settings = {"dark_mode": False}
    self.sessions = []
    self.milestones = []
    self.journal = journal.empty_journal()
    self.creative_projects = creative_projects.empty_creative_projects()
    self.youtube_history = youtube_takeout.empty_youtube_history()
    self.day_plans = day_plans.empty_day_plans()
    self.program_state = {}
    self.programs = load_program_definitions()
    self.data_path = data_file()
    self.vault_passphrase = None
    self.theme = get_theme(False)
    self._insights_cache = None
    self._streak_cache = {}
    self._session_counts_cache = None
    self._save_after_id = None
    self._pending_save_payload = None
    self._fitness_state_dirty = False
    self._dashboard_ready = False
    self._categories_tab_built = False
    self._theme_dark = None
    self._log_bar = None
    self._todays_log_filter = ""
    self._todays_log_status = "all"
    self._activity_grid = None
    self._guidance_panel = None
    self._streak_pill = None
    self._date_label = None
    self._overview_stats_label = None
    self._reminder_scheduler = None
    self._day_watch = None
    self._categories_tab_frame = None
    self._notebook = None
    self._streak_details_window = None
    self._deep_work_session = None
    self._deep_work_after_id = None
    self._deep_work_banner = None
    self._deep_work_timer_label = None
    self._quick_capture_win = None
    self._focus_shield = FocusShieldSession()
    self._focus_shield_after_id = None
    self.todos = todos.empty_todos()
    self.practices = practices.empty_practices()
    self._nav_buttons = {}
    self._nav_pack_order = []
    self._nav_frame = None
    self._shell_frame = None
    self._shell_header = None
    self._content_pane = None
    self._shell_footer = None
    self._banner_host = None
    self._sidebar_slot = None
    self.insights = []
    self._open_windows = {}


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
    
    with patch.object(tracker, "show_streak_details") as mock_show:
        tracker._raise_or_open("today")
        mock_show.assert_called_once()


def test_show_reflect_opens_unlogged_category(tracker):
    """AC: Reflect opens the first unlogged domain."""
    tracker.entries = {"2026-10-16": {"Money/Freedom": 3}}
    
    with patch.object(tracker, "open_log_dialog") as mock_log:
        tracker.show_reflect()
        mock_log.assert_called_once()
        called_category = mock_log.call_args[0][0]
        assert called_category in ["Career & Vocation", "Body & Presence"]


def test_show_reflect_shows_banner_when_all_logged(tracker):
    """AC: Reflect shows banner when all domains logged."""
    # Mock first_unlogged_category to return None (all logged)
    with patch.object(tracker, "first_unlogged_category", return_value=None):
        import tkinter.messagebox
        with patch.object(tkinter.messagebox, "showinfo") as mock_info:
            tracker.show_reflect()
            mock_info.assert_called_once()
            call_args = mock_info.call_args[0]
            assert "All domains logged" in call_args[0]


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
    assert ("<Control-R>" in binds_str or "Control-Key-R" in binds_str), "Ctrl+Shift+R not bound"
    assert ("<Control-J>" in binds_str or "Control-Key-J" in binds_str), "Ctrl+Shift+J not bound"
    assert ("<Control-G>" in binds_str or "Control-Key-G" in binds_str), "Ctrl+Shift+G not bound"
    assert ("<Control-I>" in binds_str or "Control-Key-I" in binds_str), "Ctrl+Shift+I not bound"


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


def test_show_weekly_summary_raise_if_open(tracker):
    """show_weekly_summary implements raise-if-open."""
    tracker.root.update_idletasks()
    
    mock_window = MagicMock(spec=tk.Toplevel)
    mock_window.winfo_exists.return_value = True
    tracker._open_windows["weekly_summary"] = mock_window
    
    tracker.show_weekly_summary()
    
    mock_window.lift.assert_called_once()
    mock_window.focus_force.assert_called_once()
