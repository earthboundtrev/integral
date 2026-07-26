"""SPEC-325 — low-friction today presence copy."""

from unittest.mock import MagicMock

from personal_dev_tracker import PersonalDevelopmentTracker


def test_format_today_presence_never_scores_completeness():
    tracker = MagicMock()
    tracker.count_today_logged.return_value = (0, 18)
    assert "/" not in PersonalDevelopmentTracker.format_today_presence_line(tracker)
    assert "enough" in PersonalDevelopmentTracker.format_today_presence_line(tracker).lower()

    tracker.count_today_logged.return_value = (1, 18)
    line = PersonalDevelopmentTracker.format_today_presence_line(tracker)
    assert "1 check-in" in line
    assert "complete honest day" in line
    assert "/18" not in line

    tracker.count_today_logged.return_value = (3, 18)
    line = PersonalDevelopmentTracker.format_today_presence_line(tracker)
    assert "3 check-ins" in line
    assert "only if you want" in line
