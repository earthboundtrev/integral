"""General journal entries — prompts, free write, and backdated logging."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

GAP_PROMPT = "What got in the way of logging?"

DEFAULT_PROMPTS = [
    "Free write — no prompt",
    "What am I noticing right now?",
    "What challenged me today?",
    "What am I grateful for?",
    "End-of-day reflection",
    GAP_PROMPT,
    "Fitness / CC training notes",
    "Search practice — what's alive?",
    "What do I want to remember?",
    "Stream of consciousness",
]

MIN_BACKDATE_REASON_LEN = 12


def empty_journal() -> dict[str, Any]:
    return {"prompts": list(DEFAULT_PROMPTS), "entries": []}


def normalize_journal(stored: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_journal()
    if not stored:
        return base

    prompts = list(stored.get("prompts") or [])
    for prompt in DEFAULT_PROMPTS:
        if prompt not in prompts:
            prompts.append(prompt)

    entries: list[dict[str, Any]] = []
    for raw in stored.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        body = str(raw.get("body", "")).strip()
        if not body:
            continue
        entry_date = str(raw.get("entry_date", "")).strip()
        if not parse_entry_date(entry_date):
            continue
        entries.append(
            {
                "id": str(raw.get("id") or new_entry_id()),
                "entry_date": entry_date,
                "written_at": str(raw.get("written_at") or datetime.now().isoformat(timespec="seconds")),
                "prompt": str(raw.get("prompt") or DEFAULT_PROMPTS[0]),
                "title": str(raw.get("title") or "").strip(),
                "body": body,
                "backdate_reason": str(raw.get("backdate_reason") or "").strip() or None,
            }
        )

    base["prompts"] = prompts
    base["entries"] = entries
    return base


def new_entry_id() -> str:
    return uuid.uuid4().hex[:12]


def parse_entry_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def validate_backdate(entry_date: str, today: date | None = None, reason: str = "") -> str | None:
    """Return an error message, or None if valid."""
    parsed = parse_entry_date(entry_date)
    if parsed is None:
        return "Use a valid date (YYYY-MM-DD)."

    today = today or date.today()
    if parsed > today:
        return "You cannot log journal entries for a future date."

    if parsed < today:
        cleaned = reason.strip()
        if len(cleaned) < MIN_BACKDATE_REASON_LEN:
            return (
                f"Logging for a past date requires a reason "
                f"(at least {MIN_BACKDATE_REASON_LEN} characters)."
            )
    return None


def create_entry(
    entry_date: str,
    body: str,
    *,
    prompt: str = DEFAULT_PROMPTS[0],
    title: str = "",
    backdate_reason: str | None = None,
    entry_id: str | None = None,
    written_at: str | None = None,
) -> dict[str, Any]:
    cleaned_body = body.strip()
    if not cleaned_body:
        raise ValueError("Journal entry cannot be empty.")

    today = date.today()
    parsed = parse_entry_date(entry_date)
    if parsed is None:
        raise ValueError("Invalid entry date.")

    reason = (backdate_reason or "").strip() or None
    if parsed < today and not reason:
        raise ValueError("Backdate reason required for past entries.")

    return {
        "id": entry_id or new_entry_id(),
        "entry_date": entry_date.strip(),
        "written_at": written_at or datetime.now().isoformat(timespec="seconds"),
        "prompt": prompt.strip() or DEFAULT_PROMPTS[0],
        "title": title.strip(),
        "body": cleaned_body,
        "backdate_reason": reason if parsed < today else None,
    }


def list_entries(
    journal: dict[str, Any],
    *,
    entry_date: str | None = None,
    newest_first: bool = True,
) -> list[dict[str, Any]]:
    entries = list(journal.get("entries") or [])
    if entry_date:
        entries = [entry for entry in entries if entry.get("entry_date") == entry_date]

    entries.sort(
        key=lambda item: (item.get("entry_date", ""), item.get("written_at", "")),
        reverse=newest_first,
    )
    return entries


def entries_for_day(journal: dict[str, Any], day: date) -> list[dict[str, Any]]:
    return list_entries(journal, entry_date=day.strftime("%Y-%m-%d"), newest_first=True)


def count_entries_for_day(journal: dict[str, Any], day: date) -> int:
    return len(entries_for_day(journal, day))


def search_entries(journal: dict[str, Any], query: str) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    if not needle:
        return list_entries(journal)

    hits = []
    for entry in journal.get("entries") or []:
        blob = " ".join(
            [
                entry.get("entry_date", ""),
                entry.get("title", ""),
                entry.get("prompt", ""),
                entry.get("body", ""),
                entry.get("backdate_reason") or "",
            ]
        ).lower()
        if needle in blob:
            hits.append(entry)

    hits.sort(key=lambda item: (item.get("entry_date", ""), item.get("written_at", "")), reverse=True)
    return hits


def format_entry_summary(entry: dict[str, Any], *, max_body: int = 160) -> str:
    title = entry.get("title") or entry.get("prompt") or "Journal"
    body = entry.get("body", "")
    preview = body[:max_body] + ("..." if len(body) > max_body else "")
    backdated = ""
    if entry.get("backdate_reason"):
        backdated = f"\n  (backdated — {entry['backdate_reason']})"
    return f"{entry.get('entry_date')} — {title}\n{preview}{backdated}"


def upsert_entry(journal: dict[str, Any], entry: dict[str, Any]) -> None:
    entries = journal.setdefault("entries", [])
    for index, existing in enumerate(entries):
        if existing.get("id") == entry.get("id"):
            entries[index] = entry
            return
    entries.append(entry)


def delete_entry(journal: dict[str, Any], entry_id: str) -> bool:
    entries = journal.get("entries") or []
    kept = [entry for entry in entries if entry.get("id") != entry_id]
    if len(kept) == len(entries):
        return False
    journal["entries"] = kept
    return True


def export_rows(journal: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for entry in list_entries(journal, newest_first=False):
        rows.append(
            {
                "entry_date": entry.get("entry_date", ""),
                "written_at": entry.get("written_at", ""),
                "prompt": entry.get("prompt", ""),
                "title": entry.get("title", ""),
                "body": entry.get("body", ""),
                "backdate_reason": entry.get("backdate_reason") or "",
            }
        )
    return rows


# --- Cross-links (SPEC-309) ---

JOURNAL_ID_RE = re.compile(r"^[a-f0-9]{12}$", re.IGNORECASE)
WIKI_JOURNAL_RE = re.compile(
    r"\[\[journal:([a-f0-9]{12})(?:\|([^\]]+))?\]\]",
    re.IGNORECASE,
)
URI_JOURNAL_RE = re.compile(
    r"integral://journal/([a-f0-9]{12})",
    re.IGNORECASE,
)


def get_entry(journal_data: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    needle = (entry_id or "").strip().lower()
    if not JOURNAL_ID_RE.match(needle):
        return None
    for entry in journal_data.get("entries") or []:
        if str(entry.get("id", "")).lower() == needle:
            return entry
    return None


def entry_label(entry: dict[str, Any]) -> str:
    return (entry.get("title") or entry.get("prompt") or entry.get("entry_date") or "Journal").strip()


def format_journal_wiki_link(entry_id: str, label: str | None = None) -> str:
    eid = entry_id.strip().lower()
    if label and label.strip():
        return f"[[journal:{eid}|{label.strip()}]]"
    return f"[[journal:{eid}]]"


def format_journal_uri(entry_id: str) -> str:
    return f"integral://journal/{entry_id.strip().lower()}"


@dataclass(frozen=True)
class JournalLinkSpan:
    start: int
    end: int
    entry_id: str
    label: str | None
    raw: str


def find_journal_links(text: str) -> list[JournalLinkSpan]:
    """Find wiki and URI journal links (compat wrapper over integral_links)."""
    import integral_links

    spans: list[JournalLinkSpan] = []
    for link in integral_links.find_all_links(text):
        if link.kind != "journal":
            continue
        spans.append(
            JournalLinkSpan(
                start=link.start,
                end=link.end,
                entry_id=link.target,
                label=link.label,
                raw=link.raw,
            )
        )
    return spans


def parse_deep_link_target(url: str) -> tuple[str, str] | None:
    """
    Parse integral://… deep links.
    Returns (kind, target) where kind is journal|domain|fitness|project.
    For domain, target is 'YYYY-MM-DD\\tCategory'.
    """
    import integral_links

    link = integral_links.parse_deep_link(url)
    if not link:
        return None
    if link.kind == "domain":
        return ("domain", f"{link.target}\t{link.extra or ''}")
    return (link.kind, link.target)


def find_backlinks(journal_data: dict[str, Any], entry_id: str) -> list[dict[str, Any]]:
    import integral_links

    return integral_links.find_backlinks(journal_data, entry_id)
