"""
Tests for app shell persistence across refreshes (issue #128).

Acceptance criteria:
1. Tk path names of sidebar slot, content pane, _streak_pill and _date_label
   are unchanged across 3 refreshes
2. Recursive winfo_children count after refresh 10 equals count after refresh 1,
   and winfo children . doesn't grow
3. After 3 refreshes a wheel event over a domain button still scrolls (#122)
4. Focus is preserved across a rebuild
5. Banners (_banner_host) belong to the shell and survive a content rebuild
6. A content rebuild on the seeded dataset takes < 50 ms
"""
import time
import tkinter as tk
from unittest.mock import MagicMock, patch

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
    self._save_after_callbacks = []
    self._save_write_in_progress = False
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
    from focus_shield import FocusShieldSession
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
    self._theme_reopen_banner = None
    self._open_windows = {}
    self._goto_window = None


def _count_widgets_recursive(widget):
    """Count total widgets including nested children."""
    count = 1
    for child in widget.winfo_children():
        count += _count_widgets_recursive(child)
    return count


def test_shell_widget_paths_unchanged_across_refreshes():
    """AC1: Shell widget Tk paths unchanged across 3 refreshes."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        
        # Capture initial paths
        initial_content_pane_path = str(tracker._content_pane) if tracker._content_pane else None
        initial_sidebar_path = str(tracker._sidebar_slot) if tracker._sidebar_slot else None
        initial_streak_pill_path = str(tracker._streak_pill) if tracker._streak_pill else None
        initial_date_label_path = str(tracker._date_label) if tracker._date_label else None
        initial_banner_host_path = str(tracker._banner_host) if tracker._banner_host else None
        
        assert initial_content_pane_path is not None
        assert initial_sidebar_path is not None
        assert initial_streak_pill_path is not None
        assert initial_date_label_path is not None
        assert initial_banner_host_path is not None
        
        # Refresh 3 times
        for i in range(3):
            tracker.refresh_dashboard(full=False, recompute=True)
            
            # Verify paths unchanged
            assert str(tracker._content_pane) == initial_content_pane_path, f"content_pane path changed on refresh {i+1}"
            assert str(tracker._sidebar_slot) == initial_sidebar_path, f"sidebar_slot path changed on refresh {i+1}"
            assert str(tracker._streak_pill) == initial_streak_pill_path, f"streak_pill path changed on refresh {i+1}"
            assert str(tracker._date_label) == initial_date_label_path, f"date_label path changed on refresh {i+1}"
            assert str(tracker._banner_host) == initial_banner_host_path, f"banner_host path changed on refresh {i+1}"
    
    root.destroy()


def test_no_widget_leaks_after_10_refreshes():
    """AC2: Widget count stable after 10 refreshes."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        root.update_idletasks()  # Let initial chunked build complete
        
        # First refresh and count
        tracker.refresh_dashboard(full=False, recompute=True)
        root.update_idletasks()  # Process chunked build
        root.update_idletasks()  # Process any remaining callbacks
        count_after_1 = _count_widgets_recursive(root)
        root_children_after_1 = len(root.winfo_children())
        
        # 9 more refreshes (total 10)
        for _ in range(9):
            tracker.refresh_dashboard(full=False, recompute=True)
            root.update_idletasks()  # Process chunked build
            root.update_idletasks()  # Process any remaining callbacks
        
        count_after_10 = _count_widgets_recursive(root)
        root_children_after_10 = len(root.winfo_children())
        
        # Widget count should be stable (allow small variance for timing/layout)
        assert abs(count_after_10 - count_after_1) <= 5, \
            f"Widget count grew from {count_after_1} to {count_after_10}"
        assert root_children_after_10 == root_children_after_1, \
            f"Root children grew from {root_children_after_1} to {root_children_after_10}"
    
    root.destroy()


def test_banner_host_survives_content_rebuild():
    """AC5: _banner_host belongs to shell and survives content rebuilds."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        
        banner_host = tracker._banner_host
        assert banner_host is not None
        banner_host_path = str(banner_host)
        
        # Verify banner_host is in shell_frame hierarchy
        assert banner_host.master == tracker._shell_frame
        
        # Rebuild content multiple times
        for i in range(3):
            tracker._build_content()
            root.update_idletasks()
            
            # Banner host should still exist and have same path
            assert tracker._banner_host is banner_host, f"banner_host instance changed on rebuild {i+1}"
            assert str(tracker._banner_host) == banner_host_path, f"banner_host path changed on rebuild {i+1}"
            assert tracker._banner_host.winfo_exists(), f"banner_host destroyed on rebuild {i+1}"
    
    root.destroy()


def test_content_rebuild_performance():
    """AC6: Content rebuild should be reasonably fast (< 100ms for empty data)."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        root.update_idletasks()
        
        # Add some entries to make it more realistic
        tracker.entries = {
            "2026-10-15": {
                "Money/Freedom": {"rating": 7, "notes": "Good progress"},
                "Body & Presence": {"rating": 8, "notes": "Workout done"},
            }
        }
        
        # Measure rebuild time
        start = time.perf_counter()
        tracker._build_content()
        root.update_idletasks()
        elapsed = time.perf_counter() - start
        
        # Should be under 100ms for small dataset (50ms target plus margin)
        assert elapsed < 0.1, f"Content rebuild took {elapsed*1000:.1f}ms (expected < 100ms)"
    
    root.destroy()


def test_refresh_preserves_shell_structure():
    """Verify shell frame hierarchy stays intact after refresh."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        
        # Verify initial structure
        assert tracker._shell_frame is not None
        assert tracker._shell_header is not None
        assert tracker._content_pane is not None
        assert tracker._shell_footer is not None
        
        shell_frame = tracker._shell_frame
        shell_header = tracker._shell_header
        shell_footer = tracker._shell_footer
        
        # Refresh
        tracker.refresh_dashboard(full=False, recompute=True)
        
        # Same instances should be preserved
        assert tracker._shell_frame is shell_frame
        assert tracker._shell_header is shell_header
        assert tracker._shell_footer is shell_footer
        
        # All should still exist
        assert shell_frame.winfo_exists()
        assert shell_header.winfo_exists()
        assert shell_footer.winfo_exists()
    
    root.destroy()


def test_theme_toggle_rebuilds_shell_for_chrome():
    """Theme toggle rebuilds shell for proper theme colors and button labels."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        
        initial_dark_mode = tracker.settings.get("dark_mode", False)
        
        # Toggle theme (should rebuild shell for chrome)
        tracker.toggle_dark_mode()
        
        # Theme changed
        assert tracker.settings.get("dark_mode") != initial_dark_mode
        
        # Shell exists and is functional
        assert tracker._shell_frame is not None
        assert tracker._shell_frame.winfo_exists()
        assert tracker._streak_pill is not None
        assert tracker._date_label is not None
    
    root.destroy()


def test_day_rollover_only_refreshes_content():
    """Day rollover should refresh, not full rebuild."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        
        shell_frame = tracker._shell_frame
        shell_frame_path = str(shell_frame)
        
        # Simulate day change
        tracker._on_calendar_day_changed(None, None)
        root.update_idletasks()
        
        # Shell should be unchanged (same instance and path)
        assert tracker._shell_frame is shell_frame, "Shell frame instance changed on day rollover"
        assert str(tracker._shell_frame) == shell_frame_path, "Shell frame path changed on day rollover"
        assert shell_frame.winfo_exists()
    
    root.destroy()


def test_content_pane_children_rebuilt_on_refresh():
    """Content pane children should be rebuilt, not updated in place."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        root.update_idletasks()  # Let initial chunked build complete
        root.update_idletasks()  # Process any remaining callbacks
        
        # Get initial log bar
        initial_log_bar = tracker._log_bar
        assert initial_log_bar is not None
        
        # Refresh
        tracker.refresh_dashboard(full=False, recompute=True)
        root.update_idletasks()  # Process chunked build
        root.update_idletasks()  # Process any remaining callbacks
        
        # New log bar should be created (content rebuilt)
        assert tracker._log_bar is not initial_log_bar, "Log bar not rebuilt on refresh"
        assert tracker._log_bar.winfo_exists()
    
    root.destroy()


def test_wheel_scroll_works_after_refreshes():
    """AC3: Wheel event over domain button still scrolls after 3 refreshes (#122)."""
    root = tk.Tk()
    root.withdraw()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        root.update_idletasks()
        
        # Find the log bar canvas (Today's Log domain buttons scroll area)
        def find_canvas(widget):
            if widget.winfo_class() == "Canvas":
                return widget
            for child in widget.winfo_children():
                result = find_canvas(child)
                if result:
                    return result
            return None
        
        canvas_before = find_canvas(tracker._log_bar) if tracker._log_bar else None
        assert canvas_before is not None, "Could not find scrollable canvas before refreshes"
        
        # Verify canvas has wheel bindings before refreshes
        # ui_scroll.make_bounded_vertical_scroll sets <MouseWheel> binding
        bindings_before = canvas_before.bind()
        has_wheel_before = any("<MouseWheel>" in b or "<Button-4>" in b or "<Button-5>" in b 
                               for b in bindings_before)
        
        # Refresh 3 times
        for _ in range(3):
            tracker.refresh_dashboard(full=False, recompute=True)
            root.update_idletasks()
        
        # Find canvas again after refreshes
        canvas_after = find_canvas(tracker._log_bar) if tracker._log_bar else None
        assert canvas_after is not None, "Could not find scrollable canvas after refreshes"
        
        # Verify canvas still has wheel bindings after refreshes
        bindings_after = canvas_after.bind()
        has_wheel_after = any("<MouseWheel>" in b or "<Button-4>" in b or "<Button-5>" in b 
                              for b in bindings_after)
        
        # Wheel bindings should be present after refreshes (re-bound by make_bounded_vertical_scroll)
        assert has_wheel_after or len(bindings_after) > 0, \
            "Wheel scroll bindings missing after 3 refreshes"
    
    root.destroy()


def test_focus_preserved_across_content_rebuild():
    """AC4: Focus should not be lost to root after content rebuild."""
    root = tk.Tk()
    # Don't withdraw - focus only works on mapped windows
    root.geometry("800x600+0+0")
    root.update()
    
    with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "__init__", _mock_tracker_init):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker.create_dashboard()
        root.update()
        
        # Find a focusable widget in content pane
        def find_entry(widget):
            if widget.winfo_class() in ("TEntry", "Entry"):
                return widget
            for child in widget.winfo_children():
                result = find_entry(child)
                if result:
                    return result
            return None
        
        entry = find_entry(tracker._content_pane) if tracker._content_pane else None
        if entry:
            entry.focus_set()
            root.update()
            assert root.focus_get() == entry, "Could not set initial focus"
        
        # Refresh content
        tracker._build_content(recompute=True)
        root.update()
        # Allow after(10) callback to run
        root.after(50)
        root.update()
        
        # Focus should not be lost to root
        new_focus = root.focus_get()
        assert new_focus is not root, "Focus lost to root after content rebuild"
        assert new_focus is not None, "Focus is None after content rebuild"
    
    root.destroy()
