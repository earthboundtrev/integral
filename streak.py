from datetime import date, datetime, timedelta


def day_has_engagement(
    entries,
    day: date,
    *,
    journal=None,
    sessions: list | None = None,
) -> bool:
    """True if the calendar day has honest presence: life log, journal, or fitness."""
    date_str = day.strftime("%Y-%m-%d")
    day_entries = (entries or {}).get(date_str)
    if day_entries:
        return True

    if sessions:
        for session in sessions:
            if session.get("date") == date_str:
                return True

    if journal:
        from journal import count_entries_for_day

        if count_entries_for_day(journal, day) > 0:
            return True

    return False


def _day_logged(entries, day: date, category=None, *, journal=None, sessions=None) -> bool:
    if category is not None:
        day_entries = (entries or {}).get(day.strftime("%Y-%m-%d"))
        return bool(day_entries and category in day_entries)
    return day_has_engagement(entries, day, journal=journal, sessions=sessions)


def get_streak(
    entries,
    category=None,
    *,
    today: date | None = None,
    journal=None,
    sessions: list | None = None,
):
    """
    Count consecutive engaged days ending today.

    Overall streak: life domain, journal, or fitness session counts as engagement.
    Category streak: that life-domain category only (ignores journal/fitness).

    If today is not engaged yet, count the streak ending yesterday (grace until
    midnight local — missing today does not break the streak mid-day).
    """
    if category is not None:
        if not entries:
            return 0
        journal = None
        sessions = None
    elif not entries and not journal and not sessions:
        return 0

    expected = today or datetime.now().date()
    if not _day_logged(entries, expected, category, journal=journal, sessions=sessions):
        expected = expected - timedelta(days=1)

    streak = 0
    while True:
        if not _day_logged(entries, expected, category, journal=journal, sessions=sessions):
            break
        streak += 1
        expected -= timedelta(days=1)
    return streak


GAP_LOOKBACK_DAYS = 14

GAP_REPAIR_NUDGE = (
    "Yesterday has no log. A short journal for that day—say what got in the way—"
    "keeps continuity. Honest presence, not a streak freeze."
)


def gap_repair_hint(
    *,
    today: date | None = None,
    entries=None,
    journal=None,
    sessions: list | None = None,
) -> str | None:
    """
    Suggest human gap repair when yesterday is empty but recent prior days were engaged.
    """
    today = today or datetime.now().date()
    yesterday = today - timedelta(days=1)
    if day_has_engagement(entries, yesterday, journal=journal, sessions=sessions):
        return None

    for offset in range(2, GAP_LOOKBACK_DAYS + 1):
        prior = today - timedelta(days=offset)
        if day_has_engagement(entries, prior, journal=journal, sessions=sessions):
            return GAP_REPAIR_NUDGE
    return None
