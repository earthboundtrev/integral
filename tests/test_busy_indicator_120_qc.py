"""Quick Capture busy indicator under heavy todo load (issue #120 retest)."""

from __future__ import annotations

import time
import tkinter as tk
import unittest
from unittest import mock

import quick_capture_ui
import todos
from busy_indicator import BusyIndicator


class TestQuickCaptureBusyIndicator120(unittest.TestCase):
    def test_heavy_todo_build_shows_delayed_indicator(self):
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
            tracker.settings = {}
            tracker.today_str.return_value = "2026-07-20"
            tracker._deep_work_session = None
            tracker._focus_shield = mock.MagicMock(active=False)
            tracker._quick_capture_win = None

            items = []
            for i in range(400):
                items.append(
                    {
                        "id": f"todo-{i}",
                        "text": f"Todo item {i}",
                        "done": False,
                        "work_date": "2026-07-20" if i < 300 else "2026-08-01",
                        "category": "Body & Presence",
                    }
                )
            tracker.todos = todos.normalize_todos({"items": items})

            shown = {"value": False}
            orig_show = BusyIndicator._show

            def tracked_show(self) -> None:
                shown["value"] = True
                orig_show(self)

            BusyIndicator._show = tracked_show  # type: ignore[method-assign]
            try:
                win = quick_capture_ui.open_quick_capture_panel(tracker)
                for _ in range(60):
                    root.update()
            finally:
                BusyIndicator._show = orig_show  # type: ignore[method-assign]

            self.assertTrue(
                shown["value"],
                "busy indicator should map during heavy Quick Capture build",
            )
            self.assertTrue(win.winfo_exists())
            win.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
