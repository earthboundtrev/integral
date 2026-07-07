"""When sequential steps unlock after meeting progression standards."""

from __future__ import annotations

from typing import Any

from progression.fitness_settings import get_fitness_settings, is_sequential_exercise
from progression.mastery import meets_mastery
from progression.seed_loader import STEP_PROGRESSION_SEQUENTIAL


def advance_sessions_required(exercise, fitness_settings: dict | None) -> int:
    settings = get_fitness_settings(fitness_settings)
    if not is_sequential_exercise(exercise):
        return 1
    try:
        return max(1, int(settings.get("cc_sessions_for_advance", 2)))
    except (TypeError, ValueError):
        return 2


def min_form_quality(fitness_settings: dict | None) -> int:
    settings = get_fitness_settings(fitness_settings)
    try:
        return max(1, int(settings.get("cc_min_form_quality", 7)))
    except (TypeError, ValueError):
        return 7


def form_quality_ok(performance: dict[str, Any], fitness_settings: dict | None) -> bool:
    quality = performance.get("form_quality")
    if quality is None:
        return True
    try:
        return int(quality) >= min_form_quality(fitness_settings)
    except (TypeError, ValueError):
        return False


def performance_from_workout_set(workout_set) -> dict[str, Any]:
    performance: dict[str, Any] = {}
    if workout_set.sets is not None:
        performance["sets"] = workout_set.sets
    if workout_set.reps is not None:
        performance["reps"] = workout_set.reps
    if workout_set.hold_seconds is not None:
        performance["hold_seconds"] = workout_set.hold_seconds
    if workout_set.weight_kg is not None:
        performance["weight_kg"] = workout_set.weight_kg
    if workout_set.form_quality is not None:
        performance["form_quality"] = workout_set.form_quality
    return performance


def count_qualifying_sessions(
    repo,
    exercise_id: str,
    criteria: dict[str, Any],
    *,
    fitness_settings: dict | None = None,
) -> int:
    qualifying: set[str] = set()
    for session in repo.list_workout_sessions(limit=2000):
        for workout_set in repo.list_workout_sets(session.id):
            if workout_set.exercise_id != exercise_id:
                continue
            perf = performance_from_workout_set(workout_set)
            if not meets_mastery(criteria, perf):
                continue
            if not form_quality_ok(perf, fitness_settings):
                continue
            qualifying.add(session.id)
    return len(qualifying)


def persist_performance_for_session(
    repo,
    exercise_id: str,
    performance: dict[str, Any],
    session_id: str,
    *,
    fitness_settings: dict | None = None,
) -> None:
    """Ensure direct record_performance calls contribute to session-based unlock counts."""
    from datetime import datetime

    from progression.models import WorkoutSession, WorkoutSet

    if not form_quality_ok(performance, fitness_settings):
        return
    if not meets_mastery(
        repo.get_exercise(exercise_id).mastery_criteria if repo.get_exercise(exercise_id) else {},
        performance,
    ):
        return

    if repo.has_workout_set(session_id, exercise_id):
        return
    if not repo.workout_session_exists(session_id):
        repo.add_workout_session(
            WorkoutSession(id=session_id, date=datetime.now().strftime("%Y-%m-%d"))
        )
    repo.add_workout_set(
        WorkoutSet(
            session_id=session_id,
            exercise_id=exercise_id,
            sets=performance.get("sets"),
            reps=performance.get("reps"),
            hold_seconds=performance.get("hold_seconds"),
            weight_kg=performance.get("weight_kg"),
            form_quality=performance.get("form_quality"),
        )
    )


def advancement_progress(
    repo,
    exercise,
    *,
    fitness_settings: dict | None = None,
) -> tuple[int, int]:
    """Return (qualifying_sessions, sessions_required) for sequential programs."""
    required = advance_sessions_required(exercise, fitness_settings)
    if exercise.metadata.get("step_progression") != STEP_PROGRESSION_SEQUENTIAL:
        return (0, required)
    count = count_qualifying_sessions(
        repo,
        exercise.id,
        exercise.mastery_criteria,
        fitness_settings=fitness_settings,
    )
    return (count, required)


def ready_to_master_step(
    repo,
    exercise,
    performance: dict[str, Any],
    *,
    fitness_settings: dict | None = None,
    session_id: str | None = None,
) -> bool:
    if not meets_mastery(exercise.mastery_criteria, performance):
        return False
    if not form_quality_ok(performance, fitness_settings):
        return False
    required = advance_sessions_required(exercise, fitness_settings)
    if required <= 1:
        return True
    count = count_qualifying_sessions(
        repo,
        exercise.id,
        exercise.mastery_criteria,
        fitness_settings=fitness_settings,
    )
    return count >= required


def format_advancement_hint(
    repo,
    exercise,
    *,
    fitness_settings: dict | None = None,
) -> str:
    if exercise.metadata.get("step_progression") != STEP_PROGRESSION_SEQUENTIAL:
        return ""
    count, required = advancement_progress(repo, exercise, fitness_settings=fitness_settings)
    if required <= 1:
        criteria = ", ".join(f"{key}={value}" for key, value in exercise.mastery_criteria.items())
        return f"Hit progression standard in one session to unlock the next step ({criteria})."
    if count >= required:
        return "Progression standard met — this step should unlock the next level on save."
    remaining = required - count
    return (
        f"{count}/{required} sessions at progression standard. "
        f"{remaining} more qualifying session(s) unlock the next step."
    )
