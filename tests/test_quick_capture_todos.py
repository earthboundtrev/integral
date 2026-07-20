"""SPEC-315 todos helpers."""

from datetime import date

import todos
import quick_capture


def test_normalize_and_add():
    store = todos.empty_todos()
    store = todos.add_todo(store, text="Pay bill", work_date="2026-07-25", category="Money/Freedom")
    items = todos.list_items(store)
    assert len(items) == 1
    assert items[0]["text"] == "Pay bill"
    assert items[0]["work_date"] == "2026-07-25"
    assert items[0]["category"] == "Money/Freedom"
    assert items[0]["done"] is False


def test_today_vs_upcoming():
    store = todos.empty_todos()
    store = todos.add_todo(store, text="Today task", work_date="2026-07-20")
    store = todos.add_todo(store, text="Future", work_date="2026-07-28")
    store = todos.add_todo(store, text="Overdue", work_date="2026-07-18")
    today = todos.items_for_day(store, "2026-07-20")
    names = {i["text"] for i in today}
    assert "Today task" in names
    assert "Overdue" in names
    assert "Future" not in names
    upcoming = todos.upcoming_items(store, "2026-07-20")
    assert [i["text"] for i in upcoming] == ["Future"]


def test_toggle_and_remove():
    store = todos.add_todo(todos.empty_todos(), text="X", work_date="2026-07-20")
    tid = store["items"][0]["id"]
    store = todos.update_todo(store, tid, done=True)
    assert store["items"][0]["done"] is True
    store = todos.remove_todo(store, tid)
    assert store["items"] == []


def test_finish_merges_category_notes():
    entries = {
        "2026-07-20": {
            "Admin": {
                "rating": 6,
                "checklist": {},
                "metrics": {},
                "notes": "Earlier note",
            }
        }
    }
    quick_capture.merge_todo_done_line(
        entries,
        date_str="2026-07-20",
        category="Admin",
        text="File taxes",
        when=__import__("datetime").datetime(2026, 7, 20, 15, 5),
    )
    notes = entries["2026-07-20"]["Admin"]["notes"]
    assert "[Todo done 15:05] File taxes" in notes
    assert "Earlier note" in notes
    assert entries["2026-07-20"]["Admin"]["rating"] == 6
