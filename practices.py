"""Daily practice logging — non-DAG routines (SPEC-318).

Practices are lightweight daily routines (Tibetan Rites, breathing, yoga holds) that don't
belong to the progressive fitness DAG. They live in ``data.json`` under ``practices.items``
and bridge a readable summary line into the linked Life Domain's day entry so they show up in
history, streaks, and AI insights. Add a preset to ``PRACTICE_PRESETS`` to support a new
routine — no UI changes required.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any

# Field ids a preset can surface. The UI renders only the fields listed by the preset.
FIELD_DURATION = "duration_minutes"
FIELD_COMPLETIONS = "completions"
FIELD_SETS = "sets"
FIELD_HOLD = "hold_seconds"
FIELD_PER_SIDE = "per_side"
FIELD_QUALITY = "quality"
FIELD_NOTES = "notes"

PRACTICE_PRESETS: dict[str, dict[str, Any]] = {
    "tibetan_rites": {
        "title": "Five Tibetan Rites",
        "domain": "Physical Practices & Movement",
        "fields": [FIELD_COMPLETIONS, FIELD_DURATION, FIELD_QUALITY, FIELD_NOTES],
        "labels": {FIELD_COMPLETIONS: "Reps per rite"},
        "hint": "Classic ramp: 3 reps/rite in week 1 → +2 each week → 21 by week 10.",
    },
    "pavanamuktasana": {
        "title": "Wind-releasing pose (Pavanamuktasana)",
        "domain": "Physical Practices & Movement",
        "fields": [FIELD_HOLD, FIELD_PER_SIDE, FIELD_DURATION, FIELD_QUALITY, FIELD_NOTES],
        "labels": {FIELD_HOLD: "Hold (sec)"},
        "hint": "Hold each side; note total time. Great for trapped gas.",
    },
    "diaphragmatic_breathing": {
        "title": "Diaphragmatic / belly breathing",
        "domain": "Breathwork & Mindfulness",
        "fields": [FIELD_DURATION, FIELD_COMPLETIONS, FIELD_QUALITY, FIELD_NOTES],
        "labels": {FIELD_DURATION: "Minutes", FIELD_COMPLETIONS: "Sessions"},
        "hint": "Slow belly breathing to stimulate the vagus nerve.",
    },
    "generic": {
        "title": "Yoga / movement practice",
        "domain": "Physical Practices & Movement",
        "fields": [FIELD_DURATION, FIELD_QUALITY, FIELD_NOTES],
        "labels": {},
        "hint": "",
    },
}

DEFAULT_PRESET = "generic"


def list_presets() -> list[dict[str, Any]]:
    return [
        {
            "id": preset_id,
            "title": preset["title"],
            "domain": preset["domain"],
            "fields": list(preset["fields"]),
            "labels": dict(preset.get("labels", {})),
            "hint": preset.get("hint", ""),
        }
        for preset_id, preset in PRACTICE_PRESETS.items()
    ]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    return PRACTICE_PRESETS.get(preset_id)


def empty_practices() -> dict[str, Any]:
    return {"items": []}


def new_practice_id() -> str:
    return secrets.token_hex(6)


def _normalize_date(value: Any) -> str | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        return None


def _opt_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_quality(value: Any) -> int | None:
    quality = _opt_int(value)
    if quality is None:
        return None
    return max(1, min(10, quality))


def normalize_practices(stored: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stored, dict):
        return empty_practices()
    raw_items = stored.get("items")
    if not isinstance(raw_items, list):
        return empty_practices()
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        day = _normalize_date(raw.get("date"))
        if not name or day is None:
            continue
        items.append(
            {
                "id": str(raw.get("id") or "").strip() or new_practice_id(),
                "date": day,
                "name": name,
                "preset": str(raw.get("preset") or DEFAULT_PRESET).strip() or DEFAULT_PRESET,
                "duration_minutes": _opt_int(raw.get("duration_minutes")),
                "completions": _opt_int(raw.get("completions")),
                "sets": _opt_int(raw.get("sets")),
                "hold_seconds": _opt_float(raw.get("hold_seconds")),
                "per_side": bool(raw.get("per_side", False)),
                "quality": _clamp_quality(raw.get("quality")),
                "notes": str(raw.get("notes") or "").strip(),
                "domain": str(raw.get("domain") or "").strip(),
            }
        )
    return {"items": items}


def list_practices(practices: dict[str, Any]) -> list[dict[str, Any]]:
    return list(normalize_practices(practices).get("items") or [])


def items_for_day(practices: dict[str, Any], day: str) -> list[dict[str, Any]]:
    day_n = _normalize_date(day)
    if day_n is None:
        return []
    return [item for item in list_practices(practices) if item["date"] == day_n]


def add_practice(
    practices: dict[str, Any],
    *,
    name: str,
    date: str,
    preset: str = DEFAULT_PRESET,
    duration_minutes: Any = None,
    completions: Any = None,
    sets: Any = None,
    hold_seconds: Any = None,
    per_side: bool = False,
    quality: Any = None,
    notes: str = "",
    domain: str = "",
) -> dict[str, Any]:
    practices = normalize_practices(practices)
    cleaned = (name or "").strip()
    day = _normalize_date(date)
    if not cleaned or day is None:
        raise ValueError("Practice needs a name and a valid date (YYYY-MM-DD).")
    practices["items"].append(
        {
            "id": new_practice_id(),
            "date": day,
            "name": cleaned,
            "preset": (preset or DEFAULT_PRESET).strip() or DEFAULT_PRESET,
            "duration_minutes": _opt_int(duration_minutes),
            "completions": _opt_int(completions),
            "sets": _opt_int(sets),
            "hold_seconds": _opt_float(hold_seconds),
            "per_side": bool(per_side),
            "quality": _clamp_quality(quality),
            "notes": (notes or "").strip(),
            "domain": (domain or "").strip(),
        }
    )
    return practices


def remove_practice(practices: dict[str, Any], practice_id: str) -> dict[str, Any]:
    practices = normalize_practices(practices)
    practices["items"] = [i for i in practices["items"] if i["id"] != practice_id]
    return practices


def format_practice_summary(item: dict[str, Any]) -> str:
    """Compact one-line summary of the quantitative fields (no name/date)."""
    parts: list[str] = []
    if item.get("completions") is not None:
        parts.append(f"{item['completions']} completions")
    if item.get("sets") is not None:
        parts.append(f"{item['sets']} sets")
    if item.get("hold_seconds") is not None:
        side = "/side" if item.get("per_side") else ""
        parts.append(f"{item['hold_seconds']:g}s hold{side}")
    if item.get("duration_minutes") is not None:
        parts.append(f"{item['duration_minutes']} min")
    if item.get("quality") is not None:
        parts.append(f"quality {item['quality']}/10")
    return ", ".join(parts) if parts else "logged"


def format_practice_note(item: dict[str, Any], *, when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%H:%M")
    summary = format_practice_summary(item)
    line = f"[Practice {stamp}] {item['name']} — {summary}"
    if item.get("notes"):
        line = f"{line}\n{item['notes']}"
    return line


def merge_practice_line(
    entries: dict,
    *,
    date_str: str,
    domain: str,
    item: dict[str, Any],
    when: datetime | None = None,
) -> dict:
    """Append a practice summary into the linked domain's day notes.

    Creates the day/domain entry at a default rating if absent, so the practice counts for
    history, streaks, and AI context. Mutates and returns ``entries``.
    """
    if not domain:
        return entries
    day = entries.setdefault(date_str, {})
    existing = dict(day.get(domain) or {})
    line = format_practice_note(item, when=when)
    prev = (existing.get("notes") or "").strip()
    notes = f"{line}\n\n{prev}" if prev else line
    day[domain] = {
        "rating": existing.get("rating", 5),
        "checklist": dict(existing.get("checklist") or {}),
        "metrics": dict(existing.get("metrics") or {}),
        "notes": notes,
    }
    if existing.get("backdate_reason"):
        day[domain]["backdate_reason"] = existing["backdate_reason"]
    return entries
