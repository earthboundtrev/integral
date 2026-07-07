"""Workout session helpers — pure logic, no UI."""

from datetime import datetime
from typing import Any

from progression.db import FitnessRepository
from progression.engine import record_performance
from progression.models import WorkoutSession, WorkoutSet


def create_workout_session(
    repo: FitnessRepository,
    date: str,
    sets_data: list[dict[str, Any]],
    notes: str = "",
    duration_minutes: int | None = None,
    body_weight_kg: float | None = None,
) -> WorkoutSession:
    session = WorkoutSession(
        date=date,
        notes=notes,
        duration_minutes=duration_minutes,
        body_weight_kg=body_weight_kg,
    )
    repo.add_workout_session(session)

    for item in sets_data:
        workout_set = WorkoutSet(
            session_id=session.id,
            exercise_id=item["exercise_id"],
            sets=item.get("sets"),
            reps=item.get("reps"),
            hold_seconds=item.get("hold_seconds"),
            weight_kg=item.get("weight_kg"),
            form_quality=item.get("form_quality"),
        )
        repo.add_workout_set(workout_set)

        performance = {}
        if workout_set.sets is not None:
            performance["sets"] = workout_set.sets
        if workout_set.reps is not None:
            performance["reps"] = workout_set.reps
        if workout_set.hold_seconds is not None:
            performance["hold_seconds"] = workout_set.hold_seconds
        if workout_set.weight_kg is not None:
            performance["weight_kg"] = workout_set.weight_kg
        if performance:
            record_performance(
                repo,
                workout_set.exercise_id,
                performance,
                session_id=session.id,
            )

    return session


def format_session_summary(repo: FitnessRepository, session: WorkoutSession) -> str:
    lines = [f"Date: {session.date}"]
    if session.duration_minutes:
        lines.append(f"Duration: {session.duration_minutes} min")
    if session.body_weight_kg:
        lines.append(f"Body weight: {session.body_weight_kg} kg")
    if session.notes:
        lines.append(f"Notes: {session.notes}")

    for workout_set in repo.list_workout_sets(session.id):
        exercise = repo.get_exercise(workout_set.exercise_id)
        name = exercise.name if exercise else workout_set.exercise_id
        parts = []
        if workout_set.sets is not None:
            parts.append(f"{workout_set.sets} sets")
        if workout_set.reps is not None:
            parts.append(f"{workout_set.reps} reps")
        if workout_set.hold_seconds is not None:
            parts.append(f"{workout_set.hold_seconds}s hold")
        if workout_set.weight_kg is not None:
            parts.append(f"{workout_set.weight_kg} kg")
        lines.append(f"  • {name}: {', '.join(parts) if parts else 'logged'}")
    return "\n".join(lines)


def link_session_to_body_presence(data: dict, session_date: str) -> dict:
    """Mark Body & Presence checklist when a workout is logged."""
    entries = data.setdefault("entries", {})
    day = entries.setdefault(session_date, {})
    body = day.setdefault("Body & Presence", {})
    checklist = body.setdefault("checklist", {})
    checklist["Completed movement/exercise"] = True
    return data
