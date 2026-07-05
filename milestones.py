"""Quarterly milestone tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def current_quarter_label(when: datetime | None = None) -> tuple[int, int, str]:
    when = when or datetime.now()
    quarter = ((when.month - 1) // 3) + 1
    return when.year, quarter, f"Q{quarter} {when.year}"


def default_milestones() -> list[dict[str, Any]]:
    year, quarter, label = current_quarter_label()
    return [
        {
            "year": year,
            "quarter": quarter,
            "title": f"{label} — define your top 3 priorities",
            "status": "open",
            "notes": "",
            "completed_date": "",
        }
    ]


def merge_milestones(stored: list[dict] | None) -> list[dict]:
    if not stored:
        return default_milestones()
    return list(stored)


def milestone_summary(milestones: list[dict]) -> str:
    if not milestones:
        return "No quarterly milestones yet."
    done = sum(1 for item in milestones if item.get("status") == "done")
    return f"Milestones: {done}/{len(milestones)} complete"
