from datetime import datetime, timedelta


def _parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def numeric_rating(entry):
    """Return the entry's rating as a float, or None when it is missing or not numeric."""
    value = entry.get("rating")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _ratings_for_dates(entries, start_date):
    ratings = []
    active_days = 0
    for date_str, day_entries in entries.items():
        if _parse_date(date_str) >= start_date:
            if day_entries:
                active_days += 1
            for entry in day_entries.values():
                rating = numeric_rating(entry)
                if rating is not None:
                    ratings.append(rating)
    return ratings, active_days


def count_notes(entries, start_date=None):
    count = 0
    for date_str, day_entries in entries.items():
        if start_date and _parse_date(date_str) < start_date:
            continue
        for entry in day_entries.values():
            if entry.get("notes", "").strip():
                count += 1
    return count


def build_summary_text(entries):
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)

    lines = ["=== TODAY ==="]
    today_entries = entries.get(today_str, {})
    if today_entries:
        ratings = [r for r in (numeric_rating(e) for e in today_entries.values()) if r is not None]
        if ratings:
            avg = sum(ratings) / len(ratings)
            lines.append(f"Average rating: {avg:.1f}/10")
        lines.append(f"Categories logged: {len(today_entries)}")
        lines.append(f"Overall streak: see dashboard")
    else:
        lines.append("No logs today yet.")

    lines.append("\n=== THIS WEEK ===")
    week_ratings, week_days = _ratings_for_dates(entries, week_start)
    if week_ratings:
        lines.append(f"Avg rating: {sum(week_ratings) / len(week_ratings):.1f}/10")
        lines.append(f"Days active: {week_days}")
        lines.append(f"Notes written: {count_notes(entries, week_start)}")
    else:
        lines.append("No data this week.")

    lines.append("\n=== LAST 30 DAYS ===")
    month_ratings, month_days = _ratings_for_dates(entries, month_start)
    if month_ratings:
        lines.append(f"Avg rating: {sum(month_ratings) / len(month_ratings):.1f}/10")
        lines.append(f"Active days: {month_days}")
        lines.append(f"Total notes written: {count_notes(entries, month_start)}")
    else:
        lines.append("No data in the last 30 days.")

    lines.append("\nDetailed per-category stats available in graphs.")
    return "\n".join(lines)
