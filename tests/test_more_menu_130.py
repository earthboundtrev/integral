"""Grouped More menu (#130)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import deep_work
from more_menu_ui import (
    LEGACY_FOOTER_LABELS,
    MORE_GROUPS,
    TODAY_MORE_MENU_LABELS,
    assert_legacy_features_reachable,
    build_more_menu_rows,
    theme_menu_label,
    typeahead_advance,
)


def test_MORE_GROUPS_has_three_sections_and_fourteen_actions():
    assert len(MORE_GROUPS) == 3
    titles = [g["title"] for g in MORE_GROUPS]
    assert titles == ["VIEW", "WORK MODES", "DATA & SETTINGS"]
    action_count = sum(len(g["items"]) for g in MORE_GROUPS)
    assert action_count == 14


def test_legacy_footer_and_today_more_reachability():
    assert_legacy_features_reachable()
    for label in LEGACY_FOOTER_LABELS:
        assert label in LEGACY_FOOTER_LABELS  # sanity
    for label in TODAY_MORE_MENU_LABELS:
        assert label in TODAY_MORE_MENU_LABELS


def test_theme_menu_label_follows_mode():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    assert theme_menu_label(tracker) == "Dark Mode"
    tracker.settings = {"dark_mode": True}
    assert theme_menu_label(tracker) == "Light Mode"


def test_deep_work_hides_distractions_in_more_menu():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = MagicMock()
    tracker._deep_work_session.running = True
    labels = [row.label for row in build_more_menu_rows(tracker)]
    assert "Refresh" in labels
    assert "AI Insight" in labels
    assert "Guidance" not in labels
    assert "Export" not in labels
    assert theme_menu_label(tracker) not in labels


def test_typeahead_finds_next_matching_row():
    tracker = MagicMock()
    tracker.settings = {"dark_mode": False}
    tracker._deep_work_session = None
    rows = build_more_menu_rows(tracker)
    idx = typeahead_advance(rows, 0, "gu")
    assert idx is not None
    assert rows[idx].label == "Guidance"


def test_deep_work_more_label_sets():
    assert "Guidance" in deep_work.DEEP_WORK_HIDDEN_MORE_LABELS
    assert "Refresh" in deep_work.DEEP_WORK_KEEP_MORE_LABELS
