"""Regression tests for journal window layout helpers (#99)."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
import unittest
from unittest.mock import MagicMock

import journal
import inspect

from journal_ui import (
    JOURNAL_WINDOW_MINSIZE,
    _entry_list_hover_index,
    _truncate_text_to_px,
    show_journal_window,
)
from theme import apply_theme, get_theme


def _mock_tracker(root: tk.Tk) -> MagicMock:
    tracker = MagicMock()
    tracker.root = root
    tracker.theme = get_theme(False)
    apply_theme(root, tracker.theme)
    tracker.entries = {}
    tracker.sessions = []
    tracker.creative_projects = {"projects": []}
    # Read the date from the same clock journal.create_entry uses, so the
    # fixture stays "today" on any day the tests run.
    today = journal.date.today().isoformat()
    tracker.today_str.return_value = today
    tracker._invalidate_caches = MagicMock()
    tracker.refresh_dashboard = MagicMock()
    tracker.save_data = MagicMock()
    tracker.open_integral_link = MagicMock()
    tracker._reminder_scheduler = None
    tracker.journal = journal.empty_journal()
    for idx in range(3):
        journal.upsert_entry(
            tracker.journal,
            journal.create_entry(
                today,
                f"Body {idx}",
                title="A very long journal title that should truncate in the list " + str(idx),
            ),
        )
    return tracker


def _journal_toplevels(root: tk.Tk) -> list[tk.Toplevel]:
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists()]


def _widget_texts(widget: tk.Misc) -> list[str]:
    texts: list[str] = []
    try:
        texts.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        texts.extend(_widget_texts(child))
    return texts


def _find_entries_listbox(parent: tk.Misc) -> tk.Listbox | None:
    found: list[tk.Listbox] = []

    def walk(widget: tk.Misc) -> None:
        if isinstance(widget, tk.Listbox):
            try:
                if int(widget.cget("height")) == 5:
                    return
            except (tk.TclError, ValueError):
                pass
            found.append(widget)
        for child in widget.winfo_children():
            walk(child)

    walk(parent)
    return found[0] if found else None


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


class TestJournalWindowLayout(unittest.TestCase):
    def test_action_buttons_include_reload_on_two_rows(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = _mock_tracker(root)
            show_journal_window(tracker)
            win = _journal_toplevels(root)[0]
            win.update_idletasks()
            texts = _widget_texts(win)
            joined = " ".join(texts)
            self.assertIn("Reload from system editor", joined)
            self.assertIn("Edit in system editor", joined)
            self.assertIn("Save Entry", joined)
            win.destroy()
        finally:
            root.destroy()

    def test_configure_refill_keeps_empty_selection_after_new(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = _mock_tracker(root)
            show_journal_window(tracker)
            win = _journal_toplevels(root)[0]
            win.update_idletasks()
            entry_list = _find_entries_listbox(win)
            assert entry_list is not None
            entry_list.selection_set(0)
            win.update_idletasks()
            for text in _widget_texts(win):
                if text == "New":
                    break
            else:
                self.fail("New button not found")
            new_btn = None

            def find_new(widget: tk.Misc) -> None:
                nonlocal new_btn
                try:
                    if widget.cget("text") == "New":
                        new_btn = widget
                        return
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    find_new(child)

            find_new(win)
            assert new_btn is not None
            new_btn.invoke()
            win.update_idletasks()
            self.assertEqual(entry_list.curselection(), ())
            width = entry_list.winfo_width()
            win.geometry(f"{width + 40}x760")
            win.update_idletasks()
            entry_list.event_generate("<Configure>")
            win.update_idletasks()
            self.assertEqual(entry_list.curselection(), ())
            win.destroy()
        finally:
            root.destroy()

    def test_header_wraplength_fits_minimum_window_width(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            tracker = _mock_tracker(root)
            show_journal_window(tracker)
            win = _journal_toplevels(root)[0]
            win.update_idletasks()
            win.geometry(f"{JOURNAL_WINDOW_MINSIZE[0]}x760")
            win.update_idletasks()
            muted = None
            for widget in win.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, tk.Widget):
                        try:
                            if child.winfo_class() == "TLabel" and "Markdown-lite" in str(
                                child.cget("text")
                            ):
                                muted = child
                                break
                        except tk.TclError:
                            pass
            self.assertIsNotNone(muted)
            assert muted is not None
            wrap = int(muted.cget("wraplength"))
            self.assertLessEqual(wrap, JOURNAL_WINDOW_MINSIZE[0])
            win.destroy()
        finally:
            root.destroy()

    def test_entry_list_hover_index_ignores_gap_between_rows(self) -> None:
        root = tk.Tk()
        root.geometry("280x160")
        try:
            lb = tk.Listbox(root, height=6)
            lb.pack()
            for i in range(3):
                lb.insert(tk.END, f"Row {i}")
            root.update()
            bbox0 = lb.bbox(0)
            assert bbox0 is not None
            inside0 = bbox0[1] + bbox0[3] // 2
            self.assertEqual(_entry_list_hover_index(lb, inside0, 3), 0)
            bbox1 = lb.bbox(1)
            assert bbox1 is not None
            gap_y = bbox1[1] - 1
            if gap_y > bbox0[1]:
                self.assertIsNone(_entry_list_hover_index(lb, gap_y, 3))
            inside1 = bbox1[1] + bbox1[3] // 2
            self.assertEqual(_entry_list_hover_index(lb, inside1, 3), 1)
            bbox2 = lb.bbox(2)
            assert bbox2 is not None
            below_last = bbox2[1] + bbox2[3] + 5
            self.assertIsNone(_entry_list_hover_index(lb, below_last, 3))
        finally:
            root.destroy()

    def test_entry_list_tooltip_reuses_single_toplevel(self) -> None:
        src = inspect.getsource(show_journal_window)
        self.assertIn("_ensure_entry_list_tooltip", src)
        self.assertIn("list_tooltip.withdraw()", src)
        self.assertIn('attributes("-topmost", True)', src)
        self.assertIn("list_tooltip_idx[0] != idx", src)


if __name__ == "__main__":
    unittest.main()
