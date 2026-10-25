"""Regression tests for journal list fill performance (#131 PR tester)."""

from __future__ import annotations

import time
import tkinter as tk
from datetime import date
from unittest.mock import patch

import journal
import personal_dev_tracker

from tests.conftest import pump_tk_until
from tests.mock_tracker import mock_tracker_init


def _tracker_with_entries(root: tk.Tk, count: int):
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        mock_tracker_init,
    ):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker._ensure_shell()
        tracker.journal = journal.empty_journal()
        today = date.today().isoformat()
        for idx in range(count):
            journal.upsert_entry(
                tracker.journal,
                journal.create_entry(
                    today,
                    f"Body {idx}",
                    title=f"Entry title {idx} with extra words for truncation",
                    entry_id=f"entry-{idx:05d}",
                ),
            )
        return tracker


def test_large_journal_fill_does_not_reentrant_configure_storm():
    """One cooperative fill — not triple refill from Configure during pump."""
    root = tk.Tk()
    root.withdraw()
    tracker = _tracker_with_entries(root, 120)
    win = tk.Toplevel(root)
    win.geometry("1040x760")

    clear_count = 0
    original_delete = tk.Listbox.delete

    def counting_delete(self, *args):
        nonlocal clear_count
        if args == (0, tk.END):
            clear_count += 1
        return original_delete(self, *args)

    from deferred_toplevel import run_deferred_toplevel_build
    from journal_ui import show_journal_window

    done = False

    def build() -> None:
        nonlocal done
        show_journal_window(tracker, host=win)
        done = True

    with patch.object(tk.Listbox, "delete", counting_delete):
        run_deferred_toplevel_build(
            win,
            theme=tracker.theme,
            busy_label="Loading Journal…",
            build=build,
        )
        assert pump_tk_until(root, lambda: done, timeout_s=5.0)
    # Pre-fix storm was ~3× entry count (configure re-entry during pump).
    assert clear_count <= 3, f"expected at most 3 list clears, got {clear_count}"
    try:
        win.destroy()
    except tk.TclError:
        pass
    root.destroy()


def test_small_deferred_journal_fill_populates_list():
    root = tk.Tk()
    root.withdraw()
    tracker = _tracker_with_entries(root, 5)
    win = tk.Toplevel(root)
    win.geometry("1040x760")

    from deferred_toplevel import run_deferred_toplevel_build
    from journal_ui import show_journal_window

    done = False

    def build() -> None:
        nonlocal done
        show_journal_window(tracker, host=win)
        done = True

    run_deferred_toplevel_build(
        win,
        theme=tracker.theme,
        busy_label="Loading Journal…",
        build=build,
    )
    def _find_listbox(widget: tk.Misc) -> tk.Listbox | None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Listbox):
                return child
            nested = _find_listbox(child)
            if nested is not None:
                return nested
        return None

    assert pump_tk_until(root, lambda: done, timeout_s=3.0)

    def _list_has_five() -> bool:
        listbox = _find_listbox(win)
        return listbox is not None and listbox.size() == 5

    assert pump_tk_until(root, _list_has_five, timeout_s=3.0)
    win.destroy()
    root.destroy()


def test_journal_730_entry_cold_fill_under_budget():
    """Cold cache: 730-row deferred fill should stay well under the old ~11s path."""
    root = tk.Tk()
    root.deiconify()
    tracker = _tracker_with_entries(root, 730)
    win = tk.Toplevel(root)
    win.geometry("1040x760")
    win.deiconify()

    from deferred_toplevel import run_deferred_toplevel_build
    from journal_ui import show_journal_window

    started = time.perf_counter()

    def build() -> None:
        show_journal_window(tracker, host=win)

    indicator = run_deferred_toplevel_build(
        win,
        theme=tracker.theme,
        busy_label="Loading Journal…",
        build=build,
    )

    def _find_listbox(widget: tk.Misc) -> tk.Listbox | None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Listbox):
                return child
            nested = _find_listbox(child)
            if nested is not None:
                return nested
        return None

    def fill_complete() -> bool:
        lb = _find_listbox(win)
        try:
            return lb is not None and lb.size() == 730
        except tk.TclError:
            return False

    assert pump_tk_until(root, fill_complete, timeout_s=10.0)
    elapsed = time.perf_counter() - started
    assert elapsed < 2.5, f"730-entry journal fill took {elapsed:.2f}s"
    indicator.stop()
    win.destroy()
    root.destroy()


def test_journal_escape_from_focused_child_cancels_and_closes():
    """Real Esc path: focused listbox child must cancel fill and destroy the window."""
    root = tk.Tk()
    root.deiconify()
    tracker = _tracker_with_entries(root, 200)
    win = tk.Toplevel(root)
    win.geometry("1040x760")
    win.deiconify()

    from deferred_toplevel import run_deferred_toplevel_build
    from journal_ui import show_journal_window

    def build() -> None:
        show_journal_window(tracker, host=win)

    run_deferred_toplevel_build(
        win,
        theme=tracker.theme,
        busy_label="Loading Journal…",
        build=build,
    )

    def _find_listbox(widget: tk.Misc) -> tk.Listbox | None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Listbox):
                return child
            nested = _find_listbox(child)
            if nested is not None:
                return nested
        return None

    def listbox_ready() -> bool:
        lb = _find_listbox(win)
        return lb is not None

    assert pump_tk_until(root, listbox_ready, timeout_s=3.0)
    listbox = _find_listbox(win)
    assert listbox is not None
    listbox.focus_set()
    root.update_idletasks()
    listbox.event_generate("<KeyPress-Escape>")
    root.update()
    assert pump_tk_until(root, lambda: not win.winfo_exists(), timeout_s=2.0)
    root.destroy()


def test_journal_destroy_mid_cooperative_fill_no_tclerror():
    root = tk.Tk()
    root.withdraw()
    tracker = _tracker_with_entries(root, 80)
    win = tk.Toplevel(root)
    win.geometry("1040x760")

    from deferred_toplevel import run_deferred_toplevel_build
    from journal_ui import show_journal_window

    def build() -> None:
        show_journal_window(tracker, host=win)

    run_deferred_toplevel_build(
        win,
        theme=tracker.theme,
        busy_label="Loading Journal…",
        build=build,
    )

    def destroy_when_busy() -> bool:
        try:
            if win.winfo_exists():
                win.destroy()
                return True
        except tk.TclError:
            return True
        return False

    pump_tk_until(root, destroy_when_busy, timeout_s=2.0)
    pump_tk_until(root, lambda: True, timeout_s=0.5)
    root.destroy()
