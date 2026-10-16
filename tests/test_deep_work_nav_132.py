"""Deep Work nav chrome driven by NAV_ITEMS (#132)."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import deep_work
import nav_items
from goto_ui import build_goto_destinations
from more_menu_ui import build_more_menu_rows
from tests.test_sidebar_131 import _mock_tracker_init

import personal_dev_tracker


@pytest.fixture
def tracker():
    root = tk.Tk()
    root.withdraw()
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        _mock_tracker_init,
    ):
        t = personal_dev_tracker.PersonalDevelopmentTracker(root)
        t._ensure_shell()
        yield t
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_nav_policy_hides_q3_sidebar_destinations():
    assert nav_items.is_hidden_during_deep_work(item_id="fitness_hub", tracker=MagicMock(_deep_work_session=MagicMock(running=True)))
    assert nav_items.is_hidden_during_deep_work(item_id="reflect", tracker=MagicMock(_deep_work_session=MagicMock(running=True)))
    assert "Fitness Hub" in deep_work.DEEP_WORK_HIDDEN_NAV_LABELS
    assert "Reflect" in deep_work.DEEP_WORK_HIDDEN_NAV_LABELS


def test_sidebar_hides_items_during_deep_work(tracker):
    tracker._deep_work_session = MagicMock(running=True)
    tracker._apply_deep_work_chrome()
    tracker.root.update_idletasks()
    packed = {
        spec.id: tracker._sidebar_nav_frames[spec.id].winfo_manager() == "pack"
        for spec in nav_items.sidebar_nav_items()
    }
    assert packed["today"] is True
    assert packed["journal"] is True
    assert packed["fitness_hub"] is False
    assert packed["reflect"] is False
    assert packed["graphs"] is False
    assert tracker._sidebar_goto_frame is not None
    assert tracker._sidebar_goto_frame.winfo_manager() != "pack"
    assert tracker._sidebar_deep_work_hint_row.winfo_manager() == "pack"


def test_sidebar_restores_after_deep_work(tracker):
    tracker._deep_work_session = MagicMock(running=True)
    tracker._apply_deep_work_chrome()
    tracker._deep_work_session = None
    tracker._apply_deep_work_chrome()
    tracker.root.update_idletasks()
    for spec in nav_items.sidebar_nav_items():
        assert tracker._sidebar_nav_frames[spec.id].winfo_manager() == "pack"
    assert tracker._sidebar_goto_frame.winfo_manager() == "pack"
    assert tracker._sidebar_deep_work_hint_row.winfo_manager() != "pack"


def test_more_menu_keeps_work_modes_group_during_deep_work():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = MagicMock(running=True)
    labels = [row.label for row in build_more_menu_rows(tracker)]
    assert "Quick Capture" in labels
    assert "Writing Projects" in labels
    assert "Deep Work" in labels
    assert "Guidance" not in labels


def test_goto_excludes_hidden_destinations_during_deep_work():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = MagicMock(running=True)
    tracker.categories = {"Money/Freedom": {}}
    labels = {d["label"] for d in build_goto_destinations(tracker)}
    assert "Today" in labels
    assert "Journal" in labels
    assert "Guidance" not in labels
    assert "Fitness Hub" not in labels
    assert any(label.startswith("Log ") for label in labels)


def test_deep_work_end_button_is_accent_while_active(tracker):
    tracker._deep_work_session = MagicMock(running=True)
    tracker._ensure_deep_work_banner()
    tracker._apply_deep_work_chrome()
    assert tracker._deep_work_end_btn is not None
    assert tracker._deep_work_end_btn.cget("style") == "Accent.TButton"
    tracker._deep_work_session = None
    tracker._apply_deep_work_chrome()
    assert tracker._deep_work_end_btn.cget("style") == "TButton"


def test_shortcut_to_hidden_destination_is_blocked(tracker):
    tracker._deep_work_session = MagicMock(running=True)
    with patch.object(nav_items, "deep_work_blocks_action", return_value=True) as blocked:
        tracker._run_nav_shortcut("reflect", tracker.show_reflect)
        blocked.assert_called_once()
    with patch.object(tracker, "first_unlogged_category", return_value="Money/Freedom") as first:
        with patch.object(tracker, "open_log_dialog") as open_log:
            tracker._deep_work_session = None
            tracker.show_reflect()
            first.assert_called_once()
            open_log.assert_called_once_with("Money/Freedom")
