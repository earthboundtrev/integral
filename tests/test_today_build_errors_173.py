"""Today chunked build error handling (#173)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import pytest

import personal_dev_tracker
from status_banner import StatusBanner
from tests.mock_tracker import mock_tracker_init
from today_build_errors import BANNER_FIRST, BANNER_REPEAT, INLINE_PANEL_TEXT


@pytest.fixture
def tracker():
    root = tk.Tk()
    root.withdraw()
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        mock_tracker_init,
    ):
        t = personal_dev_tracker.PersonalDevelopmentTracker(root)
        t._ensure_shell()
        yield t
        try:
            root.destroy()
        except tk.TclError:
            pass


def _run_pending_build(tracker):
    for _ in range(40):
        tracker.root.update_idletasks()
        tracker.root.update()


def _patch_log_file(monkeypatch, path: Path) -> None:
    import integral_logging

    integral_logging.reset_logger_cache()
    monkeypatch.setattr("paths.app_log_file", lambda: str(path))
    monkeypatch.setattr("integral_logging.app_log_file", lambda: str(path))


def _all_widget_text(parent) -> str:
    parts: list[str] = []
    for w in parent.winfo_children():
        try:
            parts.append(str(w.cget("text")))
        except tk.TclError:
            pass
        parts.append(_all_widget_text(w))
    return " ".join(parts)


def test_chunk2_failure_shows_panel_and_banner_no_messagebox(tracker, tmp_path, monkeypatch):
    _patch_log_file(monkeypatch, tmp_path / "integral.log")

    def boom():
        raise RuntimeError("forced chunk 2")

    with patch.object(tracker, "create_todays_log_bar", side_effect=boom):
        tracker._build_content(recompute=False)
        _run_pending_build(tracker)

    pane_text = _all_widget_text(tracker._content_pane)
    assert INLINE_PANEL_TEXT.split(".")[0] in pane_text
    banner = tracker.ensure_status_banner()
    assert banner._frame is not None
    assert BANNER_FIRST in banner._message_var.get()


def test_chunk1_failure_still_builds_log_bar(tracker, tmp_path, monkeypatch):
    _patch_log_file(monkeypatch, tmp_path / "integral.log")

    with patch.object(tracker, "_get_insights", side_effect=ValueError("forced chunk 1")):
        tracker._build_content(recompute=True)
        _run_pending_build(tracker)

    assert tracker._log_bar is not None
    banner = tracker.ensure_status_banner()
    assert banner._frame is not None


def test_chunk1_error_no_messagebox(tracker, tmp_path, monkeypatch):
    _patch_log_file(monkeypatch, tmp_path / "integral.log")

    with patch.object(tracker, "_get_insights", side_effect=ValueError("forced chunk 1")):
        tracker._build_content(recompute=True)
        _run_pending_build(tracker)

    banner = tracker.ensure_status_banner()
    assert banner._frame is not None


def test_b1_non_dict_entry_shows_error_not_spinner(tracker, tmp_path, monkeypatch):
    _patch_log_file(monkeypatch, tmp_path / "integral.log")
    today = tracker.today_str()
    tracker.entries[today] = {"Money/Freedom": 5}
    tracker._build_content(recompute=True)
    _run_pending_build(tracker)

    banner = tracker.ensure_status_banner()
    assert banner._frame is not None
    children = tracker._content_pane.winfo_children()
    assert children, "content pane should not be empty spinner-only"
    loading = [c for c in children if "Loading" in str(c)]
    assert not loading


def test_traceback_written_to_log(tracker, tmp_path, monkeypatch):
    log_path = tmp_path / "integral.log"
    _patch_log_file(monkeypatch, log_path)

    with patch.object(tracker, "create_todays_log_bar", side_effect=RuntimeError("log fail")):
        tracker._build_content(recompute=False)
        _run_pending_build(tracker)

    assert log_path.is_file()
    assert "log fail" in log_path.read_text(encoding="utf-8")


def test_successful_build_keeps_unrelated_status_banner(tracker, tmp_path, monkeypatch):
    _patch_log_file(monkeypatch, tmp_path / "integral.log")
    banner = tracker.ensure_status_banner()
    banner.show_success("Saved.")
    tracker.root.update()

    tracker._build_content(recompute=False)
    _run_pending_build(tracker)

    assert tracker.ensure_status_banner()._kind == "success"


def test_repeat_failure_updates_banner_text(tracker, tmp_path, monkeypatch):
    _patch_log_file(monkeypatch, tmp_path / "integral.log")

    with patch.object(tracker, "create_todays_log_bar", side_effect=RuntimeError("a")):
        tracker._build_content(recompute=False)
        _run_pending_build(tracker)
    first = tracker.ensure_status_banner()._message_var.get()
    assert BANNER_FIRST in first

    with patch.object(tracker, "create_todays_log_bar", side_effect=RuntimeError("b")):
        tracker._build_content(recompute=False)
        _run_pending_build(tracker)
    second = tracker.ensure_status_banner()._message_var.get()
    assert BANNER_REPEAT in second

