"""Tests for one-screen daily reflection (#113)."""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import personal_dev_tracker
from entry_payload import build_entry_payload
from reflect_page_ui import (
    DomainReflectRow,
    RatingRow,
    ordered_reflect_domains,
    save_reflect_page,
)


def _mock_tracker_init(self, root):
    from fitness.engine import load_program_definitions
    import creative_projects
    import day_plans
    import journal
    import practices
    import todos
    import youtube_takeout
    from paths import data_file
    from theme import get_theme
    from focus_shield import FocusShieldSession

    self.root = root
    self.categories = self.get_default_categories()
    self.entries = {}
    self.settings = {"dark_mode": False}
    self.sessions = []
    self.milestones = []
    self.journal = journal.empty_journal()
    self.creative_projects = creative_projects.empty_creative_projects()
    self.youtube_history = youtube_takeout.empty_youtube_history()
    self.day_plans = day_plans.empty_day_plans()
    self.program_state = {}
    self.programs = load_program_definitions()
    self.data_path = data_file()
    self.vault_passphrase = None
    self.theme = get_theme(False)
    self._insights_cache = None
    self._streak_cache = {}
    self._session_counts_cache = None
    self._save_after_id = None
    self._pending_save_payload = None
    self._fitness_state_dirty = False
    self._dashboard_ready = False
    self._categories_tab_built = False
    self._theme_dark = None
    self._log_bar = None
    self._todays_log_filter = ""
    self._todays_log_status = "all"
    self._activity_grid = None
    self._guidance_panel = None
    self._streak_pill = None
    self._date_label = None
    self._overview_stats_label = None
    self._reminder_scheduler = None
    self._day_watch = None
    self._categories_tab_frame = None
    self._notebook = None
    self._streak_details_window = None
    self._deep_work_session = None
    self._deep_work_after_id = None
    self._deep_work_banner = None
    self._deep_work_timer_label = None
    self._quick_capture_win = None
    self._focus_shield = FocusShieldSession()
    self._focus_shield_after_id = None
    self.todos = todos.empty_todos()
    self.practices = practices.empty_practices()
    self._nav_buttons = {}
    self._nav_pack_order = []
    self._nav_frame = None
    self._shell_frame = None
    self._shell_header = None
    self._content_pane = None
    self._shell_footer = None
    self._banner_host = None
    self._sidebar_slot = None
    self.insights = []
    self._open_windows = {}
    self._status_banner = None


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


def test_ordered_reflect_domains_pins_first(tracker):
    tracker.settings = {"todays_log": {"pinned_domains": ["Body & Presence"]}}
    names = ordered_reflect_domains(list(tracker.categories.keys()), tracker.settings)
    assert names[0] == "Body & Presence"


def test_rating_row_toggle_clear(tracker):
    row = RatingRow(tracker.root, tracker.theme)
    row.set_rating(5)
    assert row.get_rating() == 5
    row._pick(5, toggle=True)
    assert row.get_rating() is None


def test_notes_without_rating_inline_error(tracker):
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    cat = "Body & Presence"
    row = DomainReflectRow(
        cat,
        tracker.categories[cat],
        {},
        tracker.theme,
        host,
        canvas,
    )
    row.notes.insert("1.0", "some notes")
    assert row.validation_error() == "Rate this domain to save its notes"


def test_save_reflect_only_rated_domains(tracker):
    tracker.entries = {}
    date_str = tracker.today_str()
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    rows = []
    for cat in ("Body & Presence", "Money/Freedom"):
        rows.append(
            DomainReflectRow(
                cat,
                tracker.categories[cat],
                {},
                tracker.theme,
                host,
                canvas,
            )
        )
    rows[0].rating_row.set_rating(8)

    page_error = tk.Label(host, text="")
    save_calls = []

    def fake_save(**kwargs):
        save_calls.append(kwargs)
        cb = kwargs.get("on_complete")
        if cb:
            cb(True, None)

    tracker.save_data = fake_save
    tracker._invalidate_caches = MagicMock()
    tracker.refresh_dashboard = MagicMock()
    tracker._get_insights = MagicMock(return_value=[])
    tracker.ensure_status_banner = MagicMock(
        return_value=MagicMock(show_success=MagicMock(), show_info=MagicMock())
    )

    save_reflect_page(tracker, rows, date_str=date_str, page_error=page_error)

    assert date_str in tracker.entries
    assert "Body & Presence" in tracker.entries[date_str]
    assert "Money/Freedom" not in tracker.entries[date_str]
    assert len(save_calls) == 1
    assert save_calls[0].get("flush", False) is False


def test_orphan_notes_block_save(tracker):
    date_str = tracker.today_str()
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    row = DomainReflectRow(
        "Body & Presence",
        tracker.categories["Body & Presence"],
        {},
        tracker.theme,
        host,
        canvas,
    )
    row.notes.insert("1.0", "orphan")
    page_error = tk.Label(host, text="")
    tracker.save_data = MagicMock()
    save_reflect_page(tracker, [row], date_str=date_str, page_error=page_error)
    tracker.save_data.assert_not_called()


def test_save_reflect_merge_does_not_clobber_checklist(tracker):
    date_str = tracker.today_str()
    cat = "Body & Presence"
    tracker.entries = {
        date_str: {
            cat: {
                "rating": 5,
                "checklist": {"Walked today": True},
                "notes": "from form",
            }
        }
    }
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    row = DomainReflectRow(
        cat,
        tracker.categories[cat],
        tracker.entries[date_str][cat],
        tracker.theme,
        host,
        canvas,
    )
    row.rating_row.set_rating(6)
    page_error = tk.Label(host, text="")

    tracker.save_data = lambda **kwargs: kwargs.get("on_complete")(True, None) if kwargs.get("on_complete") else None
    tracker._invalidate_caches = MagicMock()
    tracker.refresh_dashboard = MagicMock()
    tracker._get_insights = MagicMock(return_value=[])
    tracker.ensure_status_banner = MagicMock(
        return_value=MagicMock(show_success=MagicMock(), show_info=MagicMock())
    )

    save_reflect_page(tracker, [row], date_str=date_str, page_error=page_error)
    saved = tracker.entries[date_str][cat]
    assert saved["rating"] == 6
    assert saved["checklist"]["Walked today"] is True


def test_save_log_matches_build_entry_payload_golden(tracker):
    cat = tracker.categories["Body & Presence"]
    item = cat["checklist"][0]
    manual = build_entry_payload(
        cat,
        7,
        checklist={item: True},
        metrics=None,
        notes="note",
    )
    assert manual == {"rating": 7, "notes": "note", "checklist": {item: True}}


def test_show_reflect_opens_page(tracker):
    with patch("reflect_page_ui.open_reflect_page") as mock_open:
        tracker.show_reflect()
        mock_open.assert_called_once_with(tracker)


def test_reflect_page_open_under_one_second(tracker):
    import time

    start = time.perf_counter()
    from reflect_page_ui import open_reflect_page

    win = open_reflect_page(tracker)
    tracker.root.update_idletasks()
    elapsed = time.perf_counter() - start
    try:
        win.destroy()
    except tk.TclError:
        pass
    assert elapsed < 1.0, f"Reflect page took {elapsed:.2f}s (18 domains collapsed)"
