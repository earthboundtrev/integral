from progression.db import FitnessRepository
from progression.models import Exercise
from progression.sessions import create_workout_session


def make_repo(tmp_path):
    repo = FitnessRepository(str(tmp_path / "fitness.db"))
    repo.initialize()
    return repo


def add_exercise(repo, name):
    return repo.add_exercise(
        Exercise(
            name=name,
            source_book="CC1",
            family="push",
            mastery_criteria={"sets": 3, "reps": 5},
        )
    )


def test_session_save_applies_minimum_form_gate(tmp_path):
    repo = make_repo(tmp_path)
    squat = add_exercise(repo, "Back Squat")

    create_workout_session(
        repo,
        "2026-06-27",
        [{"exercise_id": squat.id, "sets": 3, "reps": 5, "weight_kg": 100, "form_quality": 3}],
    )

    assert repo.get_user_progress(squat.id).status != "mastered"


def test_session_save_masters_when_form_meets_minimum(tmp_path):
    repo = make_repo(tmp_path)
    squat = add_exercise(repo, "Back Squat")

    create_workout_session(
        repo,
        "2026-06-27",
        [{"exercise_id": squat.id, "sets": 3, "reps": 5, "weight_kg": 100, "form_quality": 8}],
    )

    assert repo.get_user_progress(squat.id).status == "mastered"
