"""Tests for Deep Work Mode timer and settings (SPEC-305)."""

from __future__ import annotations

import deep_work as dw


def test_start_session_and_tick_to_completion():
    session = dw.start_session(1)  # 60 seconds
    assert session.running
    assert session.remaining_seconds == 60
    assert session.format_mmss() == "01:00"
    done = False
    for _ in range(59):
        done = session.tick(1)
        assert not done
    done = session.tick(1)
    assert done
    assert session.completed
    assert not session.running
    assert session.remaining_seconds == 0


def test_tick_with_injected_large_step():
    session = dw.start_session(2)
    assert session.tick(120) is True
    assert session.completed


def test_extend_and_cancel():
    session = dw.start_session(1)
    session.tick(30)
    session.extend(10)
    assert session.running
    assert session.remaining_seconds == 30 + 10 * 60
    session.cancel()
    assert not session.running
    assert session.remaining_seconds == 0


def test_normalize_deep_work_settings():
    assert dw.normalize_deep_work_settings(None)["last_minutes"] == dw.DEFAULT_MINUTES
    settings = dw.apply_deep_work_settings({}, {"last_minutes": 90, "reduce_chrome": False})
    assert settings["deep_work"]["last_minutes"] == 90
    assert settings["deep_work"]["reduce_chrome"] is False


def test_normalize_clamps_invalid_minutes():
    assert dw.normalize_deep_work_settings({"deep_work": {"last_minutes": 0}})["last_minutes"] == 1
    assert dw.normalize_deep_work_settings({"deep_work": {"last_minutes": "nope"}})[
        "last_minutes"
    ] == dw.DEFAULT_MINUTES


def test_chrome_policy_sets():
    assert "Graphs & Progress" in dw.DEEP_WORK_HIDDEN_NAV_LABELS
    assert "Writing Projects" in dw.DEEP_WORK_KEEP_NAV_LABELS
    assert "Journal" in dw.DEEP_WORK_KEEP_NAV_LABELS
