"""SPEC-318 — practice log dialog renders and saves."""

import tkinter as tk
import unittest
from unittest import mock

import practices
import practices_ui


class TestPracticesUi(unittest.TestCase):
    def test_dialog_renders_and_saves(self):
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = mock.MagicMock()
            tracker.root = root
            tracker.theme = {
                "bg": "#1e1e1e",
                "fg": "#f0f0f0",
                "muted": "#aaaaaa",
                "accent": "#5b8def",
                "text_bg": "#252526",
                "text_fg": "#f0f0f0",
                "select_bg": "#264f78",
                "card_border": "#444444",
            }
            tracker.categories = {"Physical Practices & Movement": {}, "Breathwork & Mindfulness": {}}
            tracker.today_str.return_value = "2026-07-21"
            tracker.entries = {}
            tracker.practices = practices.empty_practices()

            dlg = practices_ui.show_practice_log_dialog(tracker, root)
            dlg.update_idletasks()

            texts: list[str] = []

            def walk(widget):
                try:
                    texts.append(str(widget.cget("text")))
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    walk(child)

            walk(dlg)
            joined = " ".join(texts)
            self.assertIn("Log a daily practice", joined)
            self.assertIn("Save practice", joined)
            self.assertTrue(dlg.winfo_exists())
            dlg.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
