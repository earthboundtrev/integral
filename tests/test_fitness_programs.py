from fitness_programs import (
    build_program_groups,
    ensure_entry_points_available,
    format_program_summary,
    pick_current_step,
)
from fitness_ui import list_exercise_rows
from progression.db import FitnessRepository
from progression.seed_loader import seed_all_fitness


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def test_build_program_groups_all_steps_per_series(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    rows = list_exercise_rows(repo, source_book="CC1", family="push")
    programs = build_program_groups(rows)
    assert len(programs) == 1
    assert len(programs[0]["steps"]) == 10


def test_pick_current_step_prefers_in_progress():
    steps = [
        {"id": "a", "step": 1, "name": "A", "status": "mastered"},
        {"id": "b", "step": 2, "name": "B", "status": "in_progress"},
        {"id": "c", "step": 3, "name": "C", "status": "locked"},
    ]
    assert pick_current_step(steps)["id"] == "b"


def test_pick_current_step_uses_available_when_no_progress():
    steps = [
        {"id": "a", "step": 1, "name": "A", "status": "mastered"},
        {"id": "b", "step": 2, "name": "B", "status": "available"},
        {"id": "c", "step": 3, "name": "C", "status": "locked"},
    ]
    assert pick_current_step(steps)["id"] == "b"


def test_program_summary_mentions_current_step(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    rows = list_exercise_rows(repo, source_book="CC1", family="push")
    summary = format_program_summary(rows)
    assert "Step" in summary
    assert "Wall Push-ups" in summary


def test_entry_points_become_available(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    unlocked = ensure_entry_points_available(repo)
    assert "cc1_push_01" in unlocked
    assert repo.get_user_progress("cc1_push_01").status == "available"
