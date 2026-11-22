"""Repeat-session listing and display helpers (#259)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fitness_programs import format_family_label
from progression.db import FitnessRepository, WorkoutSession


def format_date_display(iso_date: str) -> str:
    """Format ISO date as 'Tue Oct 14' (same as workout history)."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%a %b %d")
    except (ValueError, AttributeError):
        return iso_date


def dominant_family_label(family_counts: dict[str, int]) -> str:
    """Most common exercise family in a session, or Mixed on a tie at the top."""
    if not family_counts:
        return "Workout"
    max_cnt = max(family_counts.values())
    leaders = [fam for fam, cnt in family_counts.items() if cnt == max_cnt]
    if len(leaders) > 1:
        return "Mixed"
    return format_family_label(leaders[0])


@dataclass(frozen=True)
class RepeatableSessionRow:
    session_id: str
    date: str
    created_at: str | None
    exercise_count: int
    type_label: str


def format_repeat_queued_note(
    item_count: int,
    session: WorkoutSession,
    type_label: str,
) -> str:
    date_part = format_date_display(session.date)
    return f"Queued {item_count} sets from {date_part} ({type_label})"


def session_type_label_for_id(repo: FitnessRepository, session_id: str) -> str:
    summary_fn = getattr(repo, "summarize_session_families", None)
    if callable(summary_fn):
        counts = summary_fn(session_id)
        return dominant_family_label(counts)
    return "Workout"


def format_repeatable_row_text(row: RepeatableSessionRow) -> str:
    date_part = format_date_display(row.date)
    return f"{date_part} · {row.type_label} · {row.exercise_count} exercises"


def list_repeatable_session_rows(
    repo: FitnessRepository,
    *,
    exclude_date: str | None = None,
    limit: int = 10,
) -> list[RepeatableSessionRow]:
    list_fn = getattr(repo, "list_repeatable_session_rows", None)
    if not callable(list_fn):
        return []
    raw = list_fn(exclude_date=exclude_date, limit=limit)
    rows: list[RepeatableSessionRow] = []
    for entry in raw:
        type_label = dominant_family_label(entry.get("family_counts") or {})
        rows.append(
            RepeatableSessionRow(
                session_id=entry["session_id"],
                date=entry["date"],
                created_at=entry.get("created_at"),
                exercise_count=int(entry.get("exercise_count") or 0),
                type_label=type_label,
            )
        )
    return rows