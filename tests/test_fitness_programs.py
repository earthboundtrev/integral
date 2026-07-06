from fitness_programs import (
    build_program_groups,
    build_program_hierarchy,
    ensure_entry_points_available,
    filter_program_hierarchy,
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


def test_build_program_hierarchy_nests_by_book(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    rows = list_exercise_rows(repo)
    hierarchy = build_program_hierarchy(rows)
    books = {book["title"] for book in hierarchy}
    assert "CC1" in books
    assert "SS" in books
    cc1 = next(book for book in hierarchy if book["title"] == "CC1")
    assert len(cc1["programs"]) >= 5
    assert cc1["programs"][0]["title"] in {"Push", "Pull", "Squat", "Leg Raises", "Bridge", "Handstand Push-up"}
    assert cc1["expanded"] is False
    assert cc1["programs"][0]["expanded"] is False


def test_filter_program_hierarchy_expands_matching_book():
    hierarchy = [
        {
            "id": "book:CC1",
            "title": "CC1",
            "subtitle": "Convict Conditioning 1",
            "summary": "6 programs",
            "expanded": False,
            "programs": [
                {
                    "id": "CC1:pull",
                    "title": "Pull",
                    "summary": "Step 1",
                    "expanded": False,
                    "current_step_id": "a",
                    "steps": [
                        {
                            "id": "a",
                            "name": "Vertical Pull",
                            "source_book": "CC1",
                            "family": "pull",
                            "step": 1,
                            "status": "available",
                            "criteria": {},
                        }
                    ],
                }
            ],
        }
    ]
    result = filter_program_hierarchy(hierarchy, "CC1")
    assert len(result) == 1
    assert result[0]["expanded"] is True
    assert result[0]["programs"][0]["expanded"] is True
