"""Quarterly milestone tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def current_quarter_label(when: datetime | None = None) -> tuple[int, int, str]:
    when = when or datetime.now()
    quarter = ((when.month - 1) // 3) + 1
    return when.year, quarter, f"Q{quarter} {when.year}"


def _clamp_progress(value: Any) -> int:
    try:
        progress = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, progress))


def normalize_milestone(item: dict[str, Any]) -> dict[str, Any]:
    """Ensure a milestone has all keys, backfilling defaults for older data."""
    year, quarter, _label = current_quarter_label()
    raw = item if isinstance(item, dict) else {}
    status = str(raw.get("status") or "open")
    progress = _clamp_progress(raw.get("progress", 0))
    if status == "done":
        progress = 100
    return {
        "year": raw.get("year", year),
        "quarter": raw.get("quarter", quarter),
        "title": str(raw.get("title") or "Untitled"),
        "status": status,
        "notes": str(raw.get("notes") or ""),
        "completed_date": str(raw.get("completed_date") or ""),
        "domain": str(raw.get("domain") or ""),
        "progress": progress,
    }


def default_milestones() -> list[dict[str, Any]]:
    year, quarter, label = current_quarter_label()
    return [
        normalize_milestone(
            {
                "year": year,
                "quarter": quarter,
                "title": f"{label} — define your top 3 priorities",
                "status": "open",
                "notes": "",
                "completed_date": "",
            }
        )
    ]


def merge_milestones(stored: list[dict] | None) -> list[dict]:
    if not stored:
        return default_milestones()
    return [normalize_milestone(item) for item in stored if isinstance(item, dict)]


def milestone_summary(milestones: list[dict]) -> str:
    if not milestones:
        return "No quarterly milestones yet."
    done = sum(1 for item in milestones if item.get("status") == "done")
    avg = round(sum(_clamp_progress(item.get("progress", 0)) for item in milestones) / len(milestones))
    return f"Milestones: {done}/{len(milestones)} complete (avg progress {avg}%)"
