from datetime import datetime, timedelta


def get_streak(entries, category=None):
    """Count consecutive logged days ending today — O(streak length), not O(n log n)."""
    if not entries:
        return 0

    streak = 0
    expected = datetime.now().date()
    while True:
        date_str = expected.strftime("%Y-%m-%d")
        day_entries = entries.get(date_str)
        if category is None:
            logged = bool(day_entries)
        else:
            logged = bool(day_entries and category in day_entries)
        if not logged:
            break
        streak += 1
        expected -= timedelta(days=1)
    return streak
