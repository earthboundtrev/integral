"""Dark mode plain tk widget styling (issue #133)."""

import tkinter as tk
from tkinter import ttk
import unittest

import ui_scroll
from theme import (
    DARK,
    collect_forbidden_backgrounds,
    get_theme,
    is_forbidden_chrome_background,
    style_menu,
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


if __name__ == "__main__":
    unittest.main()
