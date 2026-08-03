"""Quick Capture mode — settings, YouTube oEmbed, day-entry starters (SPEC-314)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SECTION_KEYS = ("today", "upcoming")
DEFAULT_QUICK_CAPTURE = {"enabled": False, "collapsed": {"today": False, "upcoming": False}}

_YOUTUBE_HOSTS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
)

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def default_quick_capture_settings() -> dict:
    return {"enabled": False, "collapsed": {key: False for key in SECTION_KEYS}}


def _normalize_collapsed(raw: dict | None) -> dict:
    collapsed = {key: False for key in SECTION_KEYS}
    if isinstance(raw, dict):
        for key in SECTION_KEYS:
            collapsed[key] = bool(raw.get(key, False))
    return collapsed


def normalize_quick_capture_settings(settings: dict | None) -> dict:
    base = default_quick_capture_settings()
    if not isinstance(settings, dict):
        return base
    raw = settings.get("quick_capture")
    if not isinstance(raw, dict):
        return base
    out = {
        "enabled": bool(raw.get("enabled", False)),
        "collapsed": _normalize_collapsed(raw.get("collapsed")),
    }
    if raw.get("todo_done_entries_backfilled"):
        out["todo_done_entries_backfilled"] = True
    return out


def apply_quick_capture_settings(settings: dict | None, quick_capture: dict) -> dict:
    """Merge ``quick_capture`` onto existing normalized settings (partial updates OK)."""
    out = dict(settings or {})
    current = normalize_quick_capture_settings(settings)
    merged = {**current, **(quick_capture or {})}
    if "collapsed" in (quick_capture or {}):
        merged["collapsed"] = {**current["collapsed"], **(quick_capture["collapsed"] or {})}
    out["quick_capture"] = normalize_quick_capture_settings({"quick_capture": merged})
    return out


def is_quick_capture_enabled(settings: dict | None) -> bool:
    return bool(normalize_quick_capture_settings(settings).get("enabled"))


def is_section_collapsed(settings: dict | None, section: str) -> bool:
    return bool(normalize_quick_capture_settings(settings)["collapsed"].get(section, False))


def set_section_collapsed(settings: dict | None, section: str, collapsed: bool) -> dict:
    if section not in SECTION_KEYS:
        return dict(settings or {})
    return apply_quick_capture_settings(settings, {"collapsed": {section: bool(collapsed)}})


def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match((text or "").strip()))


def is_youtube_url(url: str) -> bool:
    text = (url or "").strip().lower()
    if not text.startswith(("http://", "https://")):
        return False
    try:
        from urllib.parse import urlparse

        host = (urlparse(text).hostname or "").lower()
    except Exception:
        return False
    return host in _YOUTUBE_HOSTS or host.endswith(".youtube.com")


def fetch_youtube_title(url: str, *, timeout: float = 3.0) -> str | None:
    """Best-effort public oEmbed title. Returns None on any failure."""
    if not is_youtube_url(url):
        return None
    query = urlencode({"url": url.strip(), "format": "json"})
    endpoint = f"https://www.youtube.com/oembed?{query}"
    request = Request(endpoint, headers={"User-Agent": "Integral/QuickCapture"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None
    title = payload.get("title") if isinstance(payload, dict) else None
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def format_capture_note(*, url: str, title: str = "", when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%H:%M")
    url = (url or "").strip()
    title = (title or "").strip()
    header = f"[Quick Capture {stamp}]"
    if title:
        return f"{header} {title}\n{url}".strip()
    return f"{header}\n{url}".strip()


def merge_day_entry_starter(
    entries: dict,
    *,
    date_str: str,
    category: str,
    url: str,
    title: str = "",
    when: datetime | None = None,
) -> dict:
    """Merge a link starter into today's category entry. Mutates and returns entries."""
    day = entries.setdefault(date_str, {})
    existing = dict(day.get(category) or {})
    starter = format_capture_note(url=url, title=title, when=when)
    prev = (existing.get("notes") or "").strip()
    notes = f"{starter}\n\n{prev}" if prev else starter
    day[category] = {
        "rating": existing.get("rating", 5),
        "checklist": dict(existing.get("checklist") or {}),
        "metrics": dict(existing.get("metrics") or {}),
        "notes": notes,
    }
    if existing.get("backdate_reason"):
        day[category]["backdate_reason"] = existing["backdate_reason"]
    return entries


def format_todo_done_note(
    *, text: str, when: datetime | None = None, todo_id: str = ""
) -> str:
    stamp = (when or datetime.now()).strftime("%H:%M")
    cleaned = (text or "").strip() or "Todo"
    line = f"[Todo done {stamp}] {cleaned}"
    tid = (todo_id or "").strip()
    if tid:
        return f"{line} (#{tid})"
    return line


def _todo_done_line_task_text(stripped: str) -> str | None:
    """Return the task text from a Todo-done note line, or None if not one."""
    if not stripped.startswith("[Todo done "):
        return None
    close = stripped.find("] ")
    if close < 0:
        return None
    rest = stripped[close + 2 :]
    marker = " (#"
    if marker in rest and rest.endswith(")"):
        rest = rest[: rest.rfind(marker)]
    return rest


def todo_done_note_present(notes: str, text: str, *, todo_id: str = "") -> bool:
    """
    True if notes already contain a Todo-done line for this completion.

    When todo_id is set, match that id only (same display text can log twice).
    When todo_id is empty, match exact task text on legacy lines (no id suffix).
    """
    cleaned = (text or "").strip() or "Todo"
    tid = (todo_id or "").strip()
    for line in (notes or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("[Todo done "):
            continue
        if tid:
            if f"(#{tid})" in stripped:
                return True
            continue
        task = _todo_done_line_task_text(stripped)
        if task == cleaned and "(#" not in stripped:
            return True
    return False


def _scan_todo_done_notes(
    entries: dict, *, category: str, text: str
) -> tuple[int, set[str]]:
    """Count legacy (no-id) Todo-done lines and collect todo ids already logged."""
    cleaned = (text or "").strip() or "Todo"
    legacy = 0
    ids: set[str] = set()
    for day in (entries or {}).values():
        if not isinstance(day, dict):
            continue
        cat_entry = day.get(category)
        if not isinstance(cat_entry, dict):
            continue
        for line in str(cat_entry.get("notes") or "").splitlines():
            stripped = line.strip()
            if _todo_done_line_task_text(stripped) != cleaned:
                continue
            marker = " (#"
            if marker in stripped and stripped.endswith(")"):
                start = stripped.rfind(marker) + len(marker)
                end = stripped.rfind(")")
                tid = stripped[start:end].strip()
                if tid:
                    ids.add(tid)
            else:
                legacy += 1
    return legacy, ids


def merge_todo_done_line(
    entries: dict,
    *,
    date_str: str,
    category: str,
    text: str,
    when: datetime | None = None,
    todo_id: str = "",
) -> dict:
    """Append a todo-completion line into category notes (idempotent per todo id)."""
    day = entries.setdefault(date_str, {})
    existing = dict(day.get(category) or {})
    prev = (existing.get("notes") or "").strip()
    if todo_done_note_present(prev, text, todo_id=todo_id):
        return entries
    line = format_todo_done_note(text=text, when=when, todo_id=todo_id)
    notes = f"{line}\n\n{prev}" if prev else line
    day[category] = {
        "rating": existing.get("rating", 5),
        "checklist": dict(existing.get("checklist") or {}),
        "metrics": dict(existing.get("metrics") or {}),
        "notes": notes,
    }
    if existing.get("backdate_reason"):
        day[category]["backdate_reason"] = existing["backdate_reason"]
    return entries


def backfill_todo_done_entries(
    entries: dict,
    todos_store: dict,
    *,
    today: str,
) -> tuple[dict, int]:
    """
    For done todos that already have a category, ensure a day-entry note exists.

    Uses completed_at as the note day. Skips when completed_at is empty (do not
    invent today or scheduled work_date). Skips when `(#todo_id)` is already
    present on any day for that category. Skips todos with no category.
    Returns (entries, number_of_lines_added).
    """
    import todos as todos_mod

    _ = today  # call-site compat; dating requires completed_at
    added = 0
    for item in todos_mod.list_items(todos_store):
        if not item.get("done"):
            continue
        category = (item.get("category") or "").strip()
        if not category:
            continue
        text = (item.get("text") or "").strip() or "Todo"
        todo_id = (item.get("id") or "").strip()
        date_str = (item.get("completed_at") or "").strip()
        if not date_str:
            # Without completed_at we cannot know the real completion day;
            # skip rather than invent today or use scheduled work_date.
            continue
        _legacy, id_set = _scan_todo_done_notes(
            entries, category=category, text=text
        )
        if todo_id and todo_id in id_set:
            continue
        merge_todo_done_line(
            entries,
            date_str=date_str,
            category=category,
            text=text,
            todo_id=todo_id,
        )
        added += 1
    return entries, added
