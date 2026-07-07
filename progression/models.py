from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


@dataclass(frozen=True)
class Exercise:
    name: str
    source_book: str
    family: str
    mastery_criteria: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_id)


@dataclass(frozen=True)
class ProgressionEdge:
    from_exercise_id: str
    to_exercise_id: str
    unlock_condition: dict[str, Any]
    edge_type: str = "prerequisite"
    id: str = field(default_factory=new_id)


@dataclass(frozen=True)
class UserExerciseProgress:
    exercise_id: str
    status: str = "locked"
    current_step: int | None = None
    best_reps: int | None = None
    best_hold_time: float | None = None
    best_weight: float | None = None
    last_logged_at: str | None = None
    achieved_at: str | None = None


@dataclass(frozen=True)
class WorkoutSession:
    date: str
    notes: str = ""
    duration_minutes: int | None = None
    body_weight_kg: float | None = None
    id: str = field(default_factory=new_id)


@dataclass(frozen=True)
class WorkoutSet:
    session_id: str
    exercise_id: str
    sets: int | None = None
    reps: int | None = None
    hold_seconds: float | None = None
    weight_kg: float | None = None
    form_quality: int | None = None
    id: str = field(default_factory=new_id)


@dataclass(frozen=True)
class BodyCompositionLog:
    date: str
    weight_kg: float | None = None
    measurements: dict[str, Any] = field(default_factory=dict)
    photo_path: str | None = None
    id: str = field(default_factory=new_id)
