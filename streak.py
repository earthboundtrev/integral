from datetime import datetime, timedelta


def get_streak(entries, category=None):
    if not entries:
        return 0

    relevant_dates = []
    for date_str, day_entries in entries.items():
        if category is None:
            if day_entries:
                relevant_dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
        elif category in day_entries:
            relevant_dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())

    if not relevant_dates:
        return 0

    sorted_dates = sorted(relevant_dates, reverse=True)
    streak = 0
    expected = datetime.now().date()
    for day in sorted_dates:
        if day == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif day < expected:
            break
    return streak
