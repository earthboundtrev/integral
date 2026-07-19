"""SPEC-211: Strong Medicine Hub ladders in the progression DAG."""

from progression.db import FitnessRepository
from progression.seed_loader import load_seed_file, seed_all_fitness, seed_from_file


def make_repo(tmp_path):
    repo = FitnessRepository(str(tmp_path / "fitness.db"))
    repo.initialize()
    return repo


EXPECTED_SM_FILES = {
    "sm_squat.json": ("squat", 7, "Assisted Squat — Shortened Rep Stroke", "Barbell Back Squat"),
    "sm_sumo_deadlift.json": (
        "sumo_deadlift",
        4,
        "Sumo Deadlift — technique (empty bar / light)",
        "Barbell Sumo Deadlift",
    ),
    "sm_db_bench.json": ("db_bench", 3, None, None),
    "sm_db_overhead_press.json": ("db_overhead_press", 3, None, None),
    "sm_statue_row.json": ("statue_row", 4, None, None),
    "sm_plank_core.json": ("plank_core", 4, "Basic Plank (forearms)", "Plank Row"),
}


def test_sm_seed_files_match_hub_ladders():
    for filename, (family, count, first, last) in EXPECTED_SM_FILES.items():
        payload = load_seed_file(filename)
        assert payload["source_book"] == "SM"
        assert payload["family"] == family
        assert payload["step_progression"] == "sequential"
        assert payload["source"] == "programs/strong-medicine.json"
        assert len(payload["exercises"]) == count
        assert len(payload["edges"]) == count - 1
        if first:
            assert payload["exercises"][0]["name"] == first
        if last:
            assert payload["exercises"][-1]["name"] == last


def test_sm_qualitative_progression_uses_hub_intermediate():
    squat = load_seed_file("sm_squat.json")
    step1 = squat["exercises"][0]
    assert step1["mastery_criteria"] == {"sets": 3, "reps": 10}
    assert step1["hub_progression_note"] == "parallel depth"


def test_sm_parseable_progression_uses_sets_reps():
    squat = load_seed_file("sm_squat.json")
    goblet = squat["exercises"][4]
    assert goblet["mastery_criteria"] == {"sets": 3, "reps": 10}


def test_sm_plank_uses_hold_seconds():
    plank = load_seed_file("sm_plank_core.json")
    assert plank["exercises"][0]["mastery_criteria"] == {"sets": 1, "hold_seconds": 60}


def test_seed_sm_squat_chain(tmp_path):
    repo = make_repo(tmp_path)
    key_map = seed_from_file(repo, "sm_squat.json")
    assert len(repo.list_exercises()) == 7
    assert len(repo.list_edges("prerequisite")) == 6
    assert "sm_squat_01" in key_map
    assert "sm_squat_07" in key_map


def test_seed_all_fitness_includes_strong_medicine(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    exercises = repo.list_exercises()
    assert len(exercises) == 177
    by_family = {}
    for ex in exercises:
        if ex.source_book == "SM":
            by_family.setdefault(ex.family, []).append(ex)
    assert set(by_family) == {
        "squat",
        "sumo_deadlift",
        "db_bench",
        "db_overhead_press",
        "statue_row",
        "plank_core",
    }
    assert len(by_family["squat"]) == 7
    assert len(by_family["sumo_deadlift"]) == 4
    names = {ex.name for ex in by_family["squat"]}
    assert "Barbell Back Squat" in names
    assert "Assisted Squat — Shortened Rep Stroke" in names
