from progression.db import FitnessRepository
from progression.seed_loader import load_seed_file, seed_all_fitness, seed_cc1_push


def make_repo(tmp_path):
    repo = FitnessRepository(str(tmp_path / "fitness.db"))
    repo.initialize()
    return repo


def test_cc1_seed_file_has_ten_push_steps():
    payload = load_seed_file("cc1_push.json")
    assert payload["source_book"] == "CC1"
    assert payload["family"] == "push"
    assert len(payload["exercises"]) == 10
    assert len(payload["edges"]) == 9


def test_seed_cc1_push_loads_exercises_and_edges(tmp_path):
    repo = make_repo(tmp_path)
    key_map = seed_cc1_push(repo)

    exercises = repo.list_exercises()
    assert len(exercises) == 10
    names = {ex.name for ex in exercises}
    assert "Wall Push-ups" in names
    assert "One-Arm Push-ups" in names
    assert len(repo.list_edges("prerequisite")) == 9
    assert "cc1_push_01" in key_map


def test_seed_all_fitness_loads_91_exercises(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    assert len(repo.list_exercises()) == 91
    assert len(repo.list_edges("recommended")) == 4


def test_cc1_seed_is_idempotent(tmp_path):
    repo = make_repo(tmp_path)
    seed_cc1_push(repo)
    seed_cc1_push(repo)
    assert len(repo.list_exercises()) == 10
    assert len(repo.list_edges("prerequisite")) == 9


def test_seed_all_is_idempotent(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    seed_all_fitness(repo)
    assert len(repo.list_exercises()) == 91


def test_mastering_wall_pushup_unlocks_incline(tmp_path):
    from progression.engine import record_performance

    repo = make_repo(tmp_path)
    key_map = seed_cc1_push(repo)

    wall_id = key_map["cc1_push_01"]
    incline_id = key_map["cc1_push_02"]

    record_performance(repo, wall_id, {"sets": 3, "reps": 50}, session_id="s1")
    record_performance(repo, wall_id, {"sets": 3, "reps": 50}, session_id="s2")

    assert repo.get_user_progress(wall_id).status == "mastered"
    assert repo.get_user_progress(incline_id).status == "available"
