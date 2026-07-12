from datetime import date, datetime, timedelta


def _day_logged(entries, day: date, category=None) -> bool:
    day_entries = entries.get(day.strftime("%Y-%m-%d"))
    if category is None:
        return bool(day_entries)
    return bool(day_entries and category in day_entries)


def get_streak(entries, category=None, *, today: date | None = None):
    """
    Count consecutive logged days ending today.

    If today is not logged yet, count the streak ending yesterday (grace until
    midnight local — missing today does not break the streak mid-day).
    """
    if not entries:
        return 0

    expected = today or datetime.now().date()
    if not _day_logged(entries, expected, category):
        expected = expected - timedelta(days=1)

    streak = 0
    while True:
        if not _day_logged(entries, expected, category):
            break
        streak += 1
        expected -= timedelta(days=1)
    return streak
