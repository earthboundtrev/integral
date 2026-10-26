"""Normalize movement log reps_per_set for program evaluation (issue #227)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_unreadable_reps_warnings: list[dict[str, str]] = []


def reset_unreadable_reps_warnings() -> None:
    _unreadable_reps_warnings.clear()


def drain_unreadable_reps_warnings() -> list[dict[str, str]]:
    drained = list(_unreadable_reps_warnings)
    _unreadable_reps_warnings.clear()
    return drained


def is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_numeric_string(value: str) -> int | float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return None


def normalize_reps_per_set(value: Any) -> list[int | float]:
    """Return a list of per-set rep counts; scalars become a one-element list."""
    reps, _malformed = classify_reps_per_set(value)
    return reps


def classify_reps_per_set(value: Any) -> tuple[list[int | float], bool]:
    """
    Classify reps_per_set for evaluation.

    Returns (normalized_reps, malformed). Malformed is True when the value was
    present but cannot be interpreted as reps (startup should skip, not crash).
    """
    if value is None:
        return [], False
    if isinstance(value, list):
        reps = [v for v in value if is_numeric(v)]
        if value and not reps:
            return [], True
        return reps, False
    if is_numeric(value):
        return [value], False
    if isinstance(value, str):
        parsed = _parse_numeric_string(value)
        if parsed is None:
            return [], True
        return [parsed], False
    return [], True


def movement_label_from_log(log: dict) -> str:
    return (
        log.get("movement_name")
        or log.get("chain_name")
        or log.get("movement_key")
        or log.get("chain_key")
        or "movement"
    )


def unreadable_reps_entry_id(date: str, movement: str, raw_value: Any) -> str:
    return f"{date}|{movement}|{repr(raw_value)}"


def note_unreadable_reps(
    log: dict,
    raw_value: Any,
    *,
    date: str | None = None,
) -> None:
    session_date = date or str(log.get("date") or "(no date)")
    movement = movement_label_from_log(log)
    entry_id = unreadable_reps_entry_id(session_date, movement, raw_value)
    if any(item.get("id") == entry_id for item in _unreadable_reps_warnings):
        return
    logger.warning(
        "Skipping movement log with unreadable reps_per_set=%r (date=%s movement=%s)",
        raw_value,
        session_date,
        movement,
    )
    _unreadable_reps_warnings.append(
        {
            "id": entry_id,
            "date": session_date,
            "movement": movement,
            "raw": repr(raw_value),
        }
    )


def reps_for_evaluation(
    log: dict,
    *,
    date: str | None = None,
) -> list[int | float]:
    """Normalize reps_per_set from a log; record malformed values for UI/logging."""
    if "reps_per_set" not in log:
        return []
    raw = log.get("reps_per_set")
    reps, malformed = classify_reps_per_set(raw)
    if malformed:
        note_unreadable_reps(log, raw, date=date)
        return []
    return reps
