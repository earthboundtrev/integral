import pytest

from fitness_ui import ensure_fitness_seeded, list_exercise_rows, submit_performance
from progression.db import FitnessRepository
from progression.seed_loader import seed_all_fitness
from progression.sessions import create_workout_session, link_session_to_body_presence


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def test_ensure_fitness_seeded_loads_all_books_when_empty(tmp_path):
    repo = make_repo(tmp_path)
    assert ensure_fitness_seeded(repo) is True
    assert len(repo.list_exercises()) == 91
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
    assert updated["entries"]["2026-06-27"]["Body & Presence"]["checklist"]["Completed movement/exercise"]


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
