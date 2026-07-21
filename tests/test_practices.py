"""SPEC-318 daily practice logging."""

from datetime import datetime

import practices


def test_presets_include_core_routines():
    ids = {p["id"] for p in practices.list_presets()}
    assert {"tibetan_rites", "pavanamuktasana", "diaphragmatic_breathing", "generic"} <= ids
    rites = practices.get_preset("tibetan_rites")
    assert rites["domain"] == "Physical Practices & Movement"
    assert practices.FIELD_COMPLETIONS in rites["fields"]


def test_add_and_normalize():
    store = practices.empty_practices()
    store = practices.add_practice(
        store,
        name="Five Tibetan Rites",
        date="2026-07-21",
        preset="tibetan_rites",
        completions=9,
        duration_minutes=12,
        quality=8,
        notes="Felt strong energy after",
        domain="Physical Practices & Movement",
    )
    items = practices.list_practices(store)
    assert len(items) == 1
    item = items[0]
    assert item["completions"] == 9
    assert item["duration_minutes"] == 12
    assert item["quality"] == 8
    assert item["notes"] == "Felt strong energy after"


def test_quality_clamped_and_optional_fields_blank():
    store = practices.add_practice(
        practices.empty_practices(),
        name="Breathing",
        date="2026-07-21",
        quality=99,
        duration_minutes="",
    )
    item = practices.list_practices(store)[0]
    assert item["quality"] == 10
    assert item["duration_minutes"] is None


def test_add_requires_name_and_date():
    for bad in [{"name": "", "date": "2026-07-21"}, {"name": "X", "date": "nope"}]:
        try:
            practices.add_practice(practices.empty_practices(), **bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_items_for_day_and_remove():
    store = practices.add_practice(practices.empty_practices(), name="A", date="2026-07-21")
    store = practices.add_practice(store, name="B", date="2026-07-22")
    assert len(practices.items_for_day(store, "2026-07-21")) == 1
    pid = practices.list_practices(store)[0]["id"]
    store = practices.remove_practice(store, pid)
    assert len(practices.list_practices(store)) == 1


def test_format_summary_and_per_side():
    item = {
        "name": "Pavanamuktasana",
        "hold_seconds": 30,
        "per_side": True,
        "duration_minutes": 5,
        "quality": 7,
    }
    summary = practices.format_practice_summary(item)
    assert "30s hold/side" in summary
    assert "5 min" in summary
    assert "quality 7/10" in summary


def test_merge_practice_line_creates_and_prepends():
    entries: dict = {}
    item = {
        "name": "Diaphragmatic breathing",
        "duration_minutes": 10,
        "quality": 6,
        "notes": "Calmer",
    }
    practices.merge_practice_line(
        entries,
        date_str="2026-07-21",
        domain="Breathwork & Mindfulness",
        item=item,
        when=datetime(2026, 7, 21, 8, 5),
    )
    entry = entries["2026-07-21"]["Breathwork & Mindfulness"]
    assert entry["rating"] == 5  # default so it counts for streaks/history
    assert "[Practice 08:05] Diaphragmatic breathing" in entry["notes"]
    assert "Calmer" in entry["notes"]


def test_normalize_drops_bad_rows():
    store = practices.normalize_practices(
        {"items": [{"name": "", "date": "2026-07-21"}, {"name": "Ok", "date": "bad"}, 42]}
    )
    assert store == {"items": []}
