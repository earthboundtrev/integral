"""Unified Integral cross-links: journal, domain, fitness day, writing project."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote

# journal:12hex
WIKI_JOURNAL = re.compile(r"\[\[journal:([a-f0-9]{12})(?:\|([^\]]+))?\]\]", re.I)
URI_JOURNAL = re.compile(r"integral://journal/([a-f0-9]{12})", re.I)

# domain:YYYY-MM-DD|Category Name
WIKI_DOMAIN = re.compile(
    r"\[\[domain:(\d{4}-\d{2}-\d{2})\|([^\]]+)\]\]",
    re.I,
)
URI_DOMAIN = re.compile(
    r"integral://domain/(\d{4}-\d{2}-\d{2})/([^/\s\]]+)",
    re.I,
)

# fitness:YYYY-MM-DD optional label
WIKI_FITNESS = re.compile(
    r"\[\[fitness:(\d{4}-\d{2}-\d{2})(?:\|([^\]]+))?\]\]",
    re.I,
)
URI_FITNESS = re.compile(r"integral://fitness/(\d{4}-\d{2}-\d{2})", re.I)

# project:12hex
WIKI_PROJECT = re.compile(r"\[\[project:([a-f0-9]{12})(?:\|([^\]]+))?\]\]", re.I)
URI_PROJECT = re.compile(r"integral://project/([a-f0-9]{12})", re.I)


@dataclass(frozen=True)
class IntegralLink:
    start: int
    end: int
    kind: str  # journal | domain | fitness | project
    target: str  # id or date
    extra: str | None  # category name, label, etc.
    label: str | None
    raw: str


def format_journal_wiki(entry_id: str, label: str | None = None) -> str:
    eid = entry_id.strip().lower()
    if label and label.strip():
        return f"[[journal:{eid}|{label.strip()}]]"
    return f"[[journal:{eid}]]"


def format_journal_uri(entry_id: str) -> str:
    return f"integral://journal/{entry_id.strip().lower()}"


def format_domain_wiki(day: str, category: str) -> str:
    return f"[[domain:{day}|{category}]]"


def format_domain_uri(day: str, category: str) -> str:
    return f"integral://domain/{day}/{quote(category, safe='')}"


def format_fitness_wiki(day: str, label: str | None = None) -> str:
    if label and label.strip():
        return f"[[fitness:{day}|{label.strip()}]]"
    return f"[[fitness:{day}]]"


def format_fitness_uri(day: str) -> str:
    return f"integral://fitness/{day}"


def format_project_wiki(project_id: str, label: str | None = None) -> str:
    pid = project_id.strip().lower()
    if label and label.strip():
        return f"[[project:{pid}|{label.strip()}]]"
    return f"[[project:{pid}]]"


def format_project_uri(project_id: str) -> str:
    return f"integral://project/{project_id.strip().lower()}"


def find_all_links(text: str) -> list[IntegralLink]:
    text = text or ""
    spans: list[IntegralLink] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(not (end <= a or start >= b) for a, b in occupied)

    def add(match: re.Match, kind: str, target: str, extra: str | None = None, label: str | None = None) -> None:
        start, end = match.span()
        if overlaps(start, end):
            return
        occupied.append((start, end))
        spans.append(
            IntegralLink(
                start=start,
                end=end,
                kind=kind,
                target=target,
                extra=extra,
                label=label,
                raw=match.group(0),
            )
        )

    for m in WIKI_JOURNAL.finditer(text):
        add(m, "journal", m.group(1).lower(), label=(m.group(2) or "").strip() or None)
    for m in WIKI_DOMAIN.finditer(text):
        add(m, "domain", m.group(1), extra=m.group(2).strip(), label=m.group(2).strip())
    for m in WIKI_FITNESS.finditer(text):
        add(m, "fitness", m.group(1), label=(m.group(2) or "").strip() or None)
    for m in WIKI_PROJECT.finditer(text):
        add(m, "project", m.group(1).lower(), label=(m.group(2) or "").strip() or None)

    for m in URI_JOURNAL.finditer(text):
        add(m, "journal", m.group(1).lower())
    for m in URI_DOMAIN.finditer(text):
        add(m, "domain", m.group(1), extra=unquote(m.group(2)))
    for m in URI_FITNESS.finditer(text):
        add(m, "fitness", m.group(1))
    for m in URI_PROJECT.finditer(text):
        add(m, "project", m.group(1).lower())

    spans.sort(key=lambda s: s.start)
    return spans


def parse_deep_link(url: str) -> IntegralLink | None:
    """Parse an integral:// URL into a synthetic IntegralLink (start/end 0)."""
    raw = (url or "").strip().strip('"').strip("'")
    if not raw:
        return None
    # Reuse finders on the URL alone
    found = find_all_links(raw)
    if found and found[0].raw == raw or (found and raw.lower().startswith("integral://")):
        # Prefer exact URI match
        for link in found:
            if link.raw.lower() == raw.lower() or raw.lower().startswith(link.raw.lower()):
                return link
        if found:
            return found[0]
    # Wiki pasted as argv
    found = find_all_links(raw)
    return found[0] if found else None


def find_backlinks(journal_data: dict[str, Any], entry_id: str) -> list[dict[str, Any]]:
    """Journal entries whose body links to entry_id."""
    needle = (entry_id or "").strip().lower()
    if not needle:
        return []
    hits: list[dict[str, Any]] = []
    for entry in journal_data.get("entries") or []:
        if str(entry.get("id", "")).lower() == needle:
            continue
        body = entry.get("body") or ""
        for link in find_all_links(body):
            if link.kind == "journal" and link.target == needle:
                hits.append(entry)
                break
    hits.sort(key=lambda e: (e.get("entry_date", ""), e.get("written_at", "")), reverse=True)
    return hits
