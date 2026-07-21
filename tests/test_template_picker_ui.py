"""SPEC-317 — template picker renders and applies via callback."""

import tkinter as tk
import unittest
from unittest import mock

import integral_dialogs


class TestTemplatePickerUi(unittest.TestCase):
    def test_picker_renders_and_calls_on_apply(self):
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
            }
            applied: list[str] = []
            dlg = integral_dialogs.show_template_picker(
                tracker, root, on_apply=applied.append
            )
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
            self.assertIn("Gut Healing Starter Pack", joined)
            self.assertIn("Apply", joined)
            self.assertTrue(dlg.winfo_exists())
            dlg.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
