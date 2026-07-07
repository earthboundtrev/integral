"""Tests for sequential vs parallel step progression in fitness seeds."""

from fitness_programs import ensure_entry_points_available
from progression.db import FitnessRepository
from progression.engine import exercise_log_allowed, record_performance
from progression.models import UserExerciseProgress
from progression.seed_loader import seed_all_fitness


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def test_cc1_second_step_locked_until_first_mastered(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    assert not exercise_log_allowed(repo, "cc1_push_02")
    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50}, session_id="session-1")
    assert repo.get_user_progress("cc1_push_01").status in {"available", "in_progress"}
    assert not exercise_log_allowed(repo, "cc1_push_02")
    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50}, session_id="session-2")
    assert repo.get_user_progress("cc1_push_01").status == "mastered"
    assert repo.get_user_progress("cc1_push_02").status == "available"


def test_starting_strength_lifts_all_available(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    for lift_id in (
        "ss_back_squat",
        "ss_bench_press",
        "ss_deadlift",
        "ss_overhead_press",
        "ss_power_clean",
    ):
        progress = repo.get_user_progress(lift_id)
        assert progress is not None, lift_id
        assert progress.status == "available", lift_id
        assert exercise_log_allowed(repo, lift_id), lift_id


def test_tibetan_rites_all_available(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    for rite_id in (
        "ftr_rite_1",
        "ftr_rite_2",
        "ftr_rite_3",
        "ftr_rite_4",
        "ftr_rite_5",
    ):
        assert repo.get_user_progress(rite_id).status == "available"


def test_parallel_seed_removes_internal_prerequisite_edges(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)

    internal = [
        edge
        for edge in repo.list_edges("prerequisite")
        if edge.from_exercise_id.startswith("ss_") and edge.to_exercise_id.startswith("ss_")
    ]
    assert internal == []


def test_locked_exercise_rejects_performance_log(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)
    repo.upsert_user_progress(UserExerciseProgress(exercise_id="cc1_push_02", status="locked"))

    try:
        record_performance(repo, "cc1_push_02", {"sets": 3, "reps": 40})
        raised = False
    except ValueError:
        raised = True
    assert raised
