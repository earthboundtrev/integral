"""Parse and merge Google Takeout YouTube watch history (local-only, no network)."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Any

CONTENT_CATEGORY = "Content You Have Consumed"
ART_CATEGORY = "Art You Have Consumed"
WATCH_HISTORY_NAMES = ("watch-history.json", "watch-history.html")


def empty_youtube_history() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "events": [],
        "last_import_at": "",
        "last_import_stats": {"added": 0, "skipped": 0, "unparsed": 0},
    }


def normalize_youtube_history(stored: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_youtube_history()
    if not isinstance(stored, dict):
        return base
    events: list[dict[str, Any]] = []
    raw_events = stored.get("events")
    if isinstance(raw_events, list):
        for item in raw_events:
            event = _normalize_event(item)
            if event is not None:
                events.append(event)
    stats = stored.get("last_import_stats")
    if not isinstance(stats, dict):
        stats = base["last_import_stats"]
    return {
        "schema_version": int(stored.get("schema_version") or 1),
        "events": events,
        "last_import_at": str(stored.get("last_import_at") or ""),
        "last_import_stats": {
            "added": int(stats.get("added") or 0),
            "skipped": int(stats.get("skipped") or 0),
            "unparsed": int(stats.get("unparsed") or 0),
        },
    }


def event_id(url: str, watched_at: str) -> str:
    digest = hashlib.sha1(f"{url.strip()}|{watched_at.strip()}".encode("utf-8")).hexdigest()
    return digest


def classify_source(header: str | None) -> str:
    text = (header or "").strip().lower()
    if "youtube music" in text:
        return "youtube_music"
    if "youtube" in text:
        return "youtube"
    return "other"


def _channel_from_subtitles(subtitles: Any) -> str:
    if not isinstance(subtitles, list):
        return ""
    for item in subtitles:
        if isinstance(item, dict) and item.get("name"):
            return str(item["name"]).strip()
    return ""


def _looks_like_watch_url(url: str) -> bool:
    lower = (url or "").lower()
    if "youtu.be/" in lower:
        return True
    if "youtube.com/watch?" in lower or "youtube.com/watch/" in lower:
        return True
    if "youtube.com/shorts/" in lower:
        return True
    return False


def _normalize_event(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    url = str(raw.get("url") or raw.get("titleUrl") or "").strip()
    watched_at = str(raw.get("watched_at") or raw.get("time") or "").strip()
    if not url or not watched_at:
        return None
    if not _looks_like_watch_url(url):
        return None
    source = str(raw.get("source") or "").strip()
    if source not in {"youtube", "youtube_music", "other"}:
        source = classify_source(str(raw.get("header") or ""))
    channel = str(raw.get("channel") or "").strip() or _channel_from_subtitles(raw.get("subtitles"))
    if title.lower().startswith("watched "):
        title = title[8:].strip()
    return {
        "id": str(raw.get("id") or event_id(url, watched_at)),
        "watched_at": watched_at,
        "title": title or "(untitled)",
        "url": url,
        "channel": channel,
        "source": source,
    }


def parse_takeout_records(records: list[Any]) -> tuple[list[dict[str, Any]], int]:
    """Return (events, unparsed_count) from raw Takeout JSON list."""
    events: list[dict[str, Any]] = []
    unparsed = 0
    for item in records:
        if not isinstance(item, dict):
            unparsed += 1
            continue
        title = str(item.get("title") or "")
        header = str(item.get("header") or "")
        is_music = "youtube music" in header.lower()
        url = str(item.get("titleUrl") or item.get("url") or "")
        if not is_music and title and not title.lower().startswith("watched"):
            if not _looks_like_watch_url(url):
                unparsed += 1
                continue
        event = _normalize_event(item)
        if event is None:
            unparsed += 1
            continue
        events.append(event)
    return events, unparsed


def load_takeout_json_bytes(raw: bytes) -> list[Any]:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("Takeout watch-history.json must be a JSON array.")
    return data


def find_watch_history_in_zip(zf: zipfile.ZipFile) -> str:
    candidates = [
        name
        for name in zf.namelist()
        if name.replace("\\", "/").lower().endswith("history/watch-history.json")
        or name.replace("\\", "/").lower().endswith("/watch-history.json")
        or os.path.basename(name).lower() == "watch-history.json"
    ]
    if not candidates:
        raise ValueError(
            "Zip does not contain watch-history.json. "
            "Export YouTube History as JSON from Google Takeout."
        )
    # Prefer the canonical Takeout path if multiple.
    for name in candidates:
        if "youtube" in name.lower() and "history" in name.lower():
            return name
    return candidates[0]


def load_events_from_path(path: str) -> tuple[list[dict[str, Any]], int]:
    """Load and parse events from a .json or .zip path."""
    lower = path.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(path, "r") as zf:
            member = find_watch_history_in_zip(zf)
            records = load_takeout_json_bytes(zf.read(member))
    elif lower.endswith(".json"):
        with open(path, "rb") as handle:
            records = load_takeout_json_bytes(handle.read())
    else:
        raise ValueError("Choose a watch-history.json file or a Takeout .zip.")
    return parse_takeout_records(records)


def merge_events(
    existing: dict[str, Any] | None,
    incoming: list[dict[str, Any]],
    *,
    unparsed: int = 0,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Merge incoming events into youtube_history. Returns (store, stats)."""
    store = normalize_youtube_history(existing)
    seen = {str(event.get("id")) for event in store["events"]}
    added = 0
    skipped = 0
    for event in incoming:
        eid = str(event.get("id") or "")
        if not eid or eid in seen:
            skipped += 1
            continue
        store["events"].append(event)
        seen.add(eid)
        added += 1
    store["events"].sort(key=lambda item: str(item.get("watched_at") or ""), reverse=True)
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    store["last_import_at"] = stamp
    stats = {"added": added, "skipped": skipped, "unparsed": int(unparsed)}
    store["last_import_stats"] = stats
    return store, stats


def _local_day(watched_at: str) -> str:
    """Calendar day in the local timezone (Integral day keys are local)."""
    text = watched_at.strip()
    if not text:
        return ""
    try:
        normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.date().isoformat()
    except ValueError:
        if "T" in text:
            return text.split("T", 1)[0]
        return text[:10]


def rollup_line(day: str, events: list[dict[str, Any]]) -> str:
    count = len(events)
    sample = events[0].get("title") if events else ""
    extra = f" e.g. {sample}" if sample else ""
    return f"[YouTube Takeout {day}] {count} watch{'es' if count != 1 else ''}{extra}"


def _replace_or_prepend_rollup_note(notes: str, day: str, line: str) -> str:
    """Replace an existing Takeout summary for this day, or prepend a new one."""
    marker = f"[YouTube Takeout {day}]"
    existing_lines = notes.splitlines() if notes else []
    kept = [row for row in existing_lines if not row.startswith(marker)]
    if kept:
        return "\n".join([line, *kept]).strip()
    return line


def apply_day_note_rollup(
    entries: dict[str, Any],
    youtube_history: dict[str, Any],
    *,
    only_event_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    Append/update non-destructive day summary notes for Content / Art.
    Never sets rating or checklist. Returns a new entries dict (shallow day copies).

    When ``only_event_ids`` is set, only days touched by those events are updated,
    but each day's line reflects **all** stored watches for that day/category so
    re-imports refresh the count instead of stacking partial lines.
    """
    store = normalize_youtube_history(youtube_history)
    all_by_bucket: dict[tuple[str, str], list[dict[str, Any]]] = {}
    touched_days: set[tuple[str, str]] = set()
    for event in store["events"]:
        day = _local_day(str(event.get("watched_at") or ""))
        if not day:
            continue
        category = ART_CATEGORY if event.get("source") == "youtube_music" else CONTENT_CATEGORY
        key = (day, category)
        all_by_bucket.setdefault(key, []).append(event)
        if only_event_ids is None or event["id"] in only_event_ids:
            touched_days.add(key)

    if only_event_ids is not None:
        keys = sorted(touched_days)
    else:
        keys = sorted(all_by_bucket.keys())

    if not keys:
        return entries

    updated: dict[str, Any] = {day: dict(cats) for day, cats in entries.items()}
    for day, category in keys:
        day_events = sorted(
            all_by_bucket.get((day, category), []),
            key=lambda e: str(e.get("watched_at") or ""),
        )
        if not day_events:
            continue
        # Only annotate days the user already logged for this category.
        # Creating a notes-only entry would count as life engagement for streaks.
        day_map = dict(updated.get(day) or {})
        if category not in day_map:
            continue
        line = rollup_line(day, day_events)
        cat_entry = dict(day_map.get(category) or {})
        notes = str(cat_entry.get("notes") or "")
        cat_entry["notes"] = _replace_or_prepend_rollup_note(notes, day, line)
        day_map[category] = cat_entry
        updated[day] = day_map
    return updated


def recent_events(youtube_history: dict[str, Any] | None, *, limit: int = 200) -> list[dict[str, Any]]:
    store = normalize_youtube_history(youtube_history)
    return list(store["events"][: max(0, int(limit))])
