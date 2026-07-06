from datetime import date

from activity_grid import activity_level, build_week_columns, day_activity_count


def test_activity_level_one_is_green():
    assert activity_level(1) >= 1
    assert activity_level(1, max_categories=18) == 1


def test_today_counts_logged_life_area():
    today = date.today()
    entries = {today.strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 7}}}
    assert day_activity_count(entries, today) == 1


def test_build_week_columns_includes_today():
    today = date.today()
    weeks = build_week_columns(end=today, num_weeks=53)
    flat = [day for week in weeks for day in week if day is not None]
    assert today in flat
