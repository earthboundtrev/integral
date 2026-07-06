from history import format_recent_activity, list_recent_entries


def test_list_recent_entries_empty():
    assert list_recent_entries({}) == []


def test_list_recent_entries_newest_first():
    entries = {
        "2026-07-01": {"Money/Freedom": {"rating": 5, "notes": "old"}},
        "2026-07-05": {
            "Body & Presence": {"rating": 8, "notes": "workout"},
            "Money/Freedom": {"rating": 7, "notes": ""},
        },
    }
    recent = list_recent_entries(entries, limit=10)
    assert recent[0]["date"] == "2026-07-05"
    assert recent[0]["category"] == "Body & Presence"
    assert recent[0]["rating"] == 8
    assert recent[0]["notes_preview"] == "workout"
    assert recent[1]["category"] == "Money/Freedom"
    assert recent[2]["date"] == "2026-07-01"


def test_list_recent_entries_respects_limit():
    entries = {
        f"2026-07-{day:02d}": {"Money/Freedom": {"rating": day, "notes": ""}}
        for day in range(1, 11)
    }
    assert len(list_recent_entries(entries, limit=3)) == 3


def test_format_recent_activity_empty():
    text = format_recent_activity({})
    assert "No activity yet" in text


def test_format_recent_activity_shows_rating_and_notes():
    entries = {
        "2026-07-05": {
            "Body & Presence": {"rating": 8, "notes": "Good session today"},
        }
    }
    text = format_recent_activity(entries)
    assert "Jul 05, 2026" in text
    assert "Body & Presence" in text
    assert "8/10" in text
    assert "Good session today" in text
