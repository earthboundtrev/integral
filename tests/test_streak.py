"""Tests for honest-presence streak and journal gap repair."""

from datetime import datetime, timedelta

import journal
import streak


def _today():
    return datetime.now().date()


def test_streak_overall_life_entries():
    today = _today()
    entries = {
        today.strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
        (today - timedelta(days=1)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.get_streak(entries) == 2


def test_streak_grace_when_today_not_logged_yet():
    today = _today()
    entries = {
        (today - timedelta(days=1)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
        (today - timedelta(days=2)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.get_streak(entries, today=today) == 2


def test_streak_zero_when_gap_before_today():
    today = _today()
    entries = {
        (today - timedelta(days=2)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.get_streak(entries, today=today) == 0


def test_streak_life_today_after_gap_is_one():
    today = _today()
    entries = {
        today.strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
        (today - timedelta(days=2)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.get_streak(entries, today=today) == 1


def test_streak_journal_only_today():
    today = _today()
    j = journal.empty_journal()
    journal.upsert_entry(
        j,
        journal.create_entry(today.strftime("%Y-%m-%d"), "Showed up even if domains are empty."),
    )
    assert streak.get_streak({}, today=today, journal=j) == 1


def test_streak_fitness_only_today():
    today = _today()
    sessions = [{"date": today.strftime("%Y-%m-%d"), "program_id": "CC1"}]
    assert streak.get_streak({}, today=today, sessions=sessions) == 1


def test_streak_category_ignores_journal():
    today = _today()
    j = journal.empty_journal()
    journal.upsert_entry(
        j,
        journal.create_entry(today.strftime("%Y-%m-%d"), "Journal only."),
    )
    entries = {
        today.strftime("%Y-%m-%d"): {
            "Body & Presence": {"rating": 5},
            "Money/Freedom": {"rating": 5},
        },
        (today - timedelta(days=1)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.get_streak(entries, "Body & Presence", journal=j) == 2
    assert streak.get_streak(entries, "Money/Freedom", journal=j) == 1


def test_backdated_journal_repairs_gap():
    today = _today()
    yesterday = today - timedelta(days=1)
    older = today - timedelta(days=2)
    entries = {
        today.strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
        older.strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.get_streak(entries, today=today) == 1

    j = journal.empty_journal()
    journal.upsert_entry(
        j,
        journal.create_entry(
            yesterday.strftime("%Y-%m-%d"),
            "Sick day — rested instead of logging domains.",
            backdate_reason="Was ill and offline for the evening.",
        ),
    )
    assert streak.get_streak(entries, today=today, journal=j) == 3


def test_gap_repair_hint_when_yesterday_empty():
    today = _today()
    entries = {
        (today - timedelta(days=2)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    hint = streak.gap_repair_hint(today=today, entries=entries)
    assert hint is not None
    assert "journal" in hint.lower()


def test_gap_repair_hint_absent_when_yesterday_logged():
    today = _today()
    entries = {
        (today - timedelta(days=1)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    }
    assert streak.gap_repair_hint(today=today, entries=entries) is None


def test_gap_prompt_in_defaults():
    assert journal.GAP_PROMPT in journal.DEFAULT_PROMPTS
