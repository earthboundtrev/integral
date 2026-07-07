"""Plan upcoming days and compare intentions with what actually happened."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def empty_day_plans() -> dict[str, dict[str, Any]]:
    return {}


def normalize_day_plans(stored: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(stored, dict):
        return empty_day_plans()

    plans: dict[str, dict[str, Any]] = {}
    for plan_date, raw in stored.items():
        if not isinstance(raw, dict):
            continue
        parsed = parse_plan_date(str(plan_date))
        if parsed is None:
            continue
        day_intention = str(raw.get("day_intention") or "").strip()
        fitness_note = str(raw.get("fitness_note") or "").strip()
        categories = _normalize_category_plans(raw.get("categories"))
        if not day_intention and not fitness_note and not categories:
            continue
        plans[parsed.isoformat()] = {
            "planned_for": parsed.isoformat(),
            "created_on": str(raw.get("created_on") or "").strip() or None,
            "updated_at": str(raw.get("updated_at") or datetime.now().isoformat(timespec="seconds")),
            "day_intention": day_intention,
            "fitness_note": fitness_note,
            "categories": categories,
        }
    return plans


def _normalize_category_plans(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    categories: dict[str, dict[str, Any]] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        notes = str(item.get("notes") or "").strip()
        checklist = item.get("checklist") if isinstance(item.get("checklist"), dict) else {}
        checklist = {str(key): bool(value) for key, value in checklist.items()}
        rating = item.get("rating")
        if rating is not None:
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                rating = None
        if not notes and not checklist and rating is None:
            continue
        categories[str(name)] = {
            "notes": notes,
            "rating": rating,
            "checklist": checklist,
        }
    return categories


def parse_plan_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def tomorrow_from(today: date | None = None) -> date:
    today = today or datetime.now().date()
    return today + timedelta(days=1)


def plan_for_date(plans: dict[str, dict[str, Any]], plan_date: str | date) -> dict[str, Any] | None:
    if isinstance(plan_date, date):
        key = plan_date.isoformat()
    else:
        parsed = parse_plan_date(plan_date)
        if parsed is None:
            return None
        key = parsed.isoformat()
    plan = plans.get(key)
    return dict(plan) if plan else None


def upsert_plan(
    plans: dict[str, dict[str, Any]],
    planned_for: str,
    *,
    day_intention: str = "",
    fitness_note: str = "",
    categories: dict[str, dict[str, Any]] | None = None,
    created_on: str | None = None,
) -> dict[str, dict[str, Any]]:
    parsed = parse_plan_date(planned_for)
    if parsed is None:
        raise ValueError("Use a valid plan date (YYYY-MM-DD).")
    if parsed < datetime.now().date():
        raise ValueError("Plans are for today or future days only.")

    key = parsed.isoformat()
    existing = plans.get(key) or {}
    updated = {
        "planned_for": key,
        "created_on": existing.get("created_on") or created_on or datetime.now().date().isoformat(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "day_intention": day_intention.strip(),
        "fitness_note": fitness_note.strip(),
        "categories": categories if categories is not None else dict(existing.get("categories") or {}),
    }
    if not updated["day_intention"] and not updated["fitness_note"] and not updated["categories"]:
        plans.pop(key, None)
        return plans
    plans[key] = updated
    return plans


def compare_plan_to_actual(
    plan: dict[str, Any] | None,
    actual_entries: dict[str, Any] | None,
    *,
    all_categories: list[str] | None = None,
) -> dict[str, Any]:
    """Compare a saved plan with what was actually logged that day."""
    actual_entries = actual_entries or {}
    if not plan:
        return {
            "has_plan": False,
            "summary": "No plan was saved for this day.",
            "categories": [],
            "stats": {"planned": 0, "logged": 0, "aligned": 0, "partial": 0, "missed": 0},
        }

    planned_categories = plan.get("categories") or {}
    category_names = list(all_categories or [])
    for name in planned_categories:
        if name not in category_names:
            category_names.append(name)

    rows: list[dict[str, Any]] = []
    stats = {"planned": 0, "logged": 0, "aligned": 0, "partial": 0, "missed": 0}

    for name in category_names:
        planned = planned_categories.get(name)
        actual = actual_entries.get(name)
        if not planned and not actual:
            continue
        if planned:
            stats["planned"] += 1
        if actual:
            stats["logged"] += 1
        status = _category_comparison_status(planned, actual)
        if status == "aligned":
            stats["aligned"] += 1
        elif status == "partial":
            stats["partial"] += 1
        elif status in {"missed", "not_logged"}:
            stats["missed"] += 1
        rows.append(
            {
                "category": name,
                "status": status,
                "planned": planned,
                "actual": actual,
            }
        )

    summary = _build_summary(plan, rows, stats)
    return {
        "has_plan": True,
        "summary": summary,
        "day_intention": plan.get("day_intention", ""),
        "fitness_note": plan.get("fitness_note", ""),
        "categories": rows,
        "stats": stats,
    }


def _category_comparison_status(planned: dict[str, Any] | None, actual: dict[str, Any] | None) -> str:
    if not planned:
        return "unplanned"
    if not actual:
        return "not_logged"
    score = 0
    checks = 0

    planned_rating = planned.get("rating")
    actual_rating = actual.get("rating")
    if planned_rating is not None:
        checks += 1
        if actual_rating is not None and int(actual_rating) >= int(planned_rating):
            score += 1

    planned_checklist = planned.get("checklist") or {}
    actual_checklist = actual.get("checklist") or {}
    if planned_checklist:
        checks += 1
        if all(actual_checklist.get(item) for item in planned_checklist):
            score += 1

    planned_notes = str(planned.get("notes") or "").strip()
    actual_notes = str(actual.get("notes") or "").strip()
    if planned_notes:
        checks += 1
        if actual_notes:
            score += 1

    if checks == 0:
        return "aligned" if actual else "not_logged"
    if score == checks:
        return "aligned"
    if score > 0:
        return "partial"
    return "missed"


def _build_summary(plan: dict[str, Any], rows: list[dict[str, Any]], stats: dict[str, int]) -> str:
    if not rows and not plan.get("day_intention") and not plan.get("fitness_note"):
        return "Plan saved, but no category intentions were listed."
    if stats["planned"] == 0:
        return "You set a day intention — review how the day went against that."
    if stats["logged"] == 0:
        return "Nothing logged yet for the areas you planned."
    if stats["aligned"] == stats["planned"]:
        return "You followed through on everything you planned."
    if stats["aligned"] + stats["partial"] > 0:
        return (
            f"{stats['aligned']} area(s) fully matched your plan, "
            f"{stats['partial']} partial, {stats['missed']} missed or not logged."
        )
    return "The day diverged from what you planned — worth a honest look."


def format_category_status(status: str) -> str:
    labels = {
        "aligned": "Matched plan",
        "partial": "Partially matched",
        "missed": "Missed plan",
        "not_logged": "Not logged",
        "unplanned": "Logged (unplanned)",
    }
    return labels.get(status, status.replace("_", " ").title())
