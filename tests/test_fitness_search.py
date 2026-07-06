import pytest

from fitness_programs import (
    build_program_groups,
    build_program_hierarchy,
    filter_program_groups,
    filter_program_hierarchy,
    filter_rows_by_search,
)
from fitness_ui import list_exercise_rows
from progression.db import FitnessRepository
from progression.seed_loader import seed_all_fitness


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def sample_programs():
    return [
        {
            "id": "CC1:push",
            "title": "CC1 · Push",
            "summary": "Step 1 of 10",
            "current_step_id": "a",
            "expanded": False,
            "steps": [
                {"id": "a", "name": "Wall Push-ups", "source_book": "CC1", "family": "push", "step": 1, "status": "available", "criteria": {"sets": 3, "reps": 50}},
                {"id": "b", "name": "Incline Push-ups", "source_book": "CC1", "family": "push", "step": 2, "status": "locked", "criteria": {"sets": 3, "reps": 40}},
            ],
        }
    ]


def test_filter_rows_by_search_matches_exercise_name():
    rows = sample_programs()[0]["steps"]
    result = filter_rows_by_search(rows, "incline")
    assert len(result) == 1
    assert result[0]["name"] == "Incline Push-ups"


def test_filter_program_groups_matches_program_title():
    programs = sample_programs()
    result = filter_program_groups(programs, "CC1")
    assert len(result) == 1
    assert len(result[0]["steps"]) == 2


def test_filter_program_groups_matches_step_only():
    programs = sample_programs()
    result = filter_program_groups(programs, "incline")
    assert len(result) == 1
    assert len(result[0]["steps"]) == 1
    assert result[0]["steps"][0]["name"] == "Incline Push-ups"


def test_filter_program_groups_empty_query_returns_all():
    programs = sample_programs()
    assert filter_program_groups(programs, "") == programs
    assert filter_program_groups(programs, "   ") == programs


def test_search_fitness_rows_integration(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    rows = list_exercise_rows(repo, source_book="CC2")
    hierarchy = build_program_hierarchy(rows)
    filtered = filter_program_hierarchy(hierarchy, "human flag")
    assert len(filtered) == 1
    steps = filtered[0]["programs"][0]["steps"]
    assert any("Human Flag" in step["name"] for step in steps)
