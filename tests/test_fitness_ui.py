import sqlite3
from uuid import uuid4

import pytest

from fitness_ui import (
    copy_previous_pending_set_item,
    ensure_fitness_seeded,
    format_exercise_picker_label,
    format_pending_set_line,
    list_exercise_rows,
    remove_pending_set_at,
    submit_performance,
)
from progression.db import FitnessRepository
from progression.seed_loader import seed_all_fitness
from progression.sessions import (
    create_workout_session,
    link_session_to_body_presence,
    prefill_from_latest_session,
)


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def test_ensure_fitness_seeded_loads_all_books_when_empty(tmp_path):
    repo = make_repo(tmp_path)
    assert ensure_fitness_seeded(repo) is True
    assert len(repo.list_exercises()) == 177
    assert ensure_fitness_seeded(repo) is False


def test_submit_performance_marks_mastered_and_unlocks_next(tmp_path):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    rows = list_exercise_rows(repo)
    wall = next(r for r in rows if r["name"] == "Wall Push-ups")
    incline = next(r for r in rows if r["name"] == "Incline Push-ups")

    submit_performance(repo, wall["id"], {"sets": 3, "reps": 50}, session_id="s1")
    result = submit_performance(repo, wall["id"], {"sets": 3, "reps": 50}, session_id="s2")
    assert result["status"] == "mastered"

    rows_after = list_exercise_rows(repo)
    incline_after = next(r for r in rows_after if r["id"] == incline["id"])
    assert incline_after["status"] == "available"


def test_seed_all_includes_multiple_books(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    books = {ex.source_book for ex in repo.list_exercises()}
    assert "CC1" in books
    assert "SS" in books
    assert "OG" in books
    assert "EC" in books
    assert "FTR" in books
    assert "CC2" in books


def test_workout_session_persists_sets(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    wall = repo.get_exercise("cc1_push_01")
    session = create_workout_session(
        repo,
        "2026-06-27",
        [{"exercise_id": wall.id, "sets": 3, "reps": 20}],
        notes="Morning push",
        duration_minutes=30,
    )
    sessions = repo.list_workout_sessions()
    assert len(sessions) == 1
    sets = repo.list_workout_sets(session.id)
    assert len(sets) == 1
    assert sets[0].reps == 20


def test_link_session_to_body_presence(tmp_path):
    data = {"categories": {}, "entries": {}}
    updated = link_session_to_body_presence(data, "2026-06-27")
    checklist = updated["entries"]["2026-06-27"]["Body & Presence"]["checklist"]
    assert checklist["Completed movement or exercise"]


def test_sync_fitness_sessions_to_entries(tmp_path):
    from progression.sessions import sync_fitness_sessions_to_entries

    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    wall = repo.get_exercise("cc1_push_01")
    create_workout_session(
        repo,
        "2026-07-06",
        [{"exercise_id": wall.id, "sets": 3, "reps": 20}],
    )
    entries: dict = {}
    assert sync_fitness_sessions_to_entries(entries, repo=repo) is True
    assert entries["2026-07-06"]["Body & Presence"]["checklist"]["Completed movement or exercise"]
    assert sync_fitness_sessions_to_entries(entries, repo=repo) is False


def test_fitness_ui_has_no_matplotlib_import():
    import ast

    with open("fitness_ui.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert "matplotlib" not in imports


def test_format_exercise_picker_label_includes_book_and_family():
    label = format_exercise_picker_label(
        {
            "name": "Wall Push-ups",
            "source_book": "CC1",
            "family": "push",
            "step": 1,
        }
    )
    assert label == "Wall Push-ups (CC1 · push · step 1)"


def test_format_exercise_picker_label_name_only():
    assert format_exercise_picker_label({"name": "Burpees"}) == "Burpees"


def test_format_pending_set_line_basic_and_extras():
    assert (
        format_pending_set_line({"label": "Wall Push-ups (CC1)", "sets": 3, "reps": 10})
        == "Wall Push-ups (CC1): 3x10"
    )
    assert (
        format_pending_set_line(
            {"name": "Plank", "sets": 1, "reps": 1, "hold_seconds": 30, "weight_kg": 5}
        )
        == "Plank: 1x1 (30s hold, 5 kg)"
    )


def test_remove_pending_set_at_mutates_and_guards():
    pending = [
        {"exercise_id": "a", "sets": 3, "reps": 10},
        {"exercise_id": "b", "sets": 2, "reps": 8},
        {"exercise_id": "c", "sets": 1, "reps": 5},
    ]
    assert remove_pending_set_at(pending, 1) is True
    assert [p["exercise_id"] for p in pending] == ["a", "c"]
    assert remove_pending_set_at(pending, 99) is False
    assert remove_pending_set_at(pending, -1) is False
    assert len(pending) == 2


def test_prefill_from_latest_session_empty_db(tmp_path):
    repo = make_repo(tmp_path)
    repo.initialize()
    items, source_id, notes = prefill_from_latest_session(repo, exclude_date="2026-10-17")
    assert items == []
    assert source_id is None
    assert notes == []


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


def test_prefill_uses_save_timestamp_and_excludes_today(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    wall = repo.get_exercise("cc1_push_01")
    assert wall is not None
    today = "2026-10-17"
    _insert_session_raw(repo, "sess-old-date", "2020-01-01", "2026-10-16T18:00:00+00:00")
    _insert_set_raw(repo, "sess-old-date", wall.id, sets=2, reps=8)
    _insert_session_raw(repo, "sess-today", today, "2026-10-15T10:00:00+00:00")
    _insert_set_raw(repo, "sess-today", wall.id, sets=5, reps=5)
    _insert_session_raw(repo, "sess-mid", "2025-06-01", "2026-10-14T10:00:00+00:00")
    _insert_set_raw(repo, "sess-mid", wall.id, sets=4, reps=4)

    items, source_id, _notes = prefill_from_latest_session(repo, exclude_date=today)
    assert source_id == "sess-old-date"
    assert len(items) == 1
    assert items[0]["sets"] == 2
    assert items[0]["reps"] == 8
    assert items[0]["prefilled"] is True


def test_copy_previous_pending_set_item_from_picker_when_exercise_differs():
    pending = [
        {
            "exercise_id": "a",
            "name": "A",
            "label": "A",
            "sets": 3,
            "reps": 12,
        }
    ]
    picker_row = {"id": "b", "name": "B", "source_book": "CC1", "family": "push", "step": 2}

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

    item = copy_previous_pending_set_item(
        pending,
        picker_row=picker_row,
        sets_var=_Var(2),
        reps_var=_Var(15),
        hold_var=_Var(0.0),
        set_weight_var=_Var(0.0),
        copy_previous=False,
    )
    assert item is not None
    assert item["exercise_id"] == "b"
    assert item["sets"] == 2
    assert item["reps"] == 15


def test_copy_previous_pending_set_item_uses_last_row():
    pending = [
        {
            "exercise_id": "a",
            "name": "A",
            "label": "A",
            "sets": 3,
            "reps": 12,
            "weight_kg": 20.0,
        }
    ]

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

    item = copy_previous_pending_set_item(
        pending,
        picker_row=None,
        sets_var=_Var(3),
        reps_var=_Var(10),
        hold_var=_Var(0.0),
        set_weight_var=_Var(0.0),
        copy_previous=True,
    )
    assert item is not None
    assert item["sets"] == 1
    assert item["reps"] == 12
    assert item["weight_kg"] == 20.0


def test_create_workout_session_rolls_back_on_record_performance_failure(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    wall = repo.get_exercise("cc1_push_01")
    incline = repo.get_exercise("cc1_push_02")
    assert wall is not None and incline is not None
    progress_before = repo.get_user_progress(wall.id)
    with pytest.raises(ValueError, match="earlier steps"):
        create_workout_session(
            repo,
            "2026-07-02",
            [
                {"exercise_id": wall.id, "sets": 1, "reps": 5},
                {"exercise_id": incline.id, "sets": 1, "reps": 5},
            ],
        )
    assert repo.list_workout_sessions(limit=10) == []
    progress_after = repo.get_user_progress(wall.id)
    assert (progress_before is None and progress_after is None) or (
        progress_before is not None
        and progress_after is not None
        and progress_before.best_reps == progress_after.best_reps
        and progress_before.status == progress_after.status
    )


def test_prefill_skips_deleted_only_session_for_earlier_rows(tmp_path):
    from progression.models import Exercise

    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    wall = repo.get_exercise("cc1_push_01")
    assert wall is not None
    removed_id = "removed_exercise_test"
    repo.add_exercise(
        Exercise(
            id=removed_id,
            name="Removed",
            source_book="CC1",
            family="push",
            mastery_criteria={"sets": 1, "reps": 1},
            metadata={},
        )
    )
    _insert_session_raw(repo, "sess-deleted-only", "2025-01-01", "2026-10-18T12:00:00+00:00")
    _insert_set_raw(repo, "sess-deleted-only", removed_id, sets=3, reps=10)
    with repo.connect() as conn:
        conn.execute(
            "UPDATE exercises SET deleted_at = datetime('now') WHERE id = ?",
            (removed_id,),
        )
        conn.commit()
    _insert_session_raw(repo, "sess-good", "2025-02-01", "2026-10-17T12:00:00+00:00")
    _insert_set_raw(repo, "sess-good", wall.id, sets=2, reps=6)

    items, source_id, notes = prefill_from_latest_session(repo, exclude_date="2026-10-17")
    assert source_id == "sess-good"
    assert len(items) == 1
    assert items[0]["reps"] == 6
    assert any("Skipped removed exercise" in n for n in notes)


def test_create_workout_session_rolls_back_on_set_failure(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    wall = repo.get_exercise("cc1_push_01")
    assert wall is not None
    with pytest.raises(sqlite3.IntegrityError):
        create_workout_session(
            repo,
            "2026-07-01",
            [
                {"exercise_id": wall.id, "sets": 1, "reps": 5},
                {"exercise_id": "not_a_real_exercise", "sets": 1, "reps": 5},
            ],
        )
    assert repo.list_workout_sessions(limit=10) == []


def test_count_workout_sessions_by_date_aggregates(tmp_path):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    repo.initialize()
    with repo.connect() as conn:
        for session_id, day in (("a", "2026-07-01"), ("b", "2026-07-01"), ("c", "2026-07-02")):
            conn.execute(
                """
                INSERT INTO workout_sessions (id, date, notes, duration_minutes, body_weight_kg)
                VALUES (?, ?, '', NULL, NULL)
                """,
                (session_id, day),
            )
    counts = repo.count_workout_sessions_by_date(limit=2000)
    assert counts["2026-07-01"] == 2
    assert counts["2026-07-02"] == 1
