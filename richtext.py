"""Lightweight markdown/forum-style formatting for Tk Text (stdlib only)."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Inline patterns — applied after masking wiki/URI links so we don't style inside them.
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
CODE_RE = re.compile(r"`([^`]+)`")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")
LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.+)$")


@dataclass(frozen=True)
class StyleSpan:
    start: int
    end: int
    style: str  # bold | italic | code | h1 | h2 | h3 | quote | list


def _mask_ranges(text: str, ranges: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in ranges:
        for i in range(start, min(end, len(chars))):
            chars[i] = " "
    return "".join(chars)


def find_style_spans(text: str, *, protected: list[tuple[int, int]] | None = None) -> list[StyleSpan]:
    """Find markdown-lite spans. `protected` ranges (e.g. wiki links) are skipped."""
    text = text or ""
    protected = protected or []
    masked = _mask_ranges(text, protected)
    spans: list[StyleSpan] = []

    # Block styles line-by-line on original offsets
    offset = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n\r")
        heading = HEADING_RE.match(bare)
        if heading:
            level = len(heading.group(1))
            style = {1: "h1", 2: "h2", 3: "h3"}.get(level, "h3")
            spans.append(StyleSpan(offset, offset + len(bare), style))
        elif QUOTE_RE.match(bare):
            spans.append(StyleSpan(offset, offset + len(bare), "quote"))
        elif LIST_RE.match(bare):
            spans.append(StyleSpan(offset, offset + len(bare), "list"))
        offset += len(line)

    for match in CODE_RE.finditer(masked):
        spans.append(StyleSpan(match.start(1), match.end(1), "code"))
    for match in BOLD_RE.finditer(masked):
        spans.append(StyleSpan(match.start(1), match.end(1), "bold"))
    for match in ITALIC_RE.finditer(masked):
        spans.append(StyleSpan(match.start(1), match.end(1), "italic"))

    spans.sort(key=lambda s: (s.start, s.end))
    return spans


def apply_richtext_tags(text_widget, theme: dict | None = None) -> None:
    """Apply formatting tags to a Tk Text widget (does not remove link tags)."""
    import tkinter as tk

    theme = theme or {}
    content = text_widget.get("1.0", "end-1c")
    # Protect wiki/URI style links if journal helpers available
    protected: list[tuple[int, int]] = []
    try:
        import integral_links

        protected = [(s.start, s.end) for s in integral_links.find_all_links(content)]
    except Exception:  # noqa: BLE001
        pass

    for name in ("rt_bold", "rt_italic", "rt_code", "rt_h1", "rt_h2", "rt_h3", "rt_quote", "rt_list"):
        text_widget.tag_remove(name, "1.0", "end")

    fg = theme.get("fg", "#1a1a1a")
    muted = theme.get("muted", "#666666")
    accent = theme.get("accent", "#5B8DEF")
    text_widget.tag_configure("rt_bold", font=("Segoe UI", 11, "bold"))
    text_widget.tag_configure("rt_italic", font=("Segoe UI", 11, "italic"))
    text_widget.tag_configure("rt_code", font=("Consolas", 10), background=theme.get("surface2", "#f0f0f0"))
    text_widget.tag_configure("rt_h1", font=("Segoe UI", 16, "bold"), foreground=fg)
    text_widget.tag_configure("rt_h2", font=("Segoe UI", 14, "bold"), foreground=fg)
    text_widget.tag_configure("rt_h3", font=("Segoe UI", 12, "bold"), foreground=fg)
    text_widget.tag_configure("rt_quote", foreground=muted, lmargin1=16, lmargin2=16)
    text_widget.tag_configure("rt_list", lmargin1=12, lmargin2=24)

    style_map = {
        "bold": "rt_bold",
        "italic": "rt_italic",
        "code": "rt_code",
        "h1": "rt_h1",
        "h2": "rt_h2",
        "h3": "rt_h3",
        "quote": "rt_quote",
        "list": "rt_list",
    }
    for span in find_style_spans(content, protected=protected):
        tag = style_map.get(span.style)
        if not tag:
            continue
        text_widget.tag_add(tag, f"1.0+{span.start}c", f"1.0+{span.end}c")

    # Keep links visually above formatting
    try:
        text_widget.tag_raise("integral_link")
    except tk.TclError:
        pass
    del accent  # reserved for future link styling here


def wrap_selection(text_widget, prefix: str, suffix: str | None = None) -> None:
    """Wrap current selection (or insert markers) with markdown delimiters."""
    suffix = prefix if suffix is None else suffix
    try:
        start = text_widget.index("sel.first")
        end = text_widget.index("sel.last")
        selected = text_widget.get(start, end)
        text_widget.delete(start, end)
        text_widget.insert(start, f"{prefix}{selected}{suffix}")
    except Exception:  # noqa: BLE001 — no selection
        text_widget.insert("insert", f"{prefix}{suffix}")
        if suffix:
            # Move cursor between markers
            text_widget.mark_set("insert", f"insert-{len(suffix)}c")


def insert_line_prefix(text_widget, prefix: str) -> None:
    line_start = text_widget.index("insert linestart")
    text_widget.insert(line_start, prefix)
