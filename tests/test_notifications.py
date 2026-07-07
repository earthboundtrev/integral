from datetime import date, datetime

from notifications import (
    due_reminders,
    mark_logged_once,
    normalize_notification_settings,
    record_sent_reminders,
    reset_reminder_state,
)


def test_normalize_notification_settings_adds_defaults():
    settings = normalize_notification_settings({"dark_mode": True})
    assert settings["dark_mode"] is True
    assert settings["notifications"]["enabled"] is True
    assert settings["notifications"]["reminder_times"] == ["09:00", "12:00", "15:00", "18:00"]


def test_due_reminders_before_first_log():
    settings = normalize_notification_settings({})
    now = datetime(2026, 7, 6, 15, 30)
    pending = due_reminders(settings, now=now, logged_today=False)
    keys = [item[0] for item in pending]
    assert keys == ["09:00", "12:00", "15:00"]


def test_due_reminders_after_first_log_only_end_of_day():
    settings = mark_logged_once(normalize_notification_settings({}), today=date(2026, 7, 6))
    now = datetime(2026, 7, 6, 15, 30)
    pending = due_reminders(settings, now=now, logged_today=True)
    assert pending == []

    evening = datetime(2026, 7, 6, 21, 5)
    pending = due_reminders(settings, now=evening, logged_today=True)
    assert len(pending) == 1
    assert pending[0][0] == "end:21:00"


def test_record_sent_reminders_prevents_duplicates():
    settings = normalize_notification_settings({})
    updated = record_sent_reminders(settings, ["09:00"], today=date(2026, 7, 6))
    again = due_reminders(updated, now=datetime(2026, 7, 6, 15, 30), logged_today=False)
    keys = [item[0] for item in again]
    assert "09:00" not in keys
    assert keys == ["12:00", "15:00"]


def test_reset_reminder_state_clears_day():
    settings = record_sent_reminders(
        mark_logged_once(normalize_notification_settings({}), today=date(2026, 7, 6)),
        ["09:00"],
        today=date(2026, 7, 6),
    )
    reset = reset_reminder_state(settings, today=date(2026, 7, 7))
    state = reset["notifications"]["reminder_state"]
    assert state["date"] == "2026-07-07"
    assert state["sent_keys"] == []
    assert state["logged_once"] is False
