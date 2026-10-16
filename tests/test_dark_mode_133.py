"""Dark mode plain tk widget styling (issue #133)."""

import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

import personal_dev_tracker
import ui_scroll
from goto_ui import open_goto_palette
from theme import (
    DARK,
    LIGHT,
    collect_forbidden_backgrounds,
    get_theme,
    is_forbidden_chrome_background,
    reapply_listbox_colors,
    reapply_text_widget_colors,
    style_listbox,
    style_menu,
    style_text_widget,
    apply_theme,
)


class TestForbiddenBackgrounds(unittest.TestCase):
    def test_forbidden_includes_platform_defaults(self):
        for value in ("#d9d9d9", "SystemButtonFace", "SystemWindow", "#f0f0f0", "white", "#ffffff"):
            self.assertTrue(is_forbidden_chrome_background(value), value)


class TestScrollChrome(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.theme = get_theme(True)

    def tearDown(self):
        self.root.destroy()

    def test_bounded_vertical_scroll_uses_surface_not_system_grey(self):
        host = ttk.Frame(self.root)
        _wrap, _inner, canvas = ui_scroll.make_bounded_vertical_scroll(
            host,
            max_height=120,
            theme=self.theme,
            chrome_bg=self.theme["surface"],
        )
        self.root.update_idletasks()
        self.assertEqual(canvas.cget("bg"), self.theme["surface"])
        self.assertFalse(is_forbidden_chrome_background(canvas.cget("bg")))
        forbidden = collect_forbidden_backgrounds(host)
        self.assertEqual(forbidden, [])


class TestMenusAndThemeToggle(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_menu_uses_theme_surface(self):
        theme = get_theme(True)
        menu = tk.Menu(self.root, tearoff=0)
        style_menu(menu, theme)
        self.assertEqual(str(menu.cget("bg")), theme["surface"])
        self.assertFalse(is_forbidden_chrome_background(str(menu.cget("bg"))))

    def test_apply_theme_rethemes_listbox(self):
        theme_dark = get_theme(True)
        apply_theme(self.root, theme_dark)
        lb = tk.Listbox(self.root)
        lb.pack()
        self.root.update_idletasks()
        self.assertEqual(lb.cget("bg"), theme_dark["text_bg"])

        theme_light = get_theme(False)
        apply_theme(self.root, theme_light)
        self.assertEqual(lb.cget("bg"), theme_light["text_bg"])

    def test_reapply_text_preserves_layout(self):
        theme = get_theme(True)
        text = tk.Text(self.root)
        style_text_widget(text, theme)
        text.configure(padx=2, pady=3, font=("Courier", 9))
        text.pack()
        reapply_text_widget_colors(text, get_theme(False))
        self.assertEqual(int(text.cget("padx")), 2)
        self.assertEqual(int(text.cget("pady")), 3)
        self.assertEqual(str(text.cget("font")), "Courier 9")

    def test_reapply_listbox_preserves_border(self):
        theme = get_theme(True)
        lb = tk.Listbox(self.root)
        style_listbox(lb, theme)
        lb.configure(borderwidth=2)
        reapply_listbox_colors(lb, get_theme(False))
        self.assertEqual(int(lb.cget("borderwidth")), 2)


def _mock_tracker_init(self, root):
    """Minimal tracker init for dark-mode widget walks."""
    from fitness.engine import load_program_definitions
    import creative_projects
    import day_plans
    import journal
    import practices
    import todos
    import youtube_takeout
    from paths import data_file

    self.root = root
    self.categories = self.get_default_categories()
    self.entries = {}
    self.settings = {"dark_mode": True}
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
    self.theme = get_theme(True)
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


class TestWidgetWalkDarkMode(unittest.TestCase):
    def test_today_shell_no_forbidden_backgrounds(self):
        root = tk.Tk()
        root.withdraw()
        with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "save_data", lambda *_a, **_k: None):
            with patch.object(
                personal_dev_tracker.PersonalDevelopmentTracker,
                "__init__",
                _mock_tracker_init,
            ):
                tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
                tracker.create_dashboard()
                root.update_idletasks()
                hits = collect_forbidden_backgrounds(root)
                self.assertEqual(hits, [], hits)
        root.destroy()

    def test_theme_toggle_preserves_other_toplevel(self):
        root = tk.Tk()
        root.withdraw()
        with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "save_data", lambda *_a, **_k: None):
            with patch.object(
                personal_dev_tracker.PersonalDevelopmentTracker,
                "__init__",
                _mock_tracker_init,
            ):
                tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
                tracker.create_dashboard()
                journal_win = tk.Toplevel(root)
                journal_win.title("Journal stub")
                journal_win.geometry("200x100")
                marker = tk.Label(journal_win, text="stay open")
                marker.pack()
                root.update_idletasks()
                tracker.toggle_dark_mode()
                root.update_idletasks()
                self.assertTrue(journal_win.winfo_exists())
                self.assertTrue(marker.winfo_exists())
        root.destroy()

    def test_theme_toggle_preserves_overview_categories_window(self):
        root = tk.Tk()
        root.withdraw()
        with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "save_data", lambda *_a, **_k: None):
            with patch.object(
                personal_dev_tracker.PersonalDevelopmentTracker,
                "__init__",
                _mock_tracker_init,
            ):
                tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
                tracker.create_dashboard()
                tracker.show_streak_details()
                root.update_idletasks()
                overview_win = tracker._streak_details_window
                self.assertIsNotNone(overview_win)
                tracker.toggle_dark_mode()
                root.update_idletasks()
                self.assertIsNotNone(tracker._streak_details_window)
                self.assertTrue(overview_win.winfo_exists())
        root.destroy()

    def test_goto_palette_no_forbidden_after_dark_theme(self):
        root = tk.Tk()
        root.withdraw()
        with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "save_data", lambda *_a, **_k: None):
            with patch.object(
                personal_dev_tracker.PersonalDevelopmentTracker,
                "__init__",
                _mock_tracker_init,
            ):
                tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
                tracker.create_dashboard()
                open_goto_palette(tracker)
                root.update_idletasks()
                goto = tracker._goto_window
                self.assertIsNotNone(goto)
                hits = collect_forbidden_backgrounds(goto)
                self.assertEqual(hits, [], hits)
        root.destroy()


class TestComboboxDropdownOptions(unittest.TestCase):
    def test_option_add_includes_combobox_listbox(self):
        root = tk.Tk()
        root.withdraw()
        theme = get_theme(True)
        apply_theme(root, theme)
        val = root.option_get("*TCombobox*Listbox.background", "")
        self.assertIn(val, (theme["surface"], ""))
        root.destroy()


if __name__ == "__main__":
    unittest.main()
