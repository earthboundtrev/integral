import ast
import sqlite3

import pytest

from progression.db import FitnessRepository
from progression.models import Exercise, ProgressionEdge, UserExerciseProgress
from progression.validate import ProgressionCycleError


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
            metadata={"difficulty": "test"},
        )
    )


def test_initialize_creates_schema_with_json_text(tmp_path):
    repo = make_repo(tmp_path)
    exercise = add_exercise(repo, "Wall Push-up")
    loaded = repo.get_exercise(exercise.id)

    assert loaded is not None
    assert loaded.mastery_criteria == {"sets": 3, "reps": 5}
    assert loaded.metadata == {"difficulty": "test"}

    with sqlite3.connect(repo.db_path) as conn:
        row = conn.execute(
            "SELECT mastery_criteria FROM exercises WHERE id = ?",
            (exercise.id,),
        ).fetchone()
    assert isinstance(row[0], str)


def test_adds_prerequisite_edge(tmp_path):
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

    edges = repo.list_edges("prerequisite")
    assert len(edges) == 1
    assert edges[0].unlock_condition == {"requires": "mastered"}


def test_rejects_direct_cycle(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")

    with pytest.raises(ProgressionCycleError):
        repo.add_edge(
            ProgressionEdge(
                from_exercise_id=wall.id,
                to_exercise_id=wall.id,
                unlock_condition={"requires": "mastered"},
            )
        )


def test_rejects_indirect_cycle(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")
    incline = add_exercise(repo, "Incline Push-up")
    knee = add_exercise(repo, "Knee Push-up")

    repo.add_edge(
        ProgressionEdge(
            from_exercise_id=wall.id,
            to_exercise_id=incline.id,
            unlock_condition={"requires": "mastered"},
        )
    )
    repo.add_edge(
        ProgressionEdge(
            from_exercise_id=incline.id,
            to_exercise_id=knee.id,
            unlock_condition={"requires": "mastered"},
        )
    )

    with pytest.raises(ProgressionCycleError):
        repo.add_edge(
            ProgressionEdge(
                from_exercise_id=knee.id,
                to_exercise_id=wall.id,
                unlock_condition={"requires": "mastered"},
            )
        )


def test_recommended_edges_do_not_participate_in_dag_validation(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")
    clap = add_exercise(repo, "Clap Push-up")

    edge = repo.add_edge(
        ProgressionEdge(
            from_exercise_id=wall.id,
            to_exercise_id=clap.id,
            edge_type="recommended",
            unlock_condition={"requires": "in_progress"},
        )
    )

    assert edge in repo.list_edges("recommended")


def test_user_progress_upsert(tmp_path):
    repo = make_repo(tmp_path)
    wall = add_exercise(repo, "Wall Push-up")

    repo.upsert_user_progress(
        UserExerciseProgress(
            exercise_id=wall.id,
            status="in_progress",
            current_step=1,
            best_reps=20,
        )
    )
    repo.upsert_user_progress(
        UserExerciseProgress(
            exercise_id=wall.id,
            status="mastered",
            current_step=1,
            best_reps=50,
            achieved_at="2026-06-27T12:00:00",
        )
    )

    with sqlite3.connect(repo.db_path) as conn:
        row = conn.execute(
            "SELECT status, best_reps FROM user_exercise_progress WHERE exercise_id = ?",
            (wall.id,),
        ).fetchone()
    assert row == ("mastered", 50)


def test_progression_package_has_no_tkinter_imports():
    for path in [
        "progression/__init__.py",
        "progression/models.py",
        "progression/db.py",
        "progression/validate.py",
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
