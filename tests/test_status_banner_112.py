"""Tests for status banners and save UX (#112)."""

from __future__ import annotations

import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from inline_validation import validate_rating_1_10
from status_banner import SUCCESS_HIDE_MS, StatusBanner


class TestInlineRatingValidation(unittest.TestCase):
    def test_rating_edge_cases(self):
        for bad in (0, 11, 95, -1, "", "abc"):
            self.assertIsNotNone(validate_rating_1_10(bad))
        for good in (1, 10, "1", "10"):
            self.assertIsNone(validate_rating_1_10(good))


class TestStatusBanner(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        host = tk.Frame(self.root)
        host.pack()
        theme = {
            "success_bg": "#ECFDF5",
            "success": "#047857",
            "error_bg": "#FEE2E2",
            "error": "#B91C1C",
            "warning_bg": "#FEF3C7",
            "fg": "#1A1D21",
            "card_border": "#D8DCE3",
        }
        self.banner = StatusBanner(host, theme)

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_show_and_dismiss(self):
        self.banner.show_success("Saved.")
        self.root.update()
        self.assertIsNotNone(self.banner._frame)
        self.banner.dismiss()
        self.root.update()
        self.assertIsNone(self.banner._frame)

    def test_auto_hide_success(self):
        self.banner.show_success("Saved.")
        self.root.update()
        self.root.after(SUCCESS_HIDE_MS + 50, self.root.quit)
        self.root.mainloop()
        self.assertIsNone(self.banner._frame)

    def test_success_does_not_replace_error_until_dismissed(self):
        self.banner.show_error("Save failed.")
        self.root.update()
        self.banner.show_success("Saved.")
        self.root.update()
        self.assertEqual(self.banner._kind, "error")
        self.assertIsNotNone(self.banner._deferred_success)
        self.banner.dismiss()
        self.root.update()
        self.assertEqual(self.banner._kind, "success")

    def test_error_replaces_success(self):
        self.banner.show_success("Saved.")
        self.root.update()
        self.banner.show_error("Failed.")
        self.root.update()
        self.assertEqual(self.banner._kind, "error")


class TestSavedMessageboxRemoved(unittest.TestCase):
    def test_no_saved_messagebox_in_fitness_ui(self):
        text = Path("fitness_ui.py").read_text(encoding="utf-8")
        self.assertNotIn('messagebox.showinfo("Saved"', text)
        self.assertNotIn('messagebox.showinfo("Logged"', text)

    def test_no_saved_messagebox_in_save_log(self):
        text = Path("personal_dev_tracker.py").read_text(encoding="utf-8")
        start = text.index("def save_log(")
        end = text.index("\n    def ", start + 1)
        block = text[start:end]
        self.assertNotIn("messagebox.showinfo", block)
        self.assertNotIn('messagebox.showwarning("Date"', block)


class TestSaveFailureBanner(unittest.TestCase):
    def test_save_failure_shows_error_banner(self):
        root = tk.Tk()
        root.withdraw()
        try:
            host = tk.Frame(root)
            host.pack()
            theme = {"error_bg": "#FEE2E2", "error": "#DC2626", "fg": "#111", "card_border": "#ccc"}
            banner = StatusBanner(host, theme)

            from personal_dev_tracker import PersonalDevelopmentTracker

            tracker = SimpleNamespace(
                root=root,
                theme=theme,
                _status_banner=banner,
                _save_after_callbacks=[],
                _save_write_in_progress=False,
                _pending_save_payload=None,
                ensure_status_banner=lambda: banner,
                _notify_save_complete=lambda ok, err: tracker._save_after_callbacks.clear(),
            )
            tracker._show_save_error_banner = lambda err: PersonalDevelopmentTracker._show_save_error_banner(
                tracker, err
            )
            PersonalDevelopmentTracker._finish_save(tracker, False, PermissionError("denied"))
            root.update()
            self.assertEqual(banner._kind, "error")
            self.assertIn("denied", banner._message_var.get())
        finally:
            root.destroy()

    def test_flush_save_monkeypatch_raises(self):
        root = tk.Tk()
        root.withdraw()
        try:
            from personal_dev_tracker import DATA_FILE, PersonalDevelopmentTracker

            host = tk.Frame(root)
            host.pack()
            theme = {"error_bg": "#FEE2E2", "error": "#DC2626", "fg": "#111", "card_border": "#ccc"}
            banner = StatusBanner(host, theme)
            tracker = SimpleNamespace(
                root=root,
                theme=theme,
                settings={},
                vault_passphrase=None,
                _status_banner=banner,
                _save_after_callbacks=[],
                _save_write_in_progress=False,
                _save_after_id=None,
                _pending_save_payload={"entries": {}},
                ensure_status_banner=lambda: banner,
                _notify_save_complete=lambda ok, err: tracker._save_after_callbacks.clear(),
            )
            tracker._show_save_error_banner = lambda err: PersonalDevelopmentTracker._show_save_error_banner(
                tracker, err
            )
            tracker._invoke_save_callbacks = lambda cbs, ok, err: PersonalDevelopmentTracker._invoke_save_callbacks(
                tracker, cbs, ok, err
            )
            tracker._schedule_chained_flush = lambda sync=False: PersonalDevelopmentTracker._schedule_chained_flush(
                tracker, sync=sync
            )
            with patch("personal_dev_tracker.save_data_file", side_effect=OSError("locked")) as mock_save:
                PersonalDevelopmentTracker._flush_save(tracker, sync=True)
            root.update()
            self.assertEqual(banner._kind, "error")
            self.assertIn("data.json", banner._message_var.get() or DATA_FILE)
            self.assertIsNone(tracker._pending_save_payload)
            self.assertEqual(mock_save.call_count, 1)
        finally:
            root.destroy()

    def test_flush_save_locked_does_not_recurse(self):
        root = tk.Tk()
        root.withdraw()
        try:
            from personal_dev_tracker import PersonalDevelopmentTracker

            host = tk.Frame(root)
            host.pack()
            theme = {"error_bg": "#FEE2E2", "error": "#DC2626", "fg": "#111", "card_border": "#ccc"}
            banner = StatusBanner(host, theme)
            tracker = SimpleNamespace(
                root=root,
                theme=theme,
                settings={},
                vault_passphrase=None,
                _status_banner=banner,
                _save_after_callbacks=[],
                _save_write_in_progress=False,
                _save_after_id=None,
                _pending_save_payload={"entries": {}},
                ensure_status_banner=lambda: banner,
            )
            tracker._show_save_error_banner = lambda err: PersonalDevelopmentTracker._show_save_error_banner(
                tracker, err
            )
            tracker._invoke_save_callbacks = lambda cbs, ok, err: PersonalDevelopmentTracker._invoke_save_callbacks(
                tracker, cbs, ok, err
            )
            tracker._schedule_chained_flush = lambda sync=False: PersonalDevelopmentTracker._schedule_chained_flush(
                tracker, sync=sync
            )
            banner_errors: list[str] = []

            def count_errors(err):
                banner_errors.append(str(err))
                PersonalDevelopmentTracker._show_save_error_banner(tracker, err)

            tracker._show_save_error_banner = count_errors
            with patch("personal_dev_tracker.save_data_file", side_effect=OSError("locked")) as mock_save:
                PersonalDevelopmentTracker._flush_save(tracker, sync=True)
            self.assertEqual(mock_save.call_count, 1)
            self.assertEqual(len(banner_errors), 1)
            self.assertIsNone(tracker._pending_save_payload)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
