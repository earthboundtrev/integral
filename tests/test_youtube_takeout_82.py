"""Tests for YouTube Takeout import (#82 / SPEC-328)."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path

import youtube_takeout
from integral_io import export_youtube_history_csv, load_backup, restore_backup_to_path, write_backup

FIXTURE = Path(__file__).parent / "fixtures" / "youtube_watch_history_sample.json"


def test_parse_takeout_fixture_keeps_watches_skips_search():
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events, unparsed = youtube_takeout.parse_takeout_records(records)
    titles = {e["title"] for e in events}
    assert "Integral intro talk" in titles
    assert "Calm morning playlist" in titles
    assert "Duplicate video" in titles
    assert all("cats" not in e["title"].lower() for e in events)
    assert unparsed >= 1
    music = [e for e in events if e["source"] == "youtube_music"]
    assert len(music) == 1
    assert music[0]["channel"] == "Music Channel"


def test_load_events_from_json_and_zip(tmp_path: Path):
    json_path = tmp_path / "watch-history.json"
    json_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    events_json, _ = youtube_takeout.load_events_from_path(str(json_path))
    assert len(events_json) >= 3

    zip_path = tmp_path / "takeout.zip"
    inner = "Takeout/YouTube and YouTube Music/history/watch-history.json"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(inner, FIXTURE.read_bytes())
    events_zip, _ = youtube_takeout.load_events_from_path(str(zip_path))
    assert len(events_zip) == len(events_json)


def test_merge_dedupe_reports_added_and_skipped():
    events, unparsed = youtube_takeout.parse_takeout_records(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    store, stats = youtube_takeout.merge_events(None, events, unparsed=unparsed)
    assert stats["added"] == len(events)
    assert stats["skipped"] == 0
    store2, stats2 = youtube_takeout.merge_events(store, events, unparsed=0)
    assert stats2["added"] == 0
    assert stats2["skipped"] == len(events)
    assert len(store2["events"]) == len(events)


def test_rollup_appends_notes_without_ratings():
    events, _ = youtube_takeout.parse_takeout_records(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    store, _ = youtube_takeout.merge_events(None, events)
    entries = {
        "2024-06-01": {
            youtube_takeout.CONTENT_CATEGORY: {
                "rating": 7,
                "checklist": {"Articles, essays, or newsletters": True},
                "metrics": {},
                "notes": "already here",
            },
            youtube_takeout.ART_CATEGORY: {
                "rating": 6,
                "checklist": {},
                "metrics": {},
                "notes": "",
            },
        }
    }
    before_rating = entries["2024-06-01"][youtube_takeout.CONTENT_CATEGORY]["rating"]
    before_check = dict(entries["2024-06-01"][youtube_takeout.CONTENT_CATEGORY]["checklist"])
    before_art_rating = entries["2024-06-01"][youtube_takeout.ART_CATEGORY]["rating"]

    updated = youtube_takeout.apply_day_note_rollup(entries, store)
    content = updated["2024-06-01"][youtube_takeout.CONTENT_CATEGORY]
    assert content["rating"] == before_rating
    assert content["checklist"] == before_check
    assert "[YouTube Takeout 2024-06-01]" in content["notes"]
    assert "already here" in content["notes"]

    art = updated["2024-06-01"][youtube_takeout.ART_CATEGORY]
    assert art["rating"] == before_art_rating
    assert "[YouTube Takeout 2024-06-01]" in art.get("notes", "")

    again = youtube_takeout.apply_day_note_rollup(updated, store)
    assert again["2024-06-01"][youtube_takeout.CONTENT_CATEGORY]["notes"].count(
        "[YouTube Takeout 2024-06-01]"
    ) == 1


def test_rollup_does_not_create_notes_only_day_entries():
    events, _ = youtube_takeout.parse_takeout_records(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    store, _ = youtube_takeout.merge_events(None, events)
    updated = youtube_takeout.apply_day_note_rollup({}, store)
    assert updated == {}


def test_incremental_rollup_updates_day_total_not_duplicate_lines():
    first = [
        {
            "header": "YouTube",
            "title": "Watched One",
            "titleUrl": "https://www.youtube.com/watch?v=one",
            "time": "2024-06-01T15:00:00.000Z",
        }
    ]
    second = [
        {
            "header": "YouTube",
            "title": "Watched Two",
            "titleUrl": "https://www.youtube.com/watch?v=two",
            "time": "2024-06-01T16:00:00.000Z",
        }
    ]
    e1, _ = youtube_takeout.parse_takeout_records(first)
    store, _ = youtube_takeout.merge_events(None, e1)
    seeded = {
        "2024-06-01": {
            youtube_takeout.CONTENT_CATEGORY: {
                "rating": 5,
                "checklist": {},
                "metrics": {},
                "notes": "",
            }
        }
    }
    entries = youtube_takeout.apply_day_note_rollup(seeded, store, only_event_ids={e1[0]["id"]})
    assert "1 watch" in entries["2024-06-01"][youtube_takeout.CONTENT_CATEGORY]["notes"]

    e2, _ = youtube_takeout.parse_takeout_records(second)
    store2, _ = youtube_takeout.merge_events(store, e2)
    entries2 = youtube_takeout.apply_day_note_rollup(
        entries, store2, only_event_ids={e2[0]["id"]}
    )
    notes = entries2["2024-06-01"][youtube_takeout.CONTENT_CATEGORY]["notes"]
    assert notes.count("[YouTube Takeout 2024-06-01]") == 1
    assert "2 watches" in notes


def test_local_day_converts_utc_evening_to_local_calendar():
    # 2024-06-01T03:00Z is still 2024-05-31 evening in US Eastern (UTC-4 in June).
    day = youtube_takeout._local_day("2024-06-01T03:00:00.000Z")
    assert len(day) == 10
    # Must not blindly use the UTC date prefix when offset would change the day.
    # On UTC+0 hosts this equals 2024-06-01; on western zones it may be 2024-05-31.
    from datetime import datetime, timezone

    expected = (
        datetime.fromisoformat("2024-06-01T03:00:00+00:00").astimezone().date().isoformat()
    )
    assert day == expected


def test_rollup_skipped_when_no_new_flag_path():
    """Import without rollup must not mutate entries (caller responsibility); helper no-op on empty ids."""
    events, _ = youtube_takeout.parse_takeout_records(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    store, _ = youtube_takeout.merge_events(None, events)
    entries = {"2024-06-01": {}}
    unchanged = youtube_takeout.apply_day_note_rollup(entries, store, only_event_ids=set())
    assert unchanged == entries


def test_export_youtube_csv_and_backup_roundtrip(tmp_path: Path):
    events, _ = youtube_takeout.parse_takeout_records(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    store, _ = youtube_takeout.merge_events(None, events)
    csv_path = tmp_path / "yt.csv"
    rows = export_youtube_history_csv(store, str(csv_path))
    assert rows == len(events)
    text = csv_path.read_text(encoding="utf-8")
    assert "Integral intro talk" in text

    payload = {"schema_version": 2, "entries": {}, "youtube_history": store}
    backup_path = tmp_path / "backup.json"
    write_backup(payload, str(backup_path))
    restored_path = tmp_path / "data.json"
    restore_backup_to_path(load_backup(str(backup_path)), str(restored_path), make_copy=False)
    loaded = json.loads(restored_path.read_text(encoding="utf-8"))
    assert len(loaded["youtube_history"]["events"]) == len(events)


def test_youtube_takeout_module_has_no_network_imports():
    import ast

    source = Path(youtube_takeout.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    forbidden = {"urllib", "requests", "http", "httpx", "aiohttp", "socket"}
    assert names.isdisjoint(forbidden)
