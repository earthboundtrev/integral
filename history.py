from datetime import datetime

DEFAULT_RECENT_LIMIT = 12
NOTES_PREVIEW_LEN = 80


def _notes_preview(notes: str, max_len: int = NOTES_PREVIEW_LEN) -> str:
    text = (notes or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def list_recent_entries(entries, limit: int = DEFAULT_RECENT_LIMIT) -> list[dict]:
    if not entries:
        return []

    items = []
    for date_str, day in entries.items():
        for category, entry in day.items():
            items.append(
                {
                    "date": date_str,
                    "category": category,
                    "rating": entry.get("rating", "?"),
                    "notes_preview": _notes_preview(entry.get("notes", "")),
                }
            )

    items.sort(key=lambda item: item["category"])
    items.sort(key=lambda item: item["date"], reverse=True)
    return items[:limit]


def format_recent_activity(entries, limit: int = DEFAULT_RECENT_LIMIT) -> str:
    recent = list_recent_entries(entries, limit)
    if not recent:
        return (
            "No activity yet.\n\n"
            'Log any category with "Log / Update Today" to see entries here.'
        )

    lines = []
    for item in recent:
        try:
            date_display = datetime.strptime(item["date"], "%Y-%m-%d").strftime("%b %d, %Y")
        except ValueError:
            date_display = item["date"]
        lines.append(f"{date_display} · {item['category']} · {item['rating']}/10")
        if item["notes_preview"]:
            lines.append(f"  {item['notes_preview']}")
        lines.append("")
    return "\n".join(lines).strip()


def format_history(entries):
    if not entries:
        return "No entries yet. Start logging from the dashboard."

    lines = []
    for date_str in sorted(entries.keys(), reverse=True):
        lines.append(f"\n=== {date_str} ===")
        for cat, entry in entries[date_str].items():
            rating = entry.get("rating", "?")
            notes = entry.get("notes", "")
            preview = notes[:200] + ("..." if len(notes) > 200 else "")
            lines.append(f"\n{cat} - Rating: {rating}")
            lines.append(f"Notes: {preview}")
    return "\n".join(lines).lstrip()