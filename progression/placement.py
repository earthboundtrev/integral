"""Manual starting placement for experienced athletes."""

from __future__ import annotations

from datetime import datetime

from progression.engine import unlock_available_targets
from progression.models import UserExerciseProgress
from progression.seed_loader import STEP_PROGRESSION_SEQUENTIAL


def program_key(source_book: str, family: str) -> str:
    return f"{source_book}:{family}"


def parse_program_key(key: str) -> tuple[str, str]:
    book, family = key.split(":", 1)
    return book, family


def list_program_steps(repo, source_book: str, family: str) -> list:
    steps = [
        exercise
        for exercise in repo.list_exercises()
        if exercise.source_book == source_book and exercise.family == family
    ]
    steps.sort(key=lambda exercise: (exercise.metadata.get("step") or 999, exercise.name))
    return steps


def apply_program_placement(
    repo,
    source_book: str,
    family: str,
    target_step: int,
    *,
    timestamp: str | None = None,
) -> list[str]:
    """Mark earlier steps mastered, target available, later steps locked."""
    timestamp = timestamp or datetime.now().isoformat(timespec="seconds")
    updated: list[str] = []
    last_unlocked_id: str | None = None

    for exercise in list_program_steps(repo, source_book, family):
        step_num = exercise.metadata.get("step")
        if step_num is None:
            continue
        if step_num < target_step:
            repo.upsert_user_progress(
                UserExerciseProgress(
                    exercise_id=exercise.id,
                    status="mastered",
                    current_step=step_num,
                    achieved_at=timestamp,
                    last_logged_at=timestamp,
                )
            )
            last_unlocked_id = exercise.id
            updated.append(exercise.id)
        elif step_num == target_step:
            repo.upsert_user_progress(
                UserExerciseProgress(
                    exercise_id=exercise.id,
                    status="available",
                    current_step=step_num,
                )
            )
            updated.append(exercise.id)
        else:
            repo.upsert_user_progress(
                UserExerciseProgress(exercise_id=exercise.id, status="locked")
            )
            updated.append(exercise.id)

    if last_unlocked_id:
        unlock_available_targets(repo, last_unlocked_id)
    return updated


def apply_stored_placements(repo, fitness_settings: dict | None) -> None:
    placements = (fitness_settings or {}).get("placements") or {}
    if not isinstance(placements, dict):
        return
    for key, step in placements.items():
        try:
            target_step = int(step)
        except (TypeError, ValueError):
            continue
        if target_step < 1:
            continue
        source_book, family = parse_program_key(str(key))
        apply_program_placement(repo, source_book, family, target_step)


def is_sequential_program(repo, source_book: str, family: str) -> bool:
    for exercise in list_program_steps(repo, source_book, family):
        if exercise.metadata.get("step_progression") == STEP_PROGRESSION_SEQUENTIAL:
            return True
    return False
