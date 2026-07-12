"""Tests for Creative/Mental Work writing integration (SPEC-304)."""

from __future__ import annotations

import creative_projects as cp


def test_mark_writing_session_sets_checklist():
    categories = {
        cp.CREATIVE_CATEGORY: {
            "checklist": [cp.CREATIVE_PROGRESS_ITEM, "Other"],
            "metrics": [],
        }
    }
    entries: dict = {}
    ok, message = cp.mark_writing_session(entries, categories, "2026-07-12")
    assert ok
    assert "Logged writing progress" in message
    entry = entries["2026-07-12"][cp.CREATIVE_CATEGORY]
    assert entry["checklist"][cp.CREATIVE_PROGRESS_ITEM] is True
    assert entry["rating"] == 5


def test_mark_writing_session_missing_checklist_item():
    categories = {cp.CREATIVE_CATEGORY: {"checklist": ["Something else"], "metrics": []}}
    entries: dict = {}
    ok, message = cp.mark_writing_session(entries, categories, "2026-07-12")
    assert not ok
    assert "Checklist item" in message
    assert entries == {}


def test_mark_writing_session_missing_category():
    ok, message = cp.mark_writing_session({}, {}, "2026-07-12")
    assert not ok
    assert "not in your profile" in message


def test_creative_category_name_unchanged():
    assert cp.CREATIVE_CATEGORY == "Creative/Mental Work"
