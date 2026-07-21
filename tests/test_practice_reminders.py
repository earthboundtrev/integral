"""SPEC-320 practice reminders + consistency guidance."""

from datetime import date, datetime, timedelta

import notifications
from insights.engine import analyze_practice_consistency


def _settings(reminders):
    return {"notifications": {"enabled": True, "practice_reminders": reminders}}


def test_normalize_practice_reminders_filters_invalid():
    settings = _settings(
        [
            {"label": "Rites", "time": "07:00", "enabled": True},
            {"label": "", "time": "08:00"},            # no label
            {"label": "Breathing", "time": "99:99"},    # bad time
            {"label": "Rites", "time": "07:00"},        # duplicate
            "nonsense",
        ]
    )
    normalized = notifications.normalize_notification_settings(settings)
    reminders = normalized["notifications"]["practice_reminders"]
    assert len(reminders) == 1
    assert reminders[0]["label"] == "Rites"
    assert reminders[0]["enabled"] is True


def test_due_practice_reminder_fires_at_time():
    settings = _settings([{"label": "Five Tibetan Rites", "time": "07:00", "enabled": True}])
    before = notifications.due_practice_reminders(
        settings, now=datetime(2026, 7, 21, 6, 30)
    )
    assert before == []
    after = notifications.due_practice_reminders(
        settings, now=datetime(2026, 7, 21, 7, 5)
    )
    assert len(after) == 1
    key, title, message = after[0]
    assert "Five Tibetan Rites" in message
    assert key == notifications.practice_reminder_key("Five Tibetan Rites", "07:00")


def test_due_practice_reminder_respects_sent_state_and_disabled():
    settings = _settings([{"label": "Breathing", "time": "07:00", "enabled": True}])
    now = datetime(2026, 7, 21, 7, 5)
    due = notifications.due_practice_reminders(settings, now=now)
    key = due[0][0]
    settings = notifications.record_sent_reminders(settings, [key], today=now.date())
    assert notifications.due_practice_reminders(settings, now=now) == []

    off = _settings([{"label": "Breathing", "time": "07:00", "enabled": False}])
    assert notifications.due_practice_reminders(off, now=now) == []


def _day(base: date, offset: int) -> str:
    return (base - timedelta(days=offset)).strftime("%Y-%m-%d")


def test_consistency_positive_when_frequent():
    today = date(2026, 7, 21)
    store = {"items": [{"date": _day(today, o), "name": "Rites"} for o in range(0, 5)]}
    findings = analyze_practice_consistency(store, today)
    assert any(f.severity == "positive" and "Rites" in f.message for f in findings)


def test_consistency_watch_when_stalled():
    today = date(2026, 7, 21)
    # Last practice 10 days ago → nothing in the last 7.
    store = {"items": [{"date": _day(today, 10), "name": "Rites"}]}
    findings = analyze_practice_consistency(store, today)
    assert any(f.severity == "watch" and "stalled" in f.title.lower() for f in findings)


def test_consistency_empty_store():
    assert analyze_practice_consistency({"items": []}, date(2026, 7, 21)) == []
