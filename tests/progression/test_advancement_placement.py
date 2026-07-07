from fitness_programs import ensure_entry_points_available
from progression.db import FitnessRepository
from progression.engine import exercise_log_allowed, record_performance
from progression.placement import apply_program_placement, program_key
from progression.seed_loader import seed_all_fitness


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def test_cc_requires_two_qualifying_sessions_before_unlock(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50, "form_quality": 8}, session_id="s1")
    assert repo.get_user_progress("cc1_push_01").status in {"available", "in_progress"}
    assert not exercise_log_allowed(repo, "cc1_push_02")

    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50, "form_quality": 8}, session_id="s2")
    assert repo.get_user_progress("cc1_push_01").status == "mastered"
    assert repo.get_user_progress("cc1_push_02").status == "available"


def test_low_form_quality_does_not_count_toward_unlock(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50, "form_quality": 5}, session_id="s1")
    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50, "form_quality": 5}, session_id="s2")
    assert repo.get_user_progress("cc1_push_01").status in {"available", "in_progress"}


def test_manual_placement_sets_ladder_position(tmp_path):
    repo = make_repo(tmp_path)
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    apply_program_placement(repo, "CC1", "push", 5)

    assert repo.get_user_progress("cc1_push_04").status == "mastered"
    assert repo.get_user_progress("cc1_push_05").status == "available"
    assert repo.get_user_progress("cc1_push_06").status == "locked"
    assert exercise_log_allowed(repo, "cc1_push_05")
    assert not exercise_log_allowed(repo, "cc1_push_06")


def test_disable_progression_locks_allows_any_step(tmp_path):
    repo = make_repo(tmp_path)
    repo.fitness_settings = {"disable_progression_locks": True}
    seed_all_fitness(repo)
    ensure_entry_points_available(repo)

    assert exercise_log_allowed(repo, "cc1_push_08", fitness_settings=repo.fitness_settings)
    record_performance(
        repo,
        "cc1_push_08",
        {"sets": 2, "reps": 20},
        fitness_settings=repo.fitness_settings,
    )
    assert repo.get_user_progress("cc1_push_08").status in {"in_progress", "mastered"}


def test_placement_key_round_trip():
    assert program_key("CC1", "pull") == "CC1:pull"
