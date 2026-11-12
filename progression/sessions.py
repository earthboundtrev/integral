"""Workout session helpers — pure logic, no UI."""

from __future__ import annotations

import copy
import os
import sqlite3
from datetime import datetime
from typing import Any

from progression.db import FitnessRepository
from progression.engine import record_performance
from progression.models import UserExerciseProgress, WorkoutSession, WorkoutSet

BODY_MOVEMENT_CHECKLIST = "Completed movement or exercise"
LEGACY_BODY_MOVEMENT_CHECKLIST = "Completed movement/exercise"


def find_latest_session_for_repeat(
    repo: FitnessRepository,
    *,
    exclude_date: str | None = None,
) -> WorkoutSession | None:
    """Latest session by save timestamp (``created_at``), optionally skipping a calendar date."""
    exclude = (exclude_date or "").strip()
    list_fn = getattr(repo, "list_workout_sessions_by_created_at", None)
    if callable(list_fn):
        sessions = list_fn(limit=5000)
    else:
        sessions = repo.list_workout_sessions(limit=5000)
    for session in sessions:
        if exclude and (session.date or "").strip() == exclude:
            continue
        return session
    return None


def _prefill_items_for_session(
    repo: FitnessRepository,
    session: WorkoutSession,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = repo.list_workout_sets(session.id)
    rows.sort(key=lambda s: (s.ordinal if s.ordinal is not None else 0, s.id))
    items: list[dict[str, Any]] = []
    skip_notes: list[str] = []
    for workout_set in rows:
        exercise = repo.get_exercise(workout_set.exercise_id)
        if exercise is None:
            skip_notes.append(f"Skipped removed exercise ({workout_set.exercise_id})")
            continue
        item: dict[str, Any] = {
            "exercise_id": exercise.id,
            "name": exercise.name,
            "label": exercise.name,
            "sets": workout_set.sets if workout_set.sets is not None else 1,
            "reps": workout_set.reps if workout_set.reps is not None else 0,
            "prefilled": True,
        }
        if workout_set.hold_seconds is not None and workout_set.hold_seconds > 0:
            item["hold_seconds"] = workout_set.hold_seconds
        if workout_set.weight_kg is not None and workout_set.weight_kg > 0:
            item["weight_kg"] = workout_set.weight_kg
        items.append(item)
    return items, skip_notes


def prefill_from_latest_session(
    repo: FitnessRepository,
    *,
    exclude_date: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    """
    Build queued-set dicts from the latest saved session (#114).

    Returns (items, source_session_id, skip_notes). Empty DB → ([], None, []).
    Skips exercises removed from the catalog (deleted). If the newest session
    only contains removed exercises, walks to an earlier session that still has rows.
    """
    exclude = (exclude_date or "").strip()
    list_fn = getattr(repo, "list_workout_sessions_by_created_at", None)
    if callable(list_fn):
        sessions = list_fn(limit=5000)
    else:
        sessions = repo.list_workout_sessions(limit=5000)
    skip_notes: list[str] = []
    for session in sessions:
        if exclude and (session.date or "").strip() == exclude:
            continue
        items, session_notes = _prefill_items_for_session(repo, session)
        skip_notes.extend(session_notes)
        if items:
            return items, session.id, skip_notes
    return [], None, skip_notes


def _insert_session_and_sets(
    repo: FitnessRepository,
    session: WorkoutSession,
    sets_data: list[dict[str, Any]],
) -> WorkoutSession:
    insert_fn = getattr(repo, "insert_workout_session_with_sets", None)
    if callable(insert_fn):
        return insert_fn(session, sets_data)
    repo.add_workout_session(session)
    for ordinal, item in enumerate(sets_data):
        workout_set = WorkoutSet(
            session_id=session.id,
            exercise_id=item["exercise_id"],
            sets=item.get("sets"),
            reps=item.get("reps"),
            hold_seconds=item.get("hold_seconds"),
            weight_kg=item.get("weight_kg"),
            form_quality=item.get("form_quality"),
            ordinal=ordinal,
        )
        repo.add_workout_set(workout_set)
    return session


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
    exercise_ids = list(dict.fromkeys(item["exercise_id"] for item in sets_data))
    progress_before = snapshot_exercise_progress_for_session(repo, exercise_ids)
    session_persisted = False
    try:
        session = _insert_session_and_sets(repo, session, sets_data)
        session_persisted = True
        for item in sets_data:
            performance = {}
            if item.get("sets") is not None:
                performance["sets"] = item["sets"]
            if item.get("reps") is not None:
                performance["reps"] = item["reps"]
            if item.get("hold_seconds") is not None:
                performance["hold_seconds"] = item["hold_seconds"]
            if item.get("weight_kg") is not None:
                performance["weight_kg"] = item["weight_kg"]
            if item.get("form_quality") is not None:
                performance["form_quality"] = item["form_quality"]
            if performance:
                record_performance(
                    repo,
                    item["exercise_id"],
                    performance,
                    session_id=session.id,
                )
    except Exception:
        if session_persisted and getattr(repo, "workout_session_exists", lambda _id: False)(
            session.id
        ):
            undo_workout_session_log(
                repo,
                session.id,
                exercise_ids=exercise_ids,
                progress_snapshots=progress_before,
            )
        raise

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
        if workout_set.form_quality is not None:
            parts.append(f"quality {workout_set.form_quality}/10")
        lines.append(f"  • {name}: {', '.join(parts) if parts else 'logged'}")
    return "\n".join(lines)


def bridge_fitness_to_daily_entries(entries: dict, session_date: str) -> None:
    """Connect a fitness session date to the daily Body & Presence life-area log."""
    day = entries.setdefault(session_date, {})
    body = day.setdefault(
        "Body & Presence",
        {"rating": 7, "checklist": {}, "metrics": {}, "notes": ""},
    )
    checklist = body.setdefault("checklist", {})
    checklist[BODY_MOVEMENT_CHECKLIST] = True
    checklist.pop(LEGACY_BODY_MOVEMENT_CHECKLIST, None)


def sync_fitness_sessions_to_entries(
    entries: dict,
    fitness_settings: dict | None = None,
    *,
    repo: FitnessRepository | None = None,
) -> bool:
    """Backfill daily entries from SQLite workout sessions (idempotent)."""
    repo = repo or FitnessRepository(fitness_settings=fitness_settings)
    repo.initialize()
    changed = False
    session_dates = {session.date for session in repo.list_workout_sessions(limit=5000)}
    for session_date in session_dates:
        before = entries.get(session_date, {}).get("Body & Presence", {}).get("checklist", {})
        bridge_fitness_to_daily_entries(entries, session_date)
        after = entries.get(session_date, {}).get("Body & Presence", {}).get("checklist", {})
        if before != after:
            changed = True
    return changed


def link_session_to_body_presence(data: dict, session_date: str) -> dict:
    """Mark Body & Presence checklist when a workout is logged."""
    entries = data.setdefault("entries", {})
    bridge_fitness_to_daily_entries(entries, session_date)
    return data


BODY_PRESENCE_CATEGORY = "Body & Presence"


def is_fitness_db_lock_error(error: BaseException) -> bool:
    if isinstance(error, PermissionError):
        return True
    if isinstance(error, sqlite3.OperationalError):
        text = str(error).lower()
        return "locked" in text or "readonly" in text or "unable to open" in text
    if isinstance(error, OSError):
        return error.errno in {13, 30}  # EACCES, EROFS
    return False


def fitness_db_file_label(repo: FitnessRepository) -> str:
    return os.path.basename(getattr(repo, "db_path", "fitness.db")) or "fitness.db"


def snapshot_body_presence_entry(entries: dict, session_date: str) -> dict | None:
    day = entries.get(session_date)
    if not day:
        return None
    body = day.get(BODY_PRESENCE_CATEGORY)
    if body is None:
        return None
    return copy.deepcopy(body)


def restore_body_presence_entry(
    entries: dict,
    session_date: str,
    snapshot: dict | None,
) -> None:
    if snapshot is None:
        day = entries.get(session_date)
        if not day:
            return
        day.pop(BODY_PRESENCE_CATEGORY, None)
        if not day:
            entries.pop(session_date, None)
        return
    day = entries.setdefault(session_date, {})
    day[BODY_PRESENCE_CATEGORY] = copy.deepcopy(snapshot)


def exercise_ids_affected_by_logging(
    repo: FitnessRepository,
    exercise_ids: list[str],
) -> list[str]:
    """Progress rows that logging may update, including unlock targets along outgoing edges."""
    seen: set[str] = set()
    queue = list(dict.fromkeys(exercise_ids))
    while queue:
        exercise_id = queue.pop(0)
        if exercise_id in seen:
            continue
        seen.add(exercise_id)
        for edge in repo.list_outgoing_edges(exercise_id):
            queue.append(edge.to_exercise_id)
    return list(seen)


def snapshot_exercise_progress(
    repo: FitnessRepository,
    exercise_ids: list[str],
) -> dict[str, UserExerciseProgress | None]:
    return {exercise_id: repo.get_user_progress(exercise_id) for exercise_id in exercise_ids}


def snapshot_exercise_progress_for_session(
    repo: FitnessRepository,
    exercise_ids: list[str],
) -> dict[str, UserExerciseProgress | None]:
    """Snapshot session exercises plus progression unlock side-effects for undo."""
    affected = exercise_ids_affected_by_logging(repo, exercise_ids)
    return snapshot_exercise_progress(repo, affected)


def restore_exercise_progress(
    repo: FitnessRepository,
    snapshots: dict[str, UserExerciseProgress | None],
) -> None:
    for exercise_id, progress in snapshots.items():
        if progress is None:
            repo.delete_user_progress(exercise_id)
        else:
            repo.upsert_user_progress(progress)


def undo_workout_session_log(
    repo: FitnessRepository,
    session_id: str,
    *,
    exercise_ids: list[str],
    progress_snapshots: dict[str, UserExerciseProgress | None],
    entries: dict | None = None,
    body_presence_snapshot: dict | None = None,
    session_date: str | None = None,
) -> None:
    """Reverse a just-logged workout (SQLite session, progress, optional daily bridge)."""
    repo.delete_workout_session(session_id)
    restore_exercise_progress(repo, progress_snapshots)
    if entries is not None and session_date is not None:
        restore_body_presence_entry(entries, session_date, body_presence_snapshot)
