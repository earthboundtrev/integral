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


def test_strong_medicine_preset_has_movements():
    preset = practices.get_preset("strong_medicine")
    assert preset is not None
    assert "King Squat" in preset["movements"]
    assert practices.FIELD_EFFECT in preset["fields"]
    rites = practices.get_preset("tibetan_rites")
    assert len(rites["movements"]) == 5


def test_add_practice_with_movements_and_effect():
    store = practices.add_practice(
        practices.empty_practices(),
        name="Five Tibetan Rites",
        date="2026-07-21",
        preset="tibetan_rites",
        effect="Big energy boost, less sleepiness",
        movements=[
            {"name": "Rite 1 — Spin", "reps": 9},
            {"name": "Rite 2 — Leg Raise", "reps": 9},
            {"name": "Rite 3 — Camel", "reps": ""},  # blank dropped
        ],
        domain="Physical Practices & Movement",
    )
    item = practices.list_practices(store)[0]
    assert item["effect"] == "Big energy boost, less sleepiness"
    # Blank movement (no reps/hold/quality) is dropped.
    assert len(item["movements"]) == 2
    assert item["movements"][0] == {
        "name": "Rite 1 — Spin",
        "reps": 9,
        "hold_seconds": None,
        "quality": None,
    }


def test_movement_breakdown_and_note_include_effect():
    item = {
        "name": "Five Tibetan Rites",
        "duration_minutes": 12,
        "effect": "Reduced sleepiness",
        "movements": [
            {"name": "Rite 1 — Spin", "reps": 9, "hold_seconds": None, "quality": None},
            {"name": "Rite 2 — Leg Raise", "reps": 9, "hold_seconds": None, "quality": None},
        ],
        "notes": "",
    }
    breakdown = practices.format_movement_breakdown(item)
    assert "Rite 1 — Spin: 9 reps" in breakdown
    note = practices.format_practice_note(item, when=__import__("datetime").datetime(2026, 7, 21, 8, 0))
    assert "Per movement:" in note
    assert "Effect: Reduced sleepiness" in note


def test_merge_practice_line_includes_effect_and_movements():
    entries: dict = {}
    store = practices.add_practice(
        practices.empty_practices(),
        name="Strong Medicine session",
        date="2026-07-21",
        preset="strong_medicine",
        effect="Felt strong",
        movements=[{"name": "King Squat", "reps": 8}],
        domain="Physical Practices & Movement",
    )
    item = practices.list_practices(store)[0]
    practices.merge_practice_line(
        entries, date_str="2026-07-21", domain="Physical Practices & Movement", item=item
    )
    notes = entries["2026-07-21"]["Physical Practices & Movement"]["notes"]
    assert "King Squat: 8 reps" in notes
    assert "Effect: Felt strong" in notes


def test_normalize_drops_bad_rows():
    store = practices.normalize_practices(
        {"items": [{"name": "", "date": "2026-07-21"}, {"name": "Ok", "date": "bad"}, 42]}
    )
    assert store == {"items": []}
