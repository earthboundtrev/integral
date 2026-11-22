"""Update saved workout sessions in place (#286) — pure logic, no Tkinter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fitness.set_field_validation import (
    SetFieldValidationError,
    parse_optional_body_weight,
    parse_optional_duration_minutes,
    parse_optional_hold_text,
    parse_optional_weight_text,
    parse_required_reps,
    parse_required_sets,
    parse_session_notes,
)
from progression.db import FitnessRepository
from progression.models import WorkoutSet


class SessionEditError(ValueError):
    """Failed to persist session edit (safe, no user payload in message)."""


@dataclass(frozen=True)
class SetEditPayload:
    set_id: str
    exercise_id: str
    sets: int
    reps: int
    hold_seconds: float | None
    weight_kg: float | None
    form_quality: int | None = None


@dataclass(frozen=True)
class SessionEditPayload:
    session_id: str
    notes: str
    duration_minutes: int | None
    body_weight_kg: float | None
    sets: list[SetEditPayload]


def resolve_exercise_id_from_name(repo: FitnessRepository, name: str) -> str:
    """Map combobox label to catalog exercise id; never creates catalog rows."""
    needle = (name or "").strip()
    if not needle:
        raise SetFieldValidationError("Exercise is required.")
    matches = [ex for ex in repo.list_exercises() if ex.name == needle]
    if len(matches) != 1:
        raise SetFieldValidationError("Choose an exercise from the list.")
    return matches[0].id


def exercise_id_active(repo: FitnessRepository, exercise_id: str) -> bool:
    check = getattr(repo, "exercise_exists_active", None)
    if callable(check):
        return bool(check(exercise_id))
    return repo.get_exercise(exercise_id) is not None


def parse_set_row(
    *,
    set_id: str,
    exercise_name: str,
    sets_text: str,
    reps_text: str,
    hold_text: str,
    weight_text: str,
    repo: FitnessRepository,
    form_quality: int | None = None,
) -> SetEditPayload:
    exercise_id = resolve_exercise_id_from_name(repo, exercise_name)
    if not exercise_id_active(repo, exercise_id):
        raise SetFieldValidationError("Choose an exercise from the list.")
    return SetEditPayload(
        set_id=set_id,
        exercise_id=exercise_id,
        sets=parse_required_sets(sets_text),
        reps=parse_required_reps(reps_text),
        hold_seconds=parse_optional_hold_text(hold_text),
        weight_kg=parse_optional_weight_text(weight_text),
        form_quality=form_quality,
    )


def build_session_edit_payload(
    repo: FitnessRepository,
    session_id: str,
    *,
    notes_text: str,
    duration_text: str,
    body_weight_text: str,
    set_rows: list[dict[str, Any]],
) -> SessionEditPayload:
    parsed_sets: list[SetEditPayload] = []
    for row in set_rows:
        parsed_sets.append(
            parse_set_row(
                set_id=row["set_id"],
                exercise_name=row["exercise_name"],
                sets_text=row["sets"],
                reps_text=row["reps"],
                hold_text=row.get("hold", ""),
                weight_text=row.get("weight", ""),
                repo=repo,
                form_quality=row.get("form_quality"),
            )
        )
    return SessionEditPayload(
        session_id=session_id,
        notes=parse_session_notes(notes_text),
        duration_minutes=parse_optional_duration_minutes(duration_text),
        body_weight_kg=parse_optional_body_weight(body_weight_text),
        sets=parsed_sets,
    )


def affected_exercise_ids(
    before: list[WorkoutSet],
    after: list[SetEditPayload],
) -> list[str]:
    old_ids = {s.exercise_id for s in before}
    new_ids = {s.exercise_id for s in after}
    return list(dict.fromkeys(list(old_ids | new_ids)))


def update_saved_workout_session(
    repo: FitnessRepository,
    payload: SessionEditPayload,
    *,
    before_sets: list[WorkoutSet] | None = None,
) -> list[str]:
    """Persist in-place updates; returns affected exercise ids."""
    if before_sets is None:
        before_sets = repo.list_workout_sets(payload.session_id)
    exercise_ids = affected_exercise_ids(before_sets, payload.sets)
    update_fn = getattr(repo, "update_saved_workout_session", None)
    if not callable(update_fn):
        raise SessionEditError("Update not supported")
    update_fn(
        payload.session_id,
        {
            "notes": payload.notes,
            "duration_minutes": payload.duration_minutes,
            "body_weight_kg": payload.body_weight_kg,
        },
        [
            {
                "id": s.set_id,
                "exercise_id": s.exercise_id,
                "sets": s.sets,
                "reps": s.reps,
                "hold_seconds": s.hold_seconds,
                "weight_kg": s.weight_kg,
                "form_quality": s.form_quality,
            }
            for s in payload.sets
        ],
        exercise_ids,
    )
    return exercise_ids