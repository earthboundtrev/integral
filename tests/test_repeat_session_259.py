"""GitHub issue #259 — repeat chosen session, recent list, history hook."""

from __future__ import annotations

import sqlite3
from uuid import uuid4

import pytest

from fitness_repeat_ui import last_of_type_menu_entries, repeatable_rows
from progression.db import FitnessRepository
from progression.seed_loader import seed_all_fitness
from progression.session_repeat import (
    RepeatableSessionRow,
    dominant_family_label,
    list_repeatable_session_rows,
)
from progression.sessions import (
    find_latest_session_for_repeat,
    prefill_from_latest_session,
    prefill_from_session,
)


def make_repo(tmp_path) -> FitnessRepository:
    return FitnessRepository(str(tmp_path / "fitness.db"))


def _insert_session_raw(repo, session_id: str, date: str, created_at: str) -> None:
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO workout_sessions (id, date, notes, duration_minutes, body_weight_kg, created_at)
            VALUES (?, ?, '', NULL, NULL, ?)
            """,
            (session_id, date, created_at),
        )
        conn.commit()


def _insert_set_raw(
    repo,
    session_id: str,
    exercise_id: str,
    *,
    sets: int = 3,
    reps: int = 10,
    ordinal: int = 0,
) -> None:
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO workout_sets (
                id, session_id, exercise_id, sets, reps, hold_seconds, weight_kg, form_quality, ordinal, created_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, datetime('now'))
            """,
            (str(uuid4()), session_id, exercise_id, sets, reps, ordinal),
        )
        conn.commit()


def test_prefill_from_session_by_id_ignores_exclude_date(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    today = "2026-11-22"
    _insert_session_raw(repo, "same-day", today, "2026-11-22T12:00:00+00:00")
    _insert_set_raw(repo, "same-day", push.id)

    items, session, _notes = prefill_from_session(repo, "same-day")
    assert session is not None
    assert session.date == today
    assert len(items) == 1
    assert items[0]["exercise_id"] == push.id


def test_last_push_vs_last_overall(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    bridge = repo.get_exercise("cc1_bridge_01")
    form_date = "2026-11-22"
    _insert_session_raw(repo, "push-only", "2026-11-09", "2026-11-09T10:00:00+00:00")
    _insert_set_raw(repo, "push-only", push.id, sets=9, reps=9)
    _insert_session_raw(repo, "bridge-only", "2026-11-10", "2026-11-10T10:00:00+00:00")
    _insert_set_raw(repo, "bridge-only", bridge.id, sets=3, reps=3)

    overall_items, overall_id, _ = prefill_from_latest_session(repo, exclude_date=form_date)
    assert overall_id == "bridge-only"
    assert overall_items[0]["reps"] == 3

    push_items, push_id, _ = prefill_from_latest_session(
        repo, exclude_date=form_date, family="push"
    )
    assert push_id == "push-only"
    assert push_items[0]["reps"] == 9


def test_same_date_last_created_at_wins(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    form_date = "2026-11-22"
    _insert_session_raw(repo, "early", "2026-11-01", "2026-11-01T08:00:00+00:00")
    _insert_set_raw(repo, "early", push.id, sets=1, reps=1)
    _insert_session_raw(repo, "late", "2026-11-01", "2026-11-01T20:00:00+00:00")
    _insert_set_raw(repo, "late", push.id, sets=2, reps=2)

    session = find_latest_session_for_repeat(repo, exclude_date=form_date, family="push")
    assert session is not None
    assert session.id == "late"


def test_skips_form_date_for_last_of_type(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    form_date = "2026-11-22"
    _insert_session_raw(repo, "on-form", form_date, "2026-11-21T10:00:00+00:00")
    _insert_set_raw(repo, "on-form", push.id, sets=5, reps=5)
    _insert_session_raw(repo, "older", "2026-11-20", "2026-11-20T10:00:00+00:00")
    _insert_set_raw(repo, "older", push.id, sets=4, reps=4)

    session = find_latest_session_for_repeat(repo, exclude_date=form_date, family="push")
    assert session is not None
    assert session.id == "older"


def test_mixed_session_copies_all_families(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    bridge = repo.get_exercise("cc1_bridge_01")
    _insert_session_raw(repo, "mixed", "2026-11-08", "2026-11-08T10:00:00+00:00")
    _insert_set_raw(repo, "mixed", push.id, ordinal=0)
    _insert_set_raw(repo, "mixed", bridge.id, ordinal=1)

    items, _session, _ = prefill_from_session(repo, "mixed")
    assert len(items) == 2
    ids = {item["exercise_id"] for item in items}
    assert push.id in ids
    assert bridge.id in ids


def test_dominant_family_and_mixed_label():
    assert dominant_family_label({"push": 3, "pull": 1}) == "Push"
    assert dominant_family_label({"push": 2, "bridge": 2}) == "Mixed"


def test_repeatable_list_cap_skip_same_date_and_single_query(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    form_date = "2026-11-22"

    def forbidden_list_sets(self, session_id: str):
        raise AssertionError(f"per-session query loop for {session_id}")

    monkeypatch.setattr(FitnessRepository, "list_workout_sets", forbidden_list_sets)

    for idx in range(12):
        sid = f"s{idx}"
        _insert_session_raw(repo, sid, f"2026-10-{idx + 1:02d}", f"2026-10-{idx + 1:02d}T10:00:00+00:00")
        _insert_set_raw(repo, sid, push.id)
    _insert_session_raw(repo, "empty", "2026-09-01", "2026-09-01T10:00:00+00:00")
    _insert_session_raw(repo, "same", form_date, "2026-11-21T10:00:00+00:00")
    _insert_set_raw(repo, "same", push.id)

    rows = list_repeatable_session_rows(repo, exclude_date=form_date, limit=10)
    assert len(rows) == 10
    assert all(row.date != form_date for row in rows)


def test_list_repeatable_session_rows_tie_break_id(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    ts = "2026-10-10T10:00:00+00:00"
    _insert_session_raw(repo, "aaa", "2026-10-10", ts)
    _insert_set_raw(repo, "aaa", push.id)
    _insert_session_raw(repo, "zzz", "2026-10-10", ts)
    _insert_set_raw(repo, "zzz", push.id)

    rows = list_repeatable_session_rows(repo, exclude_date="", limit=10)
    assert rows[0].session_id == "zzz"


def test_history_repeat_callback(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    _insert_session_raw(repo, "hist", "2026-11-01", "2026-11-01T10:00:00+00:00")
    _insert_set_raw(repo, "hist", push.id)
    received: list[str] = []

    def on_repeat(session_id: str) -> None:
        received.append(session_id)

    on_repeat("hist")
    assert received == ["hist"]


def test_no_pull_session_leaves_queue_on_failure(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    items, sid, _ = prefill_from_latest_session(repo, exclude_date="2026-11-22", family="pull")
    assert items == []
    assert sid is None


def test_repeatable_rows_and_menu_entries(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    push = repo.get_exercise("cc1_push_01")
    bridge = repo.get_exercise("cc1_bridge_01")
    _insert_session_raw(repo, "p", "2026-11-05", "2026-11-05T10:00:00+00:00")
    _insert_set_raw(repo, "p", push.id)
    _insert_session_raw(repo, "b", "2026-11-06", "2026-11-06T10:00:00+00:00")
    _insert_set_raw(repo, "b", bridge.id)

    rows = repeatable_rows(repo, "2026-11-22")
    assert len(rows) == 2
    assert isinstance(rows[0], RepeatableSessionRow)
    menu = last_of_type_menu_entries(repo, exclude_date="2026-11-22")
    families = {entry[0] for entry in menu}
    assert "push" in families
    assert "bridge" in families