"""Tests for life-area insights engine."""

import os
import sys
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from insights.engine import analyze_all, analyze_category, analyze_cross_category, top_insights  # noqa: E402
from insights.playbooks import PLAYBOOKS  # noqa: E402
from personal_dev_tracker import PersonalDevelopmentTracker  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402


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

    def test_default_categories_include_consumption_areas(self) -> None:
        tracker = MagicMock()
        defaults = PersonalDevelopmentTracker.get_default_categories(tracker)
        self.assertGreaterEqual(len(defaults), 18)
        for name in (
            "Career & Vocation",
            "Learning & Intellectual Growth",
            "Relationships & Social Connection",
            "Cultural Life & Heritage",
            "Home & Environment",
            "Community & Service",
            "What You Have Eaten",
            "Art You Have Consumed",
            "Content You Have Consumed",
            "General Reading",
        ):
            self.assertIn(name, defaults)
            self.assertIn(name, PLAYBOOKS)

    def test_merge_appends_new_checklist_items(self) -> None:
        tracker = MagicMock()
        defaults = PersonalDevelopmentTracker.get_default_categories(tracker)
        tracker.get_default_categories.return_value = defaults
        stored = {
            "Body & Presence": {
                "checklist": ["Completed movement/exercise"],
                "metrics": defaults["Body & Presence"]["metrics"],
            }
        }
        merged = PersonalDevelopmentTracker.merge_categories_with_defaults(tracker, stored)
        body_checklist = merged["Body & Presence"]["checklist"]
        self.assertIn("Completed movement/exercise", body_checklist)
        self.assertIn("Prioritized sleep or recovery", body_checklist)
        self.assertGreater(len(body_checklist), 1)

    def test_merge_adds_new_default_categories(self) -> None:
        tracker = MagicMock()
        defaults = PersonalDevelopmentTracker.get_default_categories(tracker)
        tracker.get_default_categories.return_value = defaults
        stored = {"Body & Presence": defaults["Body & Presence"]}
        merged = PersonalDevelopmentTracker.merge_categories_with_defaults(tracker, stored)
        self.assertIn("What You Have Eaten", merged)
        self.assertEqual(len(merged), len(defaults))

    def test_cross_category_food_when_body_low(self) -> None:
        tracker = MagicMock()
        categories = {
            "Body & Presence": DEFAULT_CATEGORIES["Body & Presence"],
            "What You Have Eaten": PersonalDevelopmentTracker.get_default_categories(tracker)["What You Have Eaten"],
        }
        entries = {}
        for day in range(1, 8):
            entries[f"2026-07-{day:02d}"] = {
                "Body & Presence": {"rating": 4, "checklist": {}, "metrics": {}, "notes": ""},
            }
        insights = analyze_cross_category(entries, categories, date(2026, 7, 7))
        titles = [item.title for item in insights]
        self.assertIn("Body struggling — food not logged", titles)


if __name__ == "__main__":
    unittest.main()
