"""Quick Capture panel must render visible controls (theme-safe scroll host)."""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest import mock

import quick_capture_ui


class TestQuickCaptureUi(unittest.TestCase):
    def test_open_quick_capture_panel_shows_labeled_controls(self):
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = mock.MagicMock()
            tracker.root = root
            tracker.theme = {
                "bg": "#1e1e1e",
                "fg": "#f0f0f0",
                "muted": "#aaaaaa",
                "card": "#2a2a2a",
                "card_border": "#444444",
                "accent": "#5b8def",
                "text_bg": "#252526",
                "text_fg": "#f0f0f0",
                "select_bg": "#264f78",
            }
            tracker.categories = {"Body & Presence": {}}
            tracker.todos = {"items": []}
            tracker.today_str.return_value = "2026-07-20"
            tracker._deep_work_session = None
            tracker._focus_shield = mock.MagicMock(active=False)
            tracker._quick_capture_win = None

            win = quick_capture_ui.open_quick_capture_panel(tracker)
            win.update_idletasks()

            texts: list[str] = []

            def walk(widget):
                try:
                    texts.append(str(widget.cget("text")))
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    walk(child)

            walk(win)
            joined = " ".join(texts)
            self.assertIn("Quick Capture", joined)
            self.assertTrue("Today" in joined or "todos" in joined.lower())
            self.assertIn("Deep Work", joined)
            self.assertTrue(win.winfo_exists())
            win.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
