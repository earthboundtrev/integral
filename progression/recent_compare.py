"""Exercise session snapshots, volume totals, and progress cues (#74 / #78)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from progression.db import FitnessRepository
from progression.models import WorkoutSession, WorkoutSet

DEFAULT_WINDOW_DAYS = 7
DEFAULT_HISTORY_LIMIT = 40
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
    volume: float | None = None
    volume_kind: str = ""  # weighted | reps | hold


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


def _positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _sets_for_volume(sets: Any, *, has_work: bool) -> int:
    if sets is not None:
        try:
            n = int(sets)
        except (TypeError, ValueError):
            n = -1
        else:
            if n == 0:
                return 0
            if n > 0:
                return n
    return 1 if has_work else 0


def compute_volume_score(
    *,
    sets: int | None = None,
    reps: int | None = None,
    weight_kg: float | None = None,
    hold_seconds: float | None = None,
) -> tuple[float | None, str]:
    """
    Combined volume for one logical set block.

    Prefer weight × sets × reps when weighted; else hold volume when hold is set
    (ignore default reps on hold-focused movements); else sets × reps.
    """
    r = _positive_int(reps)
    w = _positive_float(weight_kg)
    h = _positive_float(hold_seconds)
    if w is not None and r is not None:
        sn = _sets_for_volume(sets, has_work=True)
        return float(w * sn * r), "weighted"
    # Holds often leave default reps in the form — prefer hold when present.
    if h is not None and w is None:
        sn = _sets_for_volume(sets, has_work=True)
        return float(sn * h), "hold"
    if r is not None:
        sn = _sets_for_volume(sets, has_work=True)
        return float(sn * r), "reps"
    return None, ""


def volume_from_workout_sets(sets: list[WorkoutSet]) -> tuple[float | None, str]:
    """Sum volume across workout_set rows (same-exercise session aggregate)."""
    weighted = 0.0
    unweighted = 0.0
    hold_vol = 0.0
    saw_w = saw_r = saw_h = False
    for row in sets:
        if row is None:
            continue
        score, kind = compute_volume_score(
            sets=row.sets,
            reps=row.reps,
            weight_kg=row.weight_kg,
            hold_seconds=row.hold_seconds,
        )
        if score is None:
            continue
        if kind == "weighted":
            saw_w = True
            weighted += score
        elif kind == "reps":
            saw_r = True
            unweighted += score
        elif kind == "hold":
            saw_h = True
            hold_vol += score
    if saw_w and not saw_r and not saw_h and weighted > 0:
        return weighted, "weighted"
    if saw_r and not saw_w and not saw_h and unweighted > 0:
        return unweighted, "reps"
    if saw_h and not saw_w and not saw_r and hold_vol > 0:
        return hold_vol, "hold"
    # Mixed kinds in one session — do not invent a combined score.
    if saw_w or saw_r or saw_h:
        return None, ""
    return None, ""


def format_volume(volume: float | None, kind: str) -> str:
    if volume is None:
        return "—"
    if float(volume).is_integer():
        num = f"{int(volume)}"
    else:
        num = f"{volume:.1f}"
    if kind == "weighted":
        return f"{num} kg·vol"
    if kind == "hold":
        return f"{num}s hold·vol"
    if kind == "reps":
        return f"{num} rep·vol"
    return num


def snapshot_from_draft(
    *,
    sets: int | None = None,
    reps: int | None = None,
    weight_kg: float | None = None,
    hold_seconds: float | None = None,
    date_str: str = "",
    session_id: str = "draft",
) -> ExerciseSessionSnapshot:
    """Build a snapshot from the live log form values."""
    vol, kind = compute_volume_score(
        sets=sets, reps=reps, weight_kg=weight_kg, hold_seconds=hold_seconds
    )
    return ExerciseSessionSnapshot(
        session_id=session_id,
        date=(date_str or "").strip(),
        sets=_positive_int(sets),
        reps=_positive_int(reps),
        hold_seconds=_positive_float(hold_seconds),
        weight_kg=_positive_float(weight_kg),
        volume=vol,
        volume_kind=kind,
    )


def snapshot_from_pending_items(
    items: list[dict],
    *,
    date_str: str = "",
    session_id: str = "draft",
) -> ExerciseSessionSnapshot:
    """Aggregate volume from queued / draft set dicts (session logger)."""
    fake_sets: list[WorkoutSet] = []
    for i, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        fake_sets.append(
            WorkoutSet(
                id=f"p{i}",
                session_id=session_id,
                exercise_id=str(item.get("exercise_id") or "draft"),
                sets=item.get("sets"),
                reps=item.get("reps"),
                hold_seconds=item.get("hold_seconds"),
                weight_kg=item.get("weight_kg"),
            )
        )
    if not fake_sets:
        return snapshot_from_draft(date_str=date_str, session_id=session_id)
    session = WorkoutSession(id=session_id, date=date_str or "", notes="")
    snap = aggregate_exercise_sets(session, fake_sets)
    return snap or snapshot_from_draft(date_str=date_str, session_id=session_id)


def aggregate_exercise_sets(
    session: WorkoutSession, sets: list[WorkoutSet]
) -> ExerciseSessionSnapshot | None:
    """Collapse one session's sets for a single exercise into a scannable snapshot."""
    relevant = [s for s in sets if s is not None]
    if not relevant:
        return None
    total_sets = 0
    has_sets = False
    total_reps = 0
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
            # Prefer summed reps×sets contribution for display; fall back to sum of reps.
            sn = _sets_for_volume(row.sets, has_work=True)
            total_reps += sn * max(int(row.reps), 0)
        if row.hold_seconds is not None:
            has_hold = True
            max_hold = max(max_hold, float(row.hold_seconds))
        if row.weight_kg is not None:
            has_weight = True
            max_weight = max(max_weight, float(row.weight_kg))
        if row.form_quality is not None:
            has_form = True
            max_form = max(max_form, int(row.form_quality))
    vol, kind = volume_from_workout_sets(relevant)
    return ExerciseSessionSnapshot(
        session_id=session.id,
        date=session.date,
        sets=total_sets if has_sets and total_sets > 0 else None,
        reps=total_reps if has_reps and total_reps > 0 else None,
        hold_seconds=max_hold if has_hold and max_hold > 0 else None,
        weight_kg=max_weight if has_weight and max_weight > 0 else None,
        form_quality=max_form if has_form and max_form > 0 else None,
        rows=len(relevant),
        volume=vol,
        volume_kind=kind,
    )


def _snapshots_for_sessions(
    repo: FitnessRepository, exercise_id: str, sessions: list[WorkoutSession]
) -> list[ExerciseSessionSnapshot]:
    out: list[ExerciseSessionSnapshot] = []
    for session in sessions:
        sets = [
            s
            for s in repo.list_workout_sets(session.id)
            if (s.exercise_id or "") == exercise_id
        ]
        snap = aggregate_exercise_sets(session, sets)
        if snap is not None:
            out.append(snap)
    return out


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
        sessions = []
        for session in repo.list_workout_sessions(limit=max(session_limit, 500)):
            day = _parse_day(session.date)
            if day is None or day > end or day < start:
                continue
            sessions.append(session)
    return _snapshots_for_sessions(repo, eid, sessions)


def exercise_history_snapshots(
    repo: FitnessRepository,
    exercise_id: str,
    *,
    as_of: str | None = None,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> list[ExerciseSessionSnapshot]:
    """Newest-first history for an exercise on or before as_of (not week-limited)."""
    eid = (exercise_id or "").strip()
    if not eid:
        return []
    end = datetime.now().date()
    if as_of:
        parsed = _parse_day(as_of)
        if parsed is None:
            return []
        end = parsed
    cap = max(int(limit), 1)
    list_fn = getattr(repo, "list_sessions_for_exercise_upto", None)
    if callable(list_fn):
        sessions = list_fn(eid, end_date=end.isoformat(), limit=cap)
    else:
        between = getattr(repo, "list_sessions_for_exercise_between", None)
        if callable(between):
            sessions = between(
                eid,
                start_date="1970-01-01",
                end_date=end.isoformat(),
                limit=cap,
            )
        else:
            sessions = []
            for session in repo.list_workout_sessions(limit=max(cap, 500)):
                day = _parse_day(session.date)
                if day is None or day > end:
                    continue
                sessions.append(session)
                if len(sessions) >= cap:
                    break
    return _snapshots_for_sessions(repo, eid, sessions)


def compare_to_prior(
    current: ExerciseSessionSnapshot | None,
    prior: ExerciseSessionSnapshot | None,
) -> ProgressCue:
    """Volume-first compare vs last log (#78)."""
    return compare_volume_to_prior(current, prior)


def compare_volume_to_prior(
    current: ExerciseSessionSnapshot | None,
    prior: ExerciseSessionSnapshot | None,
) -> ProgressCue:
    """↑ / → / ↓ on combined volume vs the prior log (same volume_kind only)."""
    if current is None or current.volume is None:
        return ProgressCue("none", "", "Enter sets × reps to compare")
    if prior is None:
        return ProgressCue("none", "", "No prior log yet")
    if prior.volume is None:
        return ProgressCue("none", "", "Prior log not comparable — open details")
    cur_kind = (current.volume_kind or "").strip()
    prv_kind = (prior.volume_kind or "").strip()
    if not cur_kind or not prv_kind or cur_kind != prv_kind:
        return ProgressCue("none", "", "Volume kinds differ — compare details")
    cur = float(current.volume)
    prv = float(prior.volume)
    cur_txt = format_volume(cur, cur_kind)
    prv_txt = format_volume(prv, prv_kind)
    if cur > prv + _WEIGHT_EPS:
        return ProgressCue(
            "up",
            "volume",
            f"↑ volume vs last ({cur_txt} ← {prv_txt})",
        )
    if cur < prv - _WEIGHT_EPS:
        return ProgressCue(
            "down",
            "volume",
            f"↓ volume vs last ({cur_txt} ← {prv_txt})",
        )
    return ProgressCue(
        "flat",
        "volume",
        f"→ volume vs last ({cur_txt})",
    )


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
    if snapshot.volume is not None:
        parts.append(format_volume(snapshot.volume, snapshot.volume_kind))
    if snapshot.form_quality is not None:
        parts.append(f"form {snapshot.form_quality}/10")
    if snapshot.rows > 1:
        parts.append(f"{snapshot.rows} logged rows")
    body = ", ".join(parts) if parts else "logged"
    return f"{snapshot.date}\n{body}"
