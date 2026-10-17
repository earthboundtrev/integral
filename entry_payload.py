"""Shared daily log entry payload builder — issues #107, #113."""

from __future__ import annotations

from typing import Any


def clamp_rating(value: int | float | str | None) -> int | None:
    """Return an integer 1–10, or None if not a valid rating."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        n = value
    elif isinstance(value, float):
        n = int(value)
    else:
        text = str(value).strip()
        if not text or not text.isdigit():
            return None
        n = int(text)
    if 1 <= n <= 10:
        return n
    if n > 10:
        return 10
    return None


def build_entry_payload(
    cat_data: dict,
    rating: int | None,
    checklist: dict[str, bool] | None = None,
    metrics: dict[str, float | int] | None = None,
    notes: str = "",
    *,
    include_notes: bool = True,
) -> dict[str, Any] | None:
    """
    Build a per-domain entry dict matching save_log output shape.

    Returns None when there is no valid rating (unrated domains are not written).
    Never returns an empty dict.
    """
    _ = cat_data  # reserved for future category-specific rules
    clamped = clamp_rating(rating)
    if clamped is None:
        return None

    payload: dict[str, Any] = {"rating": clamped}
    if include_notes:
        payload["notes"] = notes.strip() if isinstance(notes, str) else str(notes or "")

    if checklist:
        cleaned = {str(k): bool(v) for k, v in checklist.items()}
        if cleaned:
            payload["checklist"] = cleaned

    if metrics:
        cleaned_metrics: dict[str, float | int] = {}
        for name, val in metrics.items():
            if isinstance(val, bool):
                continue
            if isinstance(val, int):
                cleaned_metrics[str(name)] = val
            elif isinstance(val, float):
                cleaned_metrics[str(name)] = val
            else:
                try:
                    cleaned_metrics[str(name)] = float(val)
                except (TypeError, ValueError):
                    continue
        if cleaned_metrics:
            payload["metrics"] = cleaned_metrics

    if len(payload) == 1 and "rating" in payload:
        return payload
    return payload


def merge_entry_updates(existing: dict | None, updates: dict) -> dict:
    """Deep-merge reflect/log updates into an existing entry without clobbering untouched detail."""
    base = dict(existing or {})
    if not updates:
        return base

    for key in ("rating", "notes", "backdate_reason"):
        if key in updates:
            base[key] = updates[key]

    if "checklist" in updates:
        merged_cl = dict(base.get("checklist") or {})
        merged_cl.update(updates["checklist"])
        base["checklist"] = merged_cl

    if "metrics" in updates:
        merged_m = dict(base.get("metrics") or {})
        merged_m.update(updates["metrics"])
        base["metrics"] = merged_m

    return base


def collect_touched_checklist(
    check_vars: dict[str, Any],
    *,
    touched: set[str],
) -> dict[str, bool] | None:
    if not touched:
        return None
    out = {name: bool(check_vars[name].get()) for name in touched if name in check_vars}
    return out or None


def _read_metric_var(var: Any) -> float | int | None:
    try:
        val = var.get()
    except (ValueError, Exception):
        return None
    if isinstance(val, float) and val.is_integer():
        return int(val)
    if isinstance(val, (int, float)):
        return val
    return None


def collect_touched_metrics(
    metric_vars: dict[str, Any],
    cat_data: dict,
    *,
    touched: set[str],
) -> dict[str, float | int] | None:
    _ = cat_data
    if not touched:
        return None
    out: dict[str, float | int] = {}
    for name in touched:
        var = metric_vars.get(name)
        if var is None:
            continue
        val = _read_metric_var(var)
        if val is not None:
            out[name] = val
    return out or None
