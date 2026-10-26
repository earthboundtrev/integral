"""Quick Capture todo rebuild must not block the UI thread (#121)."""

from __future__ import annotations

import inspect
import tkinter as tk
import unittest
from unittest import mock

import quick_capture_ui
import todos
from busy_indicator import HEARTBEAT_MAX_GAP_MS, measure_event_loop_gaps


class TestQuickCaptureTodoRebuild121(unittest.TestCase):
    def test_rebuild_uses_cooperative_scheduler(self):
        src = inspect.getsource(quick_capture_ui._QuickCaptureBuild._phase_todos)
        self.assertIn("_schedule_cooperative_todo_rebuild", src)
        self.assertIn("run_cooperative_steps", inspect.getsource(quick_capture_ui._QuickCaptureBuild))

    def test_heavy_rebuild_yields_to_event_loop(self):
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

            win = quick_capture_ui.open_quick_capture_panel(tracker)
            for _ in range(80):
                root.update()

            rebuild = tracker._qc_rebuild_todos
            self.assertIsNotNone(rebuild)
            root.after(1, rebuild)
            gaps = measure_event_loop_gaps(root, 0.55, tick_ms=10)

            self.assertFalse(
                getattr(win, "_qc_rebuild_running", True),
                "cooperative todo rebuild should finish within measurement window",
            )
            long_gaps = [g for g in gaps if g > HEARTBEAT_MAX_GAP_MS + 20]
            self.assertLessEqual(
                len(long_gaps),
                2,
                f"expected cooperative rebuild gaps <= {HEARTBEAT_MAX_GAP_MS}ms, got {long_gaps[:5]}",
            )
            win.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
