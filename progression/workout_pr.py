"""Personal-record badges and best-set metrics for workout history (#117).

PR display uses ``user_exercise_progress.best_*`` when consistent with history.
If stored bests lag behind aggregated workout_sets maxima, history wins for
display and badge thresholds (see ``resolve_display_bests``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from progression.models import UserExerciseProgress, WorkoutSet

_EPS = 1e-6

PrBadgeKind = Literal["none", "tie", "beat"]


@dataclass
class ExerciseBests:
    best_reps: int | None = None
    best_hold_time: float | None = None
    best_weight: float | None = None

    def copy(self) -> ExerciseBests:
        return ExerciseBests(
            best_reps=self.best_reps,
            best_hold_time=self.best_hold_time,
            best_weight=self.best_weight,
        )


def _pos_int(value) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _pos_float(value) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def bests_from_progress(progress: UserExerciseProgress | None) -> ExerciseBests:
    if progress is None:
        return ExerciseBests()
    return ExerciseBests(
        best_reps=progress.best_reps,
        best_hold_time=progress.best_hold_time,
        best_weight=progress.best_weight,
    )


def bests_from_row(row) -> ExerciseBests:
    return ExerciseBests(
        best_reps=_pos_int(row["best_reps"] if "best_reps" in row.keys() else None),
        best_hold_time=_pos_float(
            row["best_hold_time"] if "best_hold_time" in row.keys() else None
        ),
        best_weight=_pos_float(row["best_weight"] if "best_weight" in row.keys() else None),
    )


def aggregate_bests_from_sets(sets: list[WorkoutSet]) -> ExerciseBests:
    best_reps: int | None = None
    best_hold: float | None = None
    best_weight: float | None = None
    for row in sets:
        r = _pos_int(row.reps)
        if r is not None:
            best_reps = r if best_reps is None else max(best_reps, r)
        h = _pos_float(row.hold_seconds)
        if h is not None:
            best_hold = h if best_hold is None else max(best_hold, h)
        w = _pos_float(row.weight_kg)
        if w is not None:
            best_weight = w if best_weight is None else max(best_weight, w)
    return ExerciseBests(best_reps=best_reps, best_hold_time=best_hold, best_weight=best_weight)


def merge_bests(a: ExerciseBests, b: ExerciseBests) -> ExerciseBests:
    def mx(x, y):
        if x is None:
            return y
        if y is None:
            return x
        return max(x, y)

    return ExerciseBests(
        best_reps=mx(a.best_reps, b.best_reps),
        best_hold_time=mx(a.best_hold_time, b.best_hold_time),
        best_weight=mx(a.best_weight, b.best_weight),
    )


def stored_bests_consistent(stored: ExerciseBests, computed: ExerciseBests) -> bool:
    """True when each stored best equals the history aggregate (or both unset)."""

    def eq(a, b):
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= _EPS

    return (
        eq(stored.best_reps, computed.best_reps)
        and eq(stored.best_hold_time, computed.best_hold_time)
        and eq(stored.best_weight, computed.best_weight)
    )


def resolve_display_bests(stored: ExerciseBests, computed: ExerciseBests) -> ExerciseBests:
    """Prefer stored progress when consistent; otherwise use history aggregate."""
    if stored_bests_consistent(stored, computed):
        return stored
    return computed


def classify_set_pr(wset: WorkoutSet, prior: ExerciseBests) -> PrBadgeKind:
    """Classify one logged set vs prior all-time bests (before this set)."""
    weight = _pos_float(wset.weight_kg)
    reps = _pos_int(wset.reps)
    hold = _pos_float(wset.hold_seconds)

    if weight is not None:
        pw = prior.best_weight
        pr = prior.best_reps
        if pw is None:
            return "beat"
        if weight > pw + _EPS:
            return "beat"
        if abs(weight - pw) <= _EPS:
            if reps is None and pr is None:
                return "tie"
            if reps is not None and pr is not None:
                if reps > pr:
                    return "beat"
                return "tie"
            if reps is not None and pr is None:
                return "beat"
            return "tie"
        return "none"

    if hold is not None:
        ph = prior.best_hold_time
        if ph is None:
            return "beat"
        if hold > ph + _EPS:
            return "beat"
        if abs(hold - ph) <= _EPS:
            return "tie"
        return "none"

    if reps is not None:
        pr = prior.best_reps
        if pr is None:
            return "beat"
        if reps > pr:
            return "beat"
        if reps == pr:
            return "tie"
        return "none"

    return "none"


def update_rolling_bests(prior: ExerciseBests, wset: WorkoutSet) -> ExerciseBests:
    """Update rolling bests after applying a set (for multiple sets in one session)."""
    next_best = prior.copy()
    weight = _pos_float(wset.weight_kg)
    reps = _pos_int(wset.reps)
    hold = _pos_float(wset.hold_seconds)
    if weight is not None:
        if next_best.best_weight is None or weight > next_best.best_weight + _EPS:
            next_best.best_weight = weight
            if reps is not None:
                next_best.best_reps = reps
        elif abs(weight - (next_best.best_weight or 0)) <= _EPS and reps is not None:
            prev_r = next_best.best_reps
            next_best.best_reps = reps if prev_r is None else max(prev_r, reps)
    elif hold is not None:
        if next_best.best_hold_time is None or hold > next_best.best_hold_time + _EPS:
            next_best.best_hold_time = hold
    elif reps is not None:
        if next_best.best_reps is None or reps > next_best.best_reps:
            next_best.best_reps = reps
    return next_best


def pr_badges_for_sets(
    sets: list[WorkoutSet], prior: ExerciseBests
) -> list[PrBadgeKind]:
    """Badge each set in log order; updates rolling bests between sets."""
    rolling = prior.copy()
    badges: list[PrBadgeKind] = []
    for wset in sets:
        badges.append(classify_set_pr(wset, rolling))
        rolling = update_rolling_bests(rolling, wset)
    return badges


def pr_badge_label(kind: PrBadgeKind) -> str:
    if kind == "beat":
        return "PR"
    if kind == "tie":
        return "=PR"
    return ""


def format_best_display(bests: ExerciseBests) -> str:
    """Locale-neutral PR summary for UI and screen readers."""
    parts: list[str] = []
    if bests.best_weight is not None:
        w = bests.best_weight
        w_txt = f"{w:g}" if float(w).is_integer() else f"{w:.1f}"
        parts.append(f"{w_txt} kg")
        if bests.best_reps is not None:
            parts.append(f"{bests.best_reps} reps at that weight")
    elif bests.best_hold_time is not None:
        h = bests.best_hold_time
        h_txt = f"{h:g}" if float(h).is_integer() else f"{h:.1f}"
        parts.append(f"{h_txt} s hold")
    elif bests.best_reps is not None:
        parts.append(f"{bests.best_reps} reps")
    if not parts:
        return "No personal record yet"
    return " · ".join(parts)
