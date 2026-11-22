"""Shared set-field parsing and validation for workout log and history edit (#286 / #257)."""

from __future__ import annotations

import math
from typing import Any

from fitness.reps_normalization import classify_reps_per_set

MAX_SETS = 99
MAX_REPS = 999
MAX_HOLD_SECONDS = 3600.0
MAX_WEIGHT_KG = 999.0
MAX_DURATION_MINUTES = 600
MAX_BODY_WEIGHT_KG = 500.0
MAX_SESSION_NOTES_LEN = 8000


class SetFieldValidationError(ValueError):
    """User-facing validation failure (no payload values in message)."""


def _reject_non_finite(value: float, label: str) -> None:
    if math.isnan(value) or math.isinf(value):
        raise SetFieldValidationError(f"{label} must be a finite number.")


def parse_optional_weight_text(text: str) -> float | None:
    """Parse weight entry; empty means None. Comma decimals accepted (e.g. 40,5 → 40.5)."""
    raw = (text or "").strip()
    if not raw:
        return None
    normalized = raw.replace(",", ".")
    if "-" in normalized or normalized.count(".") > 1:
        raise SetFieldValidationError("Weight must be a number.")
    try:
        value = float(normalized)
    except ValueError as exc:
        raise SetFieldValidationError("Weight must be a number.") from exc
    _reject_non_finite(value, "Weight")
    if value < 0:
        raise SetFieldValidationError("Weight cannot be negative.")
    if value > MAX_WEIGHT_KG:
        raise SetFieldValidationError("Weight is too large.")
    if value == 0:
        return None
    return value


def parse_optional_hold_text(text: str) -> float | None:
    raw = (text or "").strip()
    if not raw:
        return None
    normalized = raw.replace(",", ".")
    try:
        value = float(normalized)
    except ValueError as exc:
        raise SetFieldValidationError("Hold must be a number.") from exc
    _reject_non_finite(value, "Hold")
    if value < 0:
        raise SetFieldValidationError("Hold cannot be negative.")
    if value > MAX_HOLD_SECONDS:
        raise SetFieldValidationError("Hold is too large.")
    if value == 0:
        return None
    return value


def parse_required_sets(value: Any) -> int:
    text = str(value).strip()
    if not text:
        raise SetFieldValidationError("Sets is required.")
    if not text.isdigit():
        raise SetFieldValidationError("Sets must be a whole number.")
    n = int(text)
    if n < 1 or n > MAX_SETS:
        raise SetFieldValidationError("Sets must be between 1 and 99.")
    return n


def parse_required_reps(value: Any) -> int:
    text = str(value).strip()
    if not text:
        raise SetFieldValidationError("Reps is required.")
    reps, malformed = classify_reps_per_set(text)
    if malformed or not reps:
        raise SetFieldValidationError("Reps must be a whole number.")
    if len(reps) != 1 or not isinstance(reps[0], int):
        raise SetFieldValidationError("Reps must be a whole number.")
    n = int(reps[0])
    if n < 1 or n > MAX_REPS:
        raise SetFieldValidationError("Reps must be between 1 and 999.")
    return n


def parse_optional_duration_minutes(value: Any) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    if not text.isdigit():
        raise SetFieldValidationError("Duration must be a whole number of minutes.")
    n = int(text)
    if n < 0 or n > MAX_DURATION_MINUTES:
        raise SetFieldValidationError("Duration is out of range.")
    if n == 0:
        return None
    return n


def parse_optional_body_weight(value: Any) -> float | None:
    return parse_optional_weight_text(str(value))


def parse_session_notes(value: Any) -> str:
    text = str(value) if value is not None else ""
    if len(text) > MAX_SESSION_NOTES_LEN:
        raise SetFieldValidationError("Session notes are too long.")
    return text


def format_weight_display(weight_kg: float | None) -> str:
    if weight_kg is None:
        return ""
    w = float(weight_kg)
    if w.is_integer():
        return str(int(w))
    return f"{w:g}"


def format_hold_display(hold_seconds: float | None) -> str:
    if hold_seconds is None:
        return ""
    h = float(hold_seconds)
    if h.is_integer():
        return str(int(h))
    return f"{h:g}"