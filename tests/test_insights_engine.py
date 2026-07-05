"""Tests for life-area insights engine."""

import os
import sys
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from insights.engine import analyze_all, analyze_category, top_insights  # noqa: E402


DEFAULT_CATEGORIES = {
    "Body & Presence": {
        "checklist": ["Completed movement/exercise"],
        "metrics": [{"name": "Energy level", "type": "rating", "min": 1, "max": 10, "default": 5}],
    },
    "Burnout Prevention & Energy Management": {
        "checklist": ["Took intentional breaks"],
        "metrics": [
            {"name": "Morning energy", "type": "rating", "min": 1, "max": 10, "default": 5},
            {"name": "Stress level (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5},
        ],
    },
}


class TestInsights(unittest.TestCase):
    def test_detects_neglected_category(self) -> None:
        entries = {
            "2026-06-20": {"Burnout Prevention & Energy Management": {"rating": 6, "checklist": {}, "metrics": {}, "notes": ""}},
        }
        insights = analyze_category(
            "Burnout Prevention & Energy Management",
            DEFAULT_CATEGORIES["Burnout Prevention & Energy Management"],
            entries,
            date(2026, 7, 5),
        )
        titles = [item.title for item in insights]
        self.assertIn("Maintenance gap", titles)

    def test_detects_declining_trend(self) -> None:
        entries = {}
        for day in range(1, 8):
            entries[f"2026-07-{day:02d}"] = {
                "Body & Presence": {"rating": 8, "checklist": {}, "metrics": {}, "notes": ""},
            }
        for day in range(8, 15):
            entries[f"2026-07-{day:02d}"] = {
                "Body & Presence": {"rating": 4, "checklist": {}, "metrics": {}, "notes": ""},
            }
        insights = analyze_category(
            "Body & Presence",
            DEFAULT_CATEGORIES["Body & Presence"],
            entries,
            date(2026, 7, 14),
        )
        self.assertTrue(any(item.title == "Declining trend" for item in insights))

    def test_top_insights_prioritizes_action(self) -> None:
        entries = {
            "2026-07-04": {"Body & Presence": {"rating": 3, "checklist": {}, "metrics": {}, "notes": ""}},
        }
        insights = analyze_all(entries, DEFAULT_CATEGORIES, today=date(2026, 7, 5))
        top = top_insights(insights, limit=2)
        self.assertTrue(top)
        self.assertIn(top[0].severity, ("action", "watch"))


if __name__ == "__main__":
    unittest.main()
