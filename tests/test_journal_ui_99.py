"""Regression tests for journal window layout helpers (#99)."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
import unittest

from journal_ui import _truncate_text_to_px


class TestJournalUiTruncate(unittest.TestCase):
    def test_truncate_adds_ellipsis_when_too_wide(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            font = tkfont.Font(family="Helvetica", size=10)
            long_text = "2026-01-15  A very long journal title that should not fit"
            max_width = font.measure("2026-01-15  Short title")
            truncated = _truncate_text_to_px(long_text, font, max_width)
            self.assertTrue(truncated.endswith("…"))
            self.assertLess(font.measure(truncated), font.measure(long_text))
            self.assertLessEqual(font.measure(truncated), max_width)
        finally:
            root.destroy()

    def test_truncate_keeps_short_text(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            font = tkfont.Font(family="Helvetica", size=10)
            short = "2026-01-01  Note"
            self.assertEqual(_truncate_text_to_px(short, font, 400), short)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
