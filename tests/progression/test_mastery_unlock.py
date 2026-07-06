import ast

from progression.db import FitnessRepository
from progression.engine import record_performance
from progression.mastery import meets_mastery
from progression.models import Exercise, ProgressionEdge, UserExerciseProgress


def make_repo(tmp_path):
    repo = FitnessRepository(str(tmp_path / "fitness.db"))
    repo.initialize()
    return repo


def add_exercise(repo, name, criteria=None):
    return repo.add_exercise(
        Exercise(
            name=name,
            source_book="CC1",
            family="push",
            mastery_criteria=criteria or {"sets": 3, "reps": 5},
        )
    )


def test_meets_mastery_when_all_numeric_thresholds_met():
    assert meets_mastery(
        {"sets": 3, "reps": 5, "weight_kg": 60},
        {"sets": 3, "reps": 6, "weight_kg": 62.5},
    )
    assert meets_mastery({"sets": 3, "hold_seconds": 10}, {"sets": 4, "hold_seconds": 12})
    assert meets_mastery({"sessions": 5, "min_rating": 8}, {"sessions": 5, "rating": 9})


def test_mastery_false_when_any_threshold_missed():
    assert not meets_mastery({"sets": 3, "reps": 5}, {"sets": 2, "reps": 8})
    assert not meets_mastery({"sets": 3, "hold_seconds": 10}, {"sets": 3, "hold_seconds": 9})
    assert not meets_mastery({"sessions": 5, "min_rating": 8}, {"sessions": 5, "rating": 7})


def test_record_performance_marks_mastered_and_sets_achieved_at(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")

    progress = record_performance(
        repo,
        wall.id,
        {"sets": 3, "reps": 5},
        logged_at="2026-06-27T12:00:00",
    )

    stored = repo.get_user_progress(wall.id)
    assert progress.status == "mastered"
    assert stored.status == "mastered"
    assert stored.achieved_at == "2026-06-27T12:00:00"
    assert stored.best_reps == 5


def test_mastered_edge_unlocks_target_as_available(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")
    incline = add_exercise(repo, "Incline Push-up")
    repo.add_edge(
        ProgressionEdge(
            from_exercise_id=wall.id,
            to_exercise_id=incline.id,
            unlock_condition={"requires": "mastered"},
        )
    )

    record_performance(repo, wall.id, {"sets": 3, "reps": 5})

    assert repo.get_user_progress(wall.id).status == "mastered"
    assert repo.get_user_progress(incline.id).status == "available"


def test_unlock_does_not_downgrade_in_progress_or_mastered_targets(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")
    incline = add_exercise(repo, "Incline Push-up")
    repo.add_edge(
        ProgressionEdge(
            from_exercise_id=wall.id,
            to_exercise_id=incline.id,
            unlock_condition={"requires": "mastered"},
        )
    )
    repo.upsert_user_progress(
        UserExerciseProgress(exercise_id=incline.id, status="in_progress", current_step=2)
    )

    record_performance(repo, wall.id, {"sets": 3, "reps": 5})

    target = repo.get_user_progress(incline.id)
    assert target.status == "in_progress"
    assert target.current_step == 2


def test_in_progress_min_step_unlocks_only_after_step_threshold(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up", {"sets": 3, "reps": 50})
    incline = add_exercise(repo, "Incline Push-up")
    repo.add_edge(
        ProgressionEdge(
            from_exercise_id=wall.id,
            to_exercise_id=incline.id,
            edge_type="recommended",
            unlock_condition={"requires": "in_progress", "min_step": 3},
        )
    )

    record_performance(repo, wall.id, {"sets": 2, "reps": 20, "current_step": 2})
    assert repo.get_user_progress(incline.id) is None

    record_performance(repo, wall.id, {"sets": 2, "reps": 25, "current_step": 3})
    assert repo.get_user_progress(incline.id).status == "available"


def test_requires_any_unlocks_when_any_listed_exercise_mastered(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")
    pull = repo.add_exercise(
        Exercise(
            name="Vertical Pull",
            source_book="CC1",
            family="pull",
            mastery_criteria={"sets": 3, "reps": 5},
        )
    )
    planche = repo.add_exercise(
        Exercise(
            name="Planche Lean",
            source_book="OG",
            family="push",
            mastery_criteria={"sets": 3, "hold_seconds": 10},
        )
    )
    repo.add_edge(
        ProgressionEdge(
            from_exercise_id=wall.id,
            to_exercise_id=planche.id,
            edge_type="recommended",
            unlock_condition={"requires_any": [wall.id, pull.id]},
        )
    )

    record_performance(repo, wall.id, {"sets": 3, "reps": 5})

    assert repo.get_user_progress(planche.id).status == "available"


def test_mastery_unlock_modules_have_no_tkinter_imports():
    for path in [
        "progression/mastery.py",
        "progression/engine.py",
    ]:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert "tkinter" not in imports
