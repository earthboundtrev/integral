"""Quick Capture mode — settings, YouTube oEmbed, day-entry starters (SPEC-314)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_QUICK_CAPTURE = {"enabled": False}

_YOUTUBE_HOSTS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
)

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def default_quick_capture_settings() -> dict:
    return dict(DEFAULT_QUICK_CAPTURE)


def normalize_quick_capture_settings(settings: dict | None) -> dict:
    base = default_quick_capture_settings()
    if not isinstance(settings, dict):
        return base
    raw = settings.get("quick_capture")
    if not isinstance(raw, dict):
        return base
    return {"enabled": bool(raw.get("enabled", False))}


def apply_quick_capture_settings(settings: dict | None, quick_capture: dict) -> dict:
    out = dict(settings or {})
    out["quick_capture"] = normalize_quick_capture_settings({"quick_capture": quick_capture})
    return out


def is_quick_capture_enabled(settings: dict | None) -> bool:
    return bool(normalize_quick_capture_settings(settings).get("enabled"))


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


def format_todo_done_note(*, text: str, when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%H:%M")
    cleaned = (text or "").strip() or "Todo"
    return f"[Todo done {stamp}] {cleaned}"


def merge_todo_done_line(
    entries: dict,
    *,
    date_str: str,
    category: str,
    text: str,
    when: datetime | None = None,
) -> dict:
    """Append a todo-completion line into today's category notes."""
    day = entries.setdefault(date_str, {})
    existing = dict(day.get(category) or {})
    line = format_todo_done_note(text=text, when=when)
    prev = (existing.get("notes") or "").strip()
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
