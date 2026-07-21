"""Capture todos — day list + scheduled backlog (SPEC-315)."""

from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any


def empty_todos() -> dict[str, Any]:
    return {"items": []}


def new_todo_id() -> str:
    return secrets.token_hex(6)


def normalize_todos(stored: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stored, dict):
        return empty_todos()
    raw_items = stored.get("items")
    if not isinstance(raw_items, list):
        return empty_todos()
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        work_date = _normalize_date(raw.get("work_date"))
        if not text or work_date is None:
            continue
        category = str(raw.get("category") or "").strip()
        item_id = str(raw.get("id") or "").strip() or new_todo_id()
        items.append(
            {
                "id": item_id,
                "text": text,
                "done": bool(raw.get("done", False)),
                "work_date": work_date,
                "category": category,
            }
        )
    return {"items": items}


def _normalize_date(value: Any) -> str | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        return None


def list_items(todos: dict[str, Any]) -> list[dict[str, Any]]:
    return list(normalize_todos(todos).get("items") or [])


def items_for_day(todos: dict[str, Any], day: str) -> list[dict[str, Any]]:
    """Today's list: work_date == day (including overdue incomplete from earlier days)."""
    day_n = _normalize_date(day)
    if day_n is None:
        return []
    today = datetime.strptime(day_n, "%Y-%m-%d").date()
    result: list[dict[str, Any]] = []
    for item in list_items(todos):
        work = datetime.strptime(item["work_date"], "%Y-%m-%d").date()
        if work == today:
            result.append(item)
        elif work < today and not item["done"]:
            # Overdue incomplete still on Today
            result.append(item)
    # Preserve stored (manual) order; only sink finished items to the bottom.
    result.sort(key=lambda i: i["done"])
    return result


def upcoming_items(todos: dict[str, Any], today: str) -> list[dict[str, Any]]:
    today_n = _normalize_date(today)
    if today_n is None:
        return []
    today_d = datetime.strptime(today_n, "%Y-%m-%d").date()
    result = []
    for item in list_items(todos):
        if item["done"]:
            continue
        work = datetime.strptime(item["work_date"], "%Y-%m-%d").date()
        if work > today_d:
            result.append(item)
    # Preserve stored (manual) order so ↑/↓ reordering is reflected.
    return result


def add_todo(
    todos: dict[str, Any],
    *,
    text: str,
    work_date: str,
    category: str = "",
    done: bool = False,
) -> dict[str, Any]:
    todos = normalize_todos(todos)
    cleaned = text.strip()
    day = _normalize_date(work_date)
    if not cleaned or day is None:
        raise ValueError("Todo needs text and a valid work date (YYYY-MM-DD).")
    todos["items"].append(
        {
            "id": new_todo_id(),
            "text": cleaned,
            "done": bool(done),
            "work_date": day,
            "category": (category or "").strip(),
        }
    )
    return todos


def update_todo(todos: dict[str, Any], todo_id: str, **fields: Any) -> dict[str, Any]:
    todos = normalize_todos(todos)
    for item in todos["items"]:
        if item["id"] != todo_id:
            continue
        if "text" in fields:
            text = str(fields["text"] or "").strip()
            if not text:
                raise ValueError("Todo text cannot be empty.")
            item["text"] = text
        if "work_date" in fields:
            day = _normalize_date(fields["work_date"])
            if day is None:
                raise ValueError("Invalid work date.")
            item["work_date"] = day
        if "category" in fields:
            item["category"] = str(fields["category"] or "").strip()
        if "done" in fields:
            item["done"] = bool(fields["done"])
        return todos
    raise KeyError(f"Todo not found: {todo_id}")


def remove_todo(todos: dict[str, Any], todo_id: str) -> dict[str, Any]:
    todos = normalize_todos(todos)
    todos["items"] = [i for i in todos["items"] if i["id"] != todo_id]
    return todos


def get_todo(todos: dict[str, Any], todo_id: str) -> dict[str, Any] | None:
    for item in list_items(todos):
        if item["id"] == todo_id:
            return item
    return None


def move_todo(
    todos: dict[str, Any],
    todo_id: str,
    sibling_ids: list[str],
    delta: int,
) -> dict[str, Any]:
    """Swap ``todo_id`` with its neighbour in the visible section order.

    ``sibling_ids`` is the ordered list of ids currently shown in that section;
    ``delta`` is -1 (up) or +1 (down). Reorders the underlying ``items`` list so
    the new order persists. No-op when the move would fall off either end.
    """
    todos = normalize_todos(todos)
    ids = list(sibling_ids or [])
    if todo_id not in ids:
        return todos
    pos = ids.index(todo_id)
    target = pos + delta
    if target < 0 or target >= len(ids):
        return todos
    swap_id = ids[target]
    items = todos["items"]
    index_by_id = {item["id"]: idx for idx, item in enumerate(items)}
    if todo_id not in index_by_id or swap_id not in index_by_id:
        return todos
    a, b = index_by_id[todo_id], index_by_id[swap_id]
    items[a], items[b] = items[b], items[a]
    return todos
