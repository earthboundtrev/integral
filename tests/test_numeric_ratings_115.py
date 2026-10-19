from datetime import datetime, timedelta

from summaries import _ratings_for_dates, build_summary_text


def _today():
    return datetime.now().date()


def test_null_and_non_numeric_ratings_are_skipped_in_week_summary():
    today = _today().strftime("%Y-%m-%d")
    entries = {
        today: {
            "fitness": {"rating": 8},
            "food": {"rating": None},
            "sleep": {"rating": "abc"},
            "todo": {},
        }
    }
    ratings, active_days = _ratings_for_dates(entries, _today() - timedelta(days=7))
    assert ratings == [8]
    assert active_days == 1


def test_build_summary_text_does_not_crash_on_null_rating():
    today = _today().strftime("%Y-%m-%d")
    entries = {today: {"fitness": {"rating": None}, "food": {"rating": 6}}}
    text = build_summary_text(entries)
    assert "Average rating: 6.0/10" in text


def test_daily_average_chart_skips_null_ratings():
    from charts import build_daily_avg_figure

    today = _today().strftime("%Y-%m-%d")
    entries = {today: {"fitness": {"rating": None}, "food": {"rating": "x"}}}
    build_daily_avg_figure(entries)


def test_category_average_chart_skips_null_ratings():
    from charts import build_category_avg_figure

    today = _today().strftime("%Y-%m-%d")
    entries = {today: {"fitness": {"rating": None}, "food": {"rating": 4}}}
    build_category_avg_figure(entries, {"fitness": {}, "food": {}})
