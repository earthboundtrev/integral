"""Quick Capture list cap (#219) and build persistence (#220)."""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest import mock

import quick_capture
import quick_capture_ui
import todos
from personal_dev_tracker import PersonalDevelopmentTracker


def _theme() -> dict:
    return {
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


def _tracker_mock(*, todo_items: list[dict], settings: dict | None = None) -> mock.MagicMock:
    tracker = mock.MagicMock()
    tracker.theme = _theme()
    tracker.categories = {"Body & Presence": {}}
    tracker.settings = settings or {}
    tracker.today_str.return_value = "2026-07-20"
    tracker._deep_work_session = None
    tracker._focus_shield = mock.MagicMock(active=False)
    tracker._quick_capture_win = None
    tracker.todos = todos.normalize_todos({"items": todo_items})
    tracker.save_data = mock.MagicMock()
    tracker.ensure_status_banner.return_value = mock.MagicMock()
    return tracker


class TestQuickCaptureTodoCap219(unittest.TestCase):
    def test_compute_prioritizes_today_over_upcoming(self) -> None:
        today_n, upcoming_n = quick_capture.compute_rendered_todo_counts(
            today_count=5,
            upcoming_count=400,
            visible_today_limit=50,
            visible_upcoming_limit=50,
        )
        self.assertEqual(today_n, 5)
        self.assertEqual(upcoming_n, 50)

    def test_no_show_more_at_exactly_fifty(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            items = [
                {
                    "id": f"t{i}",
                    "text": f"Todo {i}",
                    "done": False,
                    "work_date": "2026-07-20",
                    "category": "",
                }
                for i in range(50)
            ]
            tracker = _tracker_mock(todo_items=items)
            tracker.root = root
            win = quick_capture_ui.open_quick_capture_panel(tracker)
            for _ in range(80):
                root.update()
            self.assertFalse(getattr(win, "_qc_building", True))
            build = getattr(win, "_qc_build", None)
            self.assertIsNotNone(build)
            show_more = [
                w
                for w in build.today_list.winfo_children()
                if hasattr(w, "_qc_show_more_link")
            ]
            self.assertEqual(show_more, [])
            self.assertLess(build.inner.winfo_reqheight(), 32767)
            win.destroy()
        finally:
            root.destroy()

    def test_thousand_todos_capped_without_x_limits(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            items = []
            for i in range(1000):
                items.append(
                    {
                        "id": f"todo-{i}",
                        "text": f"Todo item {i}",
                        "done": False,
                        "work_date": "2026-07-20" if i < 500 else "2026-08-01",
                        "category": "Body & Presence",
                    }
                )
            tracker = _tracker_mock(todo_items=items)
            tracker.root = root
            win = quick_capture_ui.open_quick_capture_panel(tracker)
            for _ in range(120):
                root.update()
            build = win._qc_build
            today_rows = [
                c
                for c in build.today_list.winfo_children()
                if not hasattr(c, "_qc_show_more_link")
            ]
            upcoming_rows = [
                c
                for c in build.upcoming_list.winfo_children()
                if not hasattr(c, "_qc_show_more_link")
            ]
            self.assertLessEqual(len(today_rows) + len(upcoming_rows), 300)
            self.assertLess(build.inner.winfo_reqheight(), 32767)
            win.destroy()
        finally:
            root.destroy()


class TestQuickCaptureShowMoreLabels(unittest.TestCase):
    def test_format_show_more_uses_actual_batch_size(self) -> None:
        self.assertEqual(
            quick_capture_ui._format_show_more_label(12, 12),
            "Show 12 more (12 left)",
        )
        self.assertEqual(
            quick_capture_ui._format_show_more_label(50, 200),
            "Show 50 more (200 left)",
        )


class TestQuickCaptureBuildPersistence220(unittest.TestCase):
    def test_settings_for_save_hides_enabled_during_build(self) -> None:
        settings = {
            "quick_capture": {"enabled": True, "collapsed": {"today": False, "upcoming": False}},
            quick_capture.QC_BUILDING_SETTINGS_KEY: True,
        }
        saved = quick_capture.settings_for_save(settings)
        self.assertTrue(saved.get(quick_capture.QC_BUILDING_SETTINGS_KEY))
        self.assertFalse(saved["quick_capture"]["enabled"])

    def test_build_failure_clears_marker_and_disables(self) -> None:
        settings = {
            "quick_capture": {"enabled": True},
            quick_capture.QC_BUILDING_SETTINGS_KEY: True,
        }
        out = quick_capture.commit_build_failure(settings)
        self.assertNotIn(quick_capture.QC_BUILDING_SETTINGS_KEY, out)
        self.assertFalse(quick_capture.is_quick_capture_enabled(out))

    def test_enable_while_panel_open_persists_without_building_marker(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = _tracker_mock(
                todo_items=[
                    {
                        "id": "t1",
                        "text": "Todo",
                        "done": False,
                        "work_date": "2026-07-20",
                        "category": "",
                    }
                ],
            )
            tracker.root = root
            win = quick_capture_ui.open_quick_capture_panel(tracker)
            for _ in range(40):
                root.update()
            self.assertTrue(quick_capture_ui.quick_capture_panel_is_open(tracker))
            tracker.settings = quick_capture.apply_quick_capture_settings(
                tracker.settings, {"enabled": True}
            )
            if quick_capture_ui.quick_capture_panel_is_open(tracker):
                tracker.settings = quick_capture.commit_build_success(tracker.settings)
            else:
                tracker.settings[quick_capture.QC_BUILDING_SETTINGS_KEY] = True
            self.assertNotIn(quick_capture.QC_BUILDING_SETTINGS_KEY, tracker.settings)
            self.assertTrue(quick_capture.is_quick_capture_enabled(tracker.settings))
            win.destroy()
        finally:
            root.destroy()

    def test_startup_with_building_marker_skips_open(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = PersonalDevelopmentTracker.__new__(PersonalDevelopmentTracker)
            tracker.root = root
            tracker.theme = _theme()
            tracker.settings = {
                "quick_capture": {"enabled": True, "collapsed": {"today": False, "upcoming": False}},
                quick_capture.QC_BUILDING_SETTINGS_KEY: True,
            }
            tracker.save_data = mock.MagicMock()
            tracker.ensure_status_banner = mock.MagicMock(return_value=mock.MagicMock())
            opened = {"called": False}

            def fake_open(_t):
                opened["called"] = True
                return mock.MagicMock()

            with mock.patch("quick_capture_ui.open_quick_capture_panel", fake_open):
                tracker._sync_quick_capture_at_startup()
            self.assertFalse(opened["called"])
            tracker.save_data.assert_called()
            self.assertFalse(quick_capture.is_quick_capture_enabled(tracker.settings))
            self.assertNotIn(quick_capture.QC_BUILDING_SETTINGS_KEY, tracker.settings)
        finally:
            root.destroy()

    def test_build_error_shows_banner_and_persists_disabled(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = _tracker_mock(
                todo_items=[],
                settings={"quick_capture": {"enabled": True, "collapsed": {"today": False, "upcoming": False}}},
            )
            tracker.root = root
            tracker.settings[quick_capture.QC_BUILDING_SETTINGS_KEY] = True

            original_phase = quick_capture_ui._QuickCaptureBuild._phase_todos

            def boom(self) -> None:
                raise RuntimeError("synthetic build failure")

            quick_capture_ui._QuickCaptureBuild._phase_todos = boom  # type: ignore[method-assign]
            try:
                quick_capture_ui.open_quick_capture_panel(tracker)
                for _ in range(30):
                    root.update()
            finally:
                quick_capture_ui._QuickCaptureBuild._phase_todos = original_phase  # type: ignore[method-assign]

            tracker.save_data.assert_called()
            self.assertFalse(quick_capture.is_quick_capture_enabled(tracker.settings))
            tracker.ensure_status_banner.return_value.show_error.assert_called()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
