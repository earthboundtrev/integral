"""SPEC-210: full CC2 Hub ladders in the progression DAG."""

from progression.db import FitnessRepository
from progression.seed_loader import load_seed_file, seed_all_fitness, seed_from_file


def make_repo(tmp_path):
    repo = FitnessRepository(str(tmp_path / "fitness.db"))
    repo.initialize()
    return repo


EXPECTED_CC2_FILES = {
    "cc2_hang.json": ("hang", 8, "Horizontal Hang", "One-Arm Towel Hang"),
    "cc2_calf.json": ("calf", 6, "Double-Leg Calf Raise", "Single-Leg Donkey Calf Raise"),
    "cc2_fingertip_pushup.json": ("fingertip_pushup", 10, None, None),
    "cc2_clutch_flag.json": ("clutch_flag", 8, None, None),
    "cc2_press_flag.json": ("press_flag", 8, None, None),
    "cc2_neck_bridge.json": ("neck_bridge", 6, None, None),
    "cc2_trifecta_bridge.json": ("trifecta_bridge", 8, None, None),
    "cc2_trifecta_l_hold.json": ("trifecta_l_hold", 6, None, None),
    "cc2_trifecta_twist.json": ("trifecta_twist", 6, None, None),
}


def test_cc2_seed_files_match_hub_ladders():
    for filename, (family, count, first, last) in EXPECTED_CC2_FILES.items():
        payload = load_seed_file(filename)
        assert payload["source_book"] == "CC2"
        assert payload["family"] == family
        assert payload["step_progression"] == "sequential"
        assert payload["source"] == "programs/convict-conditioning-2.json"
        assert len(payload["exercises"]) == count
        assert len(payload["edges"]) == count - 1
        if first:
            assert payload["exercises"][0]["name"] == first
        if last:
            assert payload["exercises"][-1]["name"] == last


def test_cc2_hang_mastery_uses_hub_hold_standards():
    hang = load_seed_file("cc2_hang.json")
    assert hang["exercises"][0]["mastery_criteria"] == {"sets": 3, "hold_seconds": 30}
    assert hang["exercises"][0]["key"] == "cc2_hang_01"


def test_cc2_calf_mastery_uses_hub_rep_standards():
    calf = load_seed_file("cc2_calf.json")
    assert calf["exercises"][0]["key"] == "cc2_calf_01"
    assert calf["exercises"][0]["mastery_criteria"] == {"sets": 3, "reps": 50}


def test_seed_cc2_hang_loads_sequential_chain(tmp_path):
    repo = make_repo(tmp_path)
    key_map = seed_from_file(repo, "cc2_hang.json")
    assert len(repo.list_exercises()) == 8
    assert len(repo.list_edges("prerequisite")) == 7
    assert "cc2_hang_01" in key_map
    assert "cc2_hang_08" in key_map


def test_seed_all_fitness_includes_full_cc2(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    exercises = repo.list_exercises()
    assert len(exercises) == 152
    by_family = {}
    for ex in exercises:
        if ex.source_book == "CC2":
            by_family.setdefault(ex.family, []).append(ex)
    assert set(by_family) == {
        "hang",
        "fingertip_pushup",
        "clutch_flag",
        "press_flag",
        "neck_bridge",
        "calf",
        "trifecta_bridge",
        "trifecta_l_hold",
        "trifecta_twist",
    }
    assert len(by_family["hang"]) == 8
    assert len(by_family["calf"]) == 6
    names = {ex.name for ex in by_family["hang"]}
    assert "Horizontal Hang" in names
    assert "One-Arm Towel Hang" in names
    calf_names = {ex.name for ex in by_family["calf"]}
    assert "Double-Leg Calf Raise" in calf_names
    assert "Single-Leg Donkey Calf Raise" in calf_names
