from datetime import date, datetime, timedelta


def day_has_engagement(
    entries,
    day: date,
    *,
    journal=None,
    sessions: list | None = None,
) -> bool:
    """True if the calendar day has honest presence: life log, journal, or fitness."""
    return bool(
        engagement_breakdown(entries, day, journal=journal, sessions=sessions)["engaged"]
    )


def engagement_breakdown(
    entries,
    day: date,
    *,
    journal=None,
    sessions: list | None = None,
) -> dict:
    """
    Explain why a calendar day counts (or not) toward the overall streak.

    Returns keys: date, life (list[str]), journal_count (int), fitness_count (int), engaged (bool).
    """
    date_str = day.strftime("%Y-%m-%d")
    day_entries = (entries or {}).get(date_str) or {}
    life = sorted(str(name) for name in day_entries.keys())

    journal_count = 0
    if journal:
        from journal import count_entries_for_day

        journal_count = int(count_entries_for_day(journal, day) or 0)

    fitness_count = 0
    if sessions:
        fitness_count = sum(1 for session in sessions if session.get("date") == date_str)

    return {
        "date": date_str,
        "life": life,
        "journal_count": journal_count,
        "fitness_count": fitness_count,
        "engaged": bool(life or journal_count or fitness_count),
    }


def format_engagement_reasons(breakdown: dict) -> str:
    """Human one-liner for life / journal / fitness contributions."""
    parts: list[str] = []
    life = breakdown.get("life") or []
    if life:
        if len(life) == 1:
            parts.append(f"life: {life[0]}")
        else:
            parts.append(f"life: {len(life)} domains ({', '.join(life[:3])}{'…' if len(life) > 3 else ''})")
    journal_count = int(breakdown.get("journal_count") or 0)
    if journal_count:
        parts.append(f"journal ×{journal_count}" if journal_count > 1 else "journal")
    fitness_count = int(breakdown.get("fitness_count") or 0)
    if fitness_count:
        parts.append(
            f"fitness ×{fitness_count}" if fitness_count > 1 else "fitness"
        )
    return "; ".join(parts) if parts else "no engagement"


def streak_day_summaries(
    entries,
    *,
    days: int = 14,
    today: date | None = None,
    journal=None,
    sessions: list | None = None,
    category: str | None = None,
) -> list[dict]:
    """Recent calendar days with engagement breakdown (newest first)."""
    today = today or datetime.now().date()
    lookback = max(1, int(days))
    rows: list[dict] = []
    for offset in range(lookback):
        day = today - timedelta(days=offset)
        if category is not None:
            date_str = day.strftime("%Y-%m-%d")
            logged = bool((entries or {}).get(date_str, {}).get(category))
            rows.append(
                {
                    "date": date_str,
                    "life": [category] if logged else [],
                    "journal_count": 0,
                    "fitness_count": 0,
                    "engaged": logged,
                    "category": category,
                }
            )
        else:
            rows.append(
                engagement_breakdown(entries, day, journal=journal, sessions=sessions)
            )
    return rows


def format_streak_detail_text(
    *,
    overall_streak: int,
    entries,
    journal=None,
    sessions: list | None = None,
    today: date | None = None,
    lookback_days: int = 14,
    category: str | None = None,
    category_streak: int | None = None,
) -> str:
    """Plain-text report for the streak details dialog."""
    today = today or datetime.now().date()
    lines: list[str] = []
    if category:
        streak_n = category_streak if category_streak is not None else overall_streak
        lines.append(f"{category}")
        lines.append(f"Domain streak: {streak_n} day{'s' if streak_n != 1 else ''}")
        lines.append("")
        lines.append(
            "Category streaks count life-domain logs only (journal and fitness do not apply)."
        )
        today_logged = bool((entries or {}).get(today.strftime("%Y-%m-%d"), {}).get(category))
        if not today_logged and streak_n > 0:
            lines.append(
                "Today is not logged yet for this domain — mid-day grace still counts consecutive prior days until midnight."
            )
    else:
        lines.append(f"Overall streak: {overall_streak} day{'s' if overall_streak != 1 else ''}")
        lines.append("")
        lines.append(
            "A day counts when you log a life domain, write in the journal, or save a fitness session."
        )
        today_engaged = day_has_engagement(
            entries, today, journal=journal, sessions=sessions
        )
        if not today_engaged and overall_streak > 0:
            lines.append(
                "Today is still empty — mid-day grace keeps the streak based on yesterday until midnight."
            )

    gap = gap_repair_hint(
        today=today, entries=entries, journal=journal, sessions=sessions
    )
    if gap and not category:
        lines.append("")
        lines.append(gap)

    lines.append("")
    lines.append(f"Last {lookback_days} days")
    lines.append("-" * 40)
    for row in streak_day_summaries(
        entries,
        days=lookback_days,
        today=today,
        journal=journal,
        sessions=sessions,
        category=category,
    ):
        mark = "✓" if row.get("engaged") else "·"
        if category:
            reason = "logged" if row.get("engaged") else "not logged"
        else:
            reason = format_engagement_reasons(row)
        lines.append(f"{mark} {row['date']}  —  {reason}")
    return "\n".join(lines)


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
