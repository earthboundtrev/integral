"""Recent exercise session snapshots and progress cues for mid-log compare (#74)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from progression.db import FitnessRepository
from progression.models import WorkoutSession, WorkoutSet

DEFAULT_WINDOW_DAYS = 7
_WEIGHT_EPS = 1e-6


@dataclass(frozen=True)
class ExerciseSessionSnapshot:
    session_id: str
    date: str
    sets: int | None = None
    reps: int | None = None
    hold_seconds: float | None = None
    weight_kg: float | None = None
    form_quality: int | None = None
    rows: int = 1


Direction = Literal["up", "flat", "down", "none"]


@dataclass(frozen=True)
class ProgressCue:
    direction: Direction
    metric: str
    label: str


def _parse_day(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def is_valid_as_of(value: str | None) -> bool:
    """True if as_of is empty (default today) or a parseable YYYY-MM-DD date."""
    raw = (value or "").strip()
    if not raw:
        return True
    return _parse_day(raw) is not None


def _positive_int(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _positive_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def aggregate_exercise_sets(
    session: WorkoutSession, sets: list[WorkoutSet]
) -> ExerciseSessionSnapshot | None:
    """Collapse one session's sets for a single exercise into a scannable snapshot."""
    relevant = [s for s in sets if s is not None]
    if not relevant:
        return None
    total_sets = 0
    has_sets = False
    max_reps = 0
    has_reps = False
    max_hold = 0.0
    has_hold = False
    max_weight = 0.0
    has_weight = False
    max_form = 0
    has_form = False
    for row in relevant:
        if row.sets is not None:
            has_sets = True
            total_sets += max(int(row.sets), 0)
        if row.reps is not None:
            has_reps = True
            max_reps = max(max_reps, int(row.reps))
        if row.hold_seconds is not None:
            has_hold = True
            max_hold = max(max_hold, float(row.hold_seconds))
        if row.weight_kg is not None:
            has_weight = True
            max_weight = max(max_weight, float(row.weight_kg))
        if row.form_quality is not None:
            has_form = True
            max_form = max(max_form, int(row.form_quality))
    return ExerciseSessionSnapshot(
        session_id=session.id,
        date=session.date,
        sets=total_sets if has_sets and total_sets > 0 else None,
        reps=max_reps if has_reps and max_reps > 0 else None,
        hold_seconds=max_hold if has_hold and max_hold > 0 else None,
        weight_kg=max_weight if has_weight and max_weight > 0 else None,
        form_quality=max_form if has_form and max_form > 0 else None,
        rows=len(relevant),
    )


def recent_exercise_snapshots(
    repo: FitnessRepository,
    exercise_id: str,
    *,
    as_of: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    session_limit: int = 100,
) -> list[ExerciseSessionSnapshot]:
    """
    Return newest-first snapshots for exercise_id within [as_of - (window_days-1), as_of].
    """
    eid = (exercise_id or "").strip()
    if not eid:
        return []
    end = datetime.now().date()
    if as_of:
        parsed = _parse_day(as_of)
        if parsed is None:
            # Incomplete/invalid date while typing — do not invent "today".
            return []
        end = parsed
    days = max(int(window_days), 1)
    start = end - timedelta(days=days - 1)
    list_fn = getattr(repo, "list_sessions_for_exercise_between", None)
    if callable(list_fn):
        sessions = list_fn(
            eid,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            limit=session_limit,
        )
    else:
        # Test doubles / older repos: scan all sessions and filter in Python.
        sessions = []
        for session in repo.list_workout_sessions(limit=max(session_limit, 500)):
            day = _parse_day(session.date)
            if day is None or day > end or day < start:
                continue
            sessions.append(session)

    out: list[ExerciseSessionSnapshot] = []
    for session in sessions:
        sets = [
            s
            for s in repo.list_workout_sets(session.id)
            if (s.exercise_id or "") == eid
        ]
        snap = aggregate_exercise_sets(session, sets)
        if snap is not None:
            out.append(snap)
    return out


def compare_to_prior(
    current: ExerciseSessionSnapshot | None,
    prior: ExerciseSessionSnapshot | None,
) -> ProgressCue:
    """Compare current vs older prior using weight → reps → hold priority."""
    if current is None:
        return ProgressCue("none", "", "")
    if prior is None:
        return ProgressCue("none", "", "First in window")

    cur_w = _positive_float(current.weight_kg)
    prv_w = _positive_float(prior.weight_kg)
    cur_r = _positive_int(current.reps)
    prv_r = _positive_int(prior.reps)
    cur_h = _positive_float(current.hold_seconds)
    prv_h = _positive_float(prior.hold_seconds)
    candidates: list[tuple[str, float | None, float | None, str]] = [
        ("weight_kg", cur_w, prv_w, "weight"),
        (
            "reps",
            float(cur_r) if cur_r is not None else None,
            float(prv_r) if prv_r is not None else None,
            "reps",
        ),
        ("hold_seconds", cur_h, prv_h, "hold"),
    ]
    first_flat: ProgressCue | None = None
    for metric, cur, prv, pretty in candidates:
        if cur is None or prv is None:
            continue
        if cur > prv + _WEIGHT_EPS:
            return ProgressCue("up", metric, f"↑ {pretty} vs prior")
        if cur < prv - _WEIGHT_EPS:
            return ProgressCue("down", metric, f"↓ {pretty} vs prior")
        if first_flat is None:
            first_flat = ProgressCue("flat", metric, f"→ {pretty} vs prior")
    return first_flat or ProgressCue("none", "", "No comparable metrics")


def progress_cues_for_snapshots(
    snapshots: list[ExerciseSessionSnapshot],
) -> list[ProgressCue]:
    """One cue per snapshot vs the next-older entry (list is newest-first)."""
    cues: list[ProgressCue] = []
    for i, snap in enumerate(snapshots):
        prior = snapshots[i + 1] if i + 1 < len(snapshots) else None
        cues.append(compare_to_prior(snap, prior))
    return cues


def format_snapshot_card(snapshot: ExerciseSessionSnapshot) -> str:
    parts: list[str] = []
    if snapshot.sets is not None:
        parts.append(f"{snapshot.sets} sets")
    if snapshot.reps is not None:
        parts.append(f"{snapshot.reps} reps")
    if snapshot.hold_seconds is not None:
        hold = snapshot.hold_seconds
        hold_txt = f"{hold:g}" if float(hold).is_integer() else f"{hold:.1f}"
        parts.append(f"{hold_txt}s hold")
    if snapshot.weight_kg is not None:
        w = snapshot.weight_kg
        w_txt = f"{w:g}" if float(w).is_integer() else f"{w:.1f}"
        parts.append(f"{w_txt} kg")
    if snapshot.form_quality is not None:
        parts.append(f"form {snapshot.form_quality}/10")
    if snapshot.rows > 1:
        parts.append(f"{snapshot.rows} logged rows")
    body = ", ".join(parts) if parts else "logged"
    return f"{snapshot.date}\n{body}"
