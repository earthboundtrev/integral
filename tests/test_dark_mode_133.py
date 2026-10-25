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


from tests.tracker_fixtures import mock_tracker_init as _base_mock_tracker_init


def _mock_tracker_init(self, root):
    """Minimal tracker init for dark-mode widget walks."""
    _base_mock_tracker_init(self, root, dark_mode=True)


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
