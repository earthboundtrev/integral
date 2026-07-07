from datetime import datetime
from typing import Any

from progression.advancement import persist_performance_for_session, ready_to_master_step
from progression.db import FitnessRepository
from progression.fitness_settings import get_fitness_settings, progression_locks_enabled
from progression.mastery import meets_mastery
from progression.models import UserExerciseProgress

PROTECTED_STATUSES = {"in_progress", "mastered"}


def _fitness_settings(repo: FitnessRepository, fitness_settings: dict | None) -> dict:
    if fitness_settings is not None:
        return get_fitness_settings({"fitness": fitness_settings})
    if getattr(repo, "fitness_settings", None):
        return get_fitness_settings({"fitness": repo.fitness_settings})
    return get_fitness_settings({})


def exercise_log_allowed(
    repo: FitnessRepository,
    exercise_id: str,
    *,
    fitness_settings: dict | None = None,
) -> bool:
    """Block logging locked or not-yet-unlocked sequential steps."""
    settings = _fitness_settings(repo, fitness_settings)
    if not progression_locks_enabled(settings):
        return True

    progress = repo.get_user_progress(exercise_id)
    if progress is not None and progress.status == "locked":
        return False

    for edge in repo.list_incoming_edges(exercise_id):
        if edge.edge_type != "prerequisite":
            continue
        if not unlock_condition_satisfied(repo, edge.unlock_condition, edge.from_exercise_id):
            return False
    return True


def record_performance(
    repo: FitnessRepository,
    exercise_id: str,
    performance: dict[str, Any],
    logged_at: str | None = None,
    *,
    fitness_settings: dict | None = None,
    session_id: str | None = None,
) -> UserExerciseProgress:
    exercise = repo.get_exercise(exercise_id)
    if exercise is None:
        raise ValueError(f"Unknown exercise: {exercise_id}")

    settings = _fitness_settings(repo, fitness_settings)
    if not exercise_log_allowed(repo, exercise_id, fitness_settings=settings):
        raise ValueError("Complete earlier steps before logging this exercise.")

    if session_id:
        persist_performance_for_session(
            repo,
            exercise_id,
            performance,
            session_id,
            fitness_settings=settings,
        )

    existing = repo.get_user_progress(exercise_id)
    timestamp = logged_at or datetime.now().isoformat(timespec="seconds")

    if ready_to_master_step(
        repo,
        exercise,
        performance,
        fitness_settings=settings,
        session_id=session_id,
    ):
        progress = UserExerciseProgress(
            exercise_id=exercise_id,
            status="mastered",
            current_step=performance.get("current_step")
            if performance.get("current_step") is not None
            else (existing.current_step if existing else None),
            best_reps=_max_or_existing(performance.get("reps"), existing.best_reps if existing else None),
            best_hold_time=_max_or_existing(
                performance.get("hold_seconds"),
                existing.best_hold_time if existing else None,
            ),
            best_weight=_max_or_existing(
                performance.get("weight_kg"),
                existing.best_weight if existing else None,
            ),
            last_logged_at=timestamp,
            achieved_at=(existing.achieved_at if existing and existing.achieved_at else timestamp),
        )
        repo.upsert_user_progress(progress)
        unlock_available_targets(repo, progress.exercise_id)
        return progress

    progress = UserExerciseProgress(
        exercise_id=exercise_id,
        status=(
            "in_progress"
            if meets_mastery(exercise.mastery_criteria, performance)
            else (existing.status if existing else "in_progress")
        ),
        current_step=performance.get("current_step")
        if performance.get("current_step") is not None
        else (existing.current_step if existing else None),
        best_reps=_max_or_existing(performance.get("reps"), existing.best_reps if existing else None),
        best_hold_time=_max_or_existing(
            performance.get("hold_seconds"),
            existing.best_hold_time if existing else None,
        ),
        best_weight=_max_or_existing(
            performance.get("weight_kg"),
            existing.best_weight if existing else None,
        ),
        last_logged_at=timestamp,
        achieved_at=existing.achieved_at if existing else None,
    )
    repo.upsert_user_progress(progress)
    unlock_available_targets(repo, progress.exercise_id)
    return progress


def unlock_available_targets(repo: FitnessRepository, exercise_id: str) -> list[str]:
    unlocked: list[str] = []
    for edge in repo.list_outgoing_edges(exercise_id):
        if not unlock_condition_satisfied(repo, edge.unlock_condition, edge.from_exercise_id):
            continue

        existing_target = repo.get_user_progress(edge.to_exercise_id)
        if existing_target and existing_target.status in PROTECTED_STATUSES:
            continue

        repo.upsert_user_progress(
            UserExerciseProgress(
                exercise_id=edge.to_exercise_id,
                status="available",
                current_step=existing_target.current_step if existing_target else None,
                best_reps=existing_target.best_reps if existing_target else None,
                best_hold_time=existing_target.best_hold_time if existing_target else None,
                best_weight=existing_target.best_weight if existing_target else None,
                last_logged_at=existing_target.last_logged_at if existing_target else None,
                achieved_at=existing_target.achieved_at if existing_target else None,
            )
        )
        unlocked.append(edge.to_exercise_id)
    return unlocked


def unlock_condition_satisfied(
    repo: FitnessRepository,
    unlock_condition: dict[str, Any],
    from_exercise_id: str,
) -> bool:
    if "requires_any" in unlock_condition:
        return any(
            (progress := repo.get_user_progress(exercise_id)) is not None
            and progress.status == "mastered"
            for exercise_id in unlock_condition["requires_any"]
        )

    required_status = unlock_condition.get("requires")
    if required_status is None:
        return True

    progress = repo.get_user_progress(from_exercise_id)
    if progress is None:
        return False

    if required_status == "mastered":
        return progress.status == "mastered"

    if required_status == "in_progress":
        if progress.status not in {"in_progress", "mastered"}:
            return False
        min_step = unlock_condition.get("min_step")
        if min_step is None:
            return True
        return progress.current_step is not None and progress.current_step >= min_step

    return progress.status == required_status


def _max_or_existing(new_value: Any, existing_value: Any) -> Any:
    if not isinstance(new_value, int | float):
        return existing_value
    if not isinstance(existing_value, int | float):
        return new_value
    return max(new_value, existing_value)
