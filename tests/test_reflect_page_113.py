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

from tests.mock_tracker import mock_tracker_init as _mock_tracker_init


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


def test_clear_rating_with_prefilled_notes_allowed(tracker):
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    cat = "Body & Presence"
    existing = {"rating": 7, "notes": "from earlier"}
    row = DomainReflectRow(
        cat,
        tracker.categories[cat],
        existing,
        tracker.theme,
        host,
        canvas,
    )
    row.rating_row.clear()
    assert row.validation_error() is None
    assert row.should_remove_entry() is True


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
    mock_banner = MagicMock(show_success=MagicMock(), show_info=MagicMock(), show_error=MagicMock())
    with patch("reflect_page_ui.get_status_banner", return_value=mock_banner):
        save_reflect_page(tracker, rows, date_str=date_str, page_error=page_error)

    assert date_str in tracker.entries
    assert "Body & Presence" in tracker.entries[date_str]
    assert "Money/Freedom" not in tracker.entries[date_str]
    assert len(save_calls) == 1
    assert save_calls[0].get("flush", False) is False


def test_save_reflect_failure_shows_error_banner(tracker):
    date_str = tracker.today_str()
    cat = "Body & Presence"
    tracker.entries = {date_str: {cat: {"rating": 5}}}
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
    row.rating_row.set_rating(8)
    page_error = tk.Label(host, text="")

    def fail_save(**kwargs):
        cb = kwargs.get("on_complete")
        if cb:
            cb(False, RuntimeError("disk full"))

    tracker.save_data = fail_save
    tracker._invalidate_caches = MagicMock()
    mock_banner = MagicMock(show_success=MagicMock(), show_info=MagicMock(), show_error=MagicMock())
    with patch("reflect_page_ui.get_status_banner", return_value=mock_banner):
        save_reflect_page(tracker, [row], date_str=date_str, page_error=page_error)
    mock_banner.show_error.assert_called_once()
    assert tracker.entries[date_str][cat]["rating"] == 5


def test_save_reflect_clears_prior_rating(tracker):
    date_str = tracker.today_str()
    cat = "Body & Presence"
    tracker.entries = {date_str: {cat: {"rating": 7, "notes": "keep"}}}
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
    row.rating_row.clear()
    page_error = tk.Label(host, text="")

    tracker.save_data = lambda **kwargs: kwargs.get("on_complete")(True, None) if kwargs.get("on_complete") else None
    tracker._invalidate_caches = MagicMock()
    tracker.refresh_dashboard = MagicMock()
    tracker._get_insights = MagicMock(return_value=[])
    mock_banner = MagicMock(show_success=MagicMock(), show_info=MagicMock(), show_error=MagicMock())
    with patch("reflect_page_ui.get_status_banner", return_value=mock_banner):
        save_reflect_page(tracker, [row], date_str=date_str, page_error=page_error)
    assert cat not in tracker.entries.get(date_str, {})


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
    mock_banner = MagicMock(show_success=MagicMock(), show_info=MagicMock(), show_error=MagicMock())
    with patch("reflect_page_ui.get_status_banner", return_value=mock_banner):
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


def test_clear_last_domain_then_rate_another_no_keyerror(tracker):
    """Clearing the only logged domain then rating another must not pop date mid-loop."""
    date_str = tracker.today_str()
    money = "Money/Freedom"
    career = "Creative/Mental Work"
    tracker.entries = {date_str: {money: {"rating": 6, "notes": "only"}}}
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    rows = [
        DomainReflectRow(money, tracker.categories[money], tracker.entries[date_str][money], tracker.theme, host, canvas),
        DomainReflectRow(career, tracker.categories[career], {}, tracker.theme, host, canvas),
    ]
    rows[0].rating_row.clear()
    rows[1].rating_row.set_rating(7)
    page_error = tk.Label(host, text="")
    tracker.save_data = lambda **kwargs: kwargs.get("on_complete")(True, None) if kwargs.get("on_complete") else None
    tracker._invalidate_caches = MagicMock()
    tracker.refresh_dashboard = MagicMock()
    tracker._get_insights = MagicMock(return_value=[])
    mock_banner = MagicMock(show_success=MagicMock(), show_info=MagicMock(), show_error=MagicMock())
    with patch("reflect_page_ui.get_status_banner", return_value=mock_banner):
        save_reflect_page(tracker, rows, date_str=date_str, page_error=page_error)
    assert money not in tracker.entries.get(date_str, {})
    assert tracker.entries[date_str][career]["rating"] == 7


def test_clear_after_first_save_persists_second_clear(tracker):
    date_str = tracker.today_str()
    cat = "Body & Presence"
    tracker.entries = {date_str: {cat: {"rating": 8, "notes": "x"}}}
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
    row.commit_saved_baseline(tracker.entries[date_str][cat])
    row.rating_row.clear()
    assert row.should_remove_entry() is True


def test_notes_after_clear_rating_requires_rerate(tracker):
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    cat = "Body & Presence"
    existing = {"rating": 7, "notes": "original"}
    row = DomainReflectRow(
        cat,
        tracker.categories[cat],
        existing,
        tracker.theme,
        host,
        canvas,
    )
    row.rating_row.clear()
    row.notes.delete("1.0", tk.END)
    row.notes.insert("1.0", "changed after clear")
    assert row.validation_error() == "Rate this domain to save its notes"


def test_full_form_on_closed_reloads_one_domain(tracker):
    date_str = tracker.today_str()
    cat_a = "Body & Presence"
    cat_b = "Money/Freedom"
    tracker.entries = {
        date_str: {
            cat_a: {"rating": 5, "notes": "stored"},
            cat_b: {"rating": 3},
        }
    }
    host = tk.Frame(tracker.root)
    canvas = tk.Canvas(host)
    row_a = DomainReflectRow(
        cat_a,
        tracker.categories[cat_a],
        tracker.entries[date_str][cat_a],
        tracker.theme,
        host,
        canvas,
    )
    row_b = DomainReflectRow(
        cat_b,
        tracker.categories[cat_b],
        tracker.entries[date_str][cat_b],
        tracker.theme,
        host,
        canvas,
    )
    row_b.rating_row.set_rating(9)
    closed_args = []

    def on_closed(saved: bool) -> None:
        closed_args.append(saved)
        if saved:
            row_a.reload_from_entry(tracker.entries[date_str][cat_a])

    tracker.entries[date_str][cat_a] = {"rating": 8, "notes": "from full form"}
    on_closed(True)
    assert row_a.rating_row.get_rating() == 8
    assert row_a.notes_text() == "from full form"
    assert row_b.rating_row.get_rating() == 9


def test_open_log_dialog_returns_toplevel_and_on_closed(tracker):
    tracker.root.update_idletasks()
    fired = []

    def on_closed(saved: bool) -> None:
        fired.append(saved)

    dialog = tracker.open_log_dialog("Body & Presence", on_closed=on_closed)
    assert isinstance(dialog, tk.Toplevel)
    close_fn = getattr(dialog, "_integral_request_close_log", None)
    assert close_fn is not None
    close_fn(saved=False)
    tracker.root.update_idletasks()
    assert fired == [False]


def test_reflect_save_on_done_after_page_error_destroyed(tracker):
    """Async save callback must finish even if the reflect window was destroyed (#113)."""
    date_str = tracker.today_str()
    cat = "Body & Presence"
    tracker.entries = {date_str: {cat: {"rating": 5}}}
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
    done_flags: list[bool] = []

    def fake_save(**kwargs):
        page_error.destroy()
        cb = kwargs.get("on_complete")
        if cb:
            cb(True, None)

    tracker.save_data = fake_save
    tracker._invalidate_caches = MagicMock()
    tracker.refresh_dashboard = MagicMock()
    tracker._get_insights = MagicMock(return_value=[])
    save_reflect_page(
        tracker,
        [row],
        date_str=date_str,
        page_error=page_error,
        on_done=done_flags.append,
    )
    assert done_flags == [True]


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
