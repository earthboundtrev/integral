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


def test_move_todo_reorders_within_section():
    store = todos.empty_todos()
    store = todos.add_todo(store, text="A", work_date="2026-07-20")
    store = todos.add_todo(store, text="B", work_date="2026-07-20")
    store = todos.add_todo(store, text="C", work_date="2026-07-20")
    today = todos.items_for_day(store, "2026-07-20")
    assert [i["text"] for i in today] == ["A", "B", "C"]
    ids = [i["id"] for i in today]
    # Move C up one → A, C, B
    store = todos.move_todo(store, ids[2], ids, -1)
    order = [i["text"] for i in todos.items_for_day(store, "2026-07-20")]
    assert order == ["A", "C", "B"]
    # Move A down one → C, A, B
    order_ids = [i["id"] for i in todos.items_for_day(store, "2026-07-20")]
    store = todos.move_todo(store, order_ids[1], order_ids, -1)
    assert [i["text"] for i in todos.items_for_day(store, "2026-07-20")] == ["C", "A", "B"]


def test_move_todo_noop_off_ends():
    store = todos.add_todo(todos.empty_todos(), text="Only", work_date="2026-07-20")
    ids = [i["id"] for i in todos.list_items(store)]
    before = list(todos.list_items(store))
    store = todos.move_todo(store, ids[0], ids, -1)
    store = todos.move_todo(store, ids[0], ids, 1)
    assert todos.list_items(store) == before


def test_edit_updates_text_date_category():
    store = todos.add_todo(todos.empty_todos(), text="Old", work_date="2026-07-20")
    tid = store["items"][0]["id"]
    store = todos.update_todo(
        store, tid, text="New", work_date="2026-07-25", category="Money/Freedom"
    )
    item = todos.get_todo(store, tid)
    assert item["text"] == "New"
    assert item["work_date"] == "2026-07-25"
    assert item["category"] == "Money/Freedom"


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
