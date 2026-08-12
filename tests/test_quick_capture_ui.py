"""Quick Capture panel must render visible controls (theme-safe scroll host)."""

from __future__ import annotations

import inspect
import tkinter as tk
import unittest
from unittest import mock

import focus_shield
import quick_capture_ui
from personal_dev_tracker import PersonalDevelopmentTracker


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

    def test_dashboard_wires_quick_capture_on_today_log_and_footer(self):
        """#76 — Today's Log strip + footer both expose Quick Capture."""
        today_src = inspect.getsource(PersonalDevelopmentTracker.create_todays_log_bar)
        footer_src = inspect.getsource(PersonalDevelopmentTracker.create_dashboard)
        self.assertIn('text="Quick Capture"', today_src)
        self.assertIn("toggle_quick_capture", today_src)
        journal = today_src.find('text="Journal"')
        more = today_src.find('text="More…')
        self.assertGreaterEqual(journal, 0)
        self.assertGreater(more, journal)
        between = today_src[journal:more]
        self.assertIn('text="Quick Capture"', between)
        self.assertIn('text="Quick Capture"', footer_src)
        self.assertIn("toggle_quick_capture", footer_src)

    def test_deep_work_shield_dialog_keeps_start_visible_with_long_list(self):
        """#80 — long focus-shield lists still expose a Start control."""
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
            tracker.settings = {}
            tracker.save_data = mock.MagicMock()
            tracker.start_deep_work = mock.MagicMock()

            fake_windows = [
                focus_shield.WindowInfo(
                    hwnd=i,
                    title=f"Window {i} " + ("x" * 40),
                    process_name=f"app{i}.exe",
                    pid=1000 + i,
                )
                for i in range(40)
            ]

            with (
                mock.patch.object(focus_shield, "is_supported", return_value=True),
                mock.patch.object(
                    focus_shield, "list_top_level_windows", return_value=fake_windows
                ),
            ):
                quick_capture_ui._show_deep_work_shield_dialog(tracker, parent=root)
                root.update_idletasks()

                dlg = None
                for child in root.winfo_children():
                    if isinstance(child, tk.Toplevel) and child.winfo_exists():
                        if str(child.title()) == "Start Deep Work":
                            dlg = child
                            break
                self.assertIsNotNone(dlg)

                start_btn = None
                cancel_btn = None

                def walk(widget):
                    nonlocal start_btn, cancel_btn
                    try:
                        text = str(widget.cget("text"))
                        if text == "Start":
                            start_btn = widget
                        elif text == "Cancel":
                            cancel_btn = widget
                    except tk.TclError:
                        pass
                    for child in widget.winfo_children():
                        walk(child)

                walk(dlg)
                self.assertIsNotNone(start_btn)
                self.assertIsNotNone(cancel_btn)
                # Footer widgets are not descendants of the scroll canvas.
                in_canvas = False
                cur: tk.Misc | None = start_btn
                while cur is not None and cur is not dlg:
                    if isinstance(cur, tk.Canvas):
                        in_canvas = True
                        break
                    cur = cur.master
                self.assertFalse(in_canvas, "Start must be pinned outside scroll body")
                try:
                    dlg.attributes("-topmost", False)
                except tk.TclError:
                    pass
                dlg.destroy()
                root.update_idletasks()
        finally:
            try:
                for child in list(root.winfo_children()):
                    try:
                        child.destroy()
                    except tk.TclError:
                        pass
                root.destroy()
            except tk.TclError:
                pass

    def test_deep_work_shield_dialog_uses_pinned_footer_shell(self):
        src = inspect.getsource(quick_capture_ui._show_deep_work_shield_dialog)
        self.assertIn("create_dialog_shell", src)
        self.assertIn('text="Start"', src)


if __name__ == "__main__":
    unittest.main()
