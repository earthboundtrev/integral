"""Go to… palette destination smoke tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from goto_ui import build_goto_destinations, filter_goto_destinations


class TestGotoUi(unittest.TestCase):
    def test_overview_categories_destination_opens_streak_details(self):
        tracker = SimpleNamespace(
            show_streak_details=MagicMock(),
            refresh_dashboard=MagicMock(),
            show_guidance=MagicMock(),
            show_weekly_summary=MagicMock(),
            _show_ai_insight=MagicMock(),
            show_history=MagicMock(),
            show_search=MagicMock(),
            show_graphs=MagicMock(),
            show_journal=MagicMock(),
            show_writing_projects=MagicMock(),
            show_deep_work=MagicMock(),
            toggle_quick_capture=MagicMock(),
            show_plan_tomorrow=MagicMock(),
            show_log_exercise=MagicMock(),
            show_fitness_hub=MagicMock(),
            show_milestones=MagicMock(),
            show_export=MagicMock(),
            show_backup=MagicMock(),
            show_settings=MagicMock(),
            show_security=MagicMock(),
            toggle_dark_mode=MagicMock(),
            open_log_dialog=MagicMock(),
            categories={"Body & Presence": {}, "Food": {}},
        )

        destinations = build_goto_destinations(tracker)
        labels = [d["label"] for d in destinations]
        self.assertIn("Overview & Categories", labels)
        self.assertNotIn("Streak details", labels)

        overview = next(d for d in destinations if d["label"] == "Overview & Categories")
        overview["action"]()
        tracker.show_streak_details.assert_called()

        matched = filter_goto_destinations(destinations, "overview")
        self.assertTrue(any(d["label"] == "Overview & Categories" for d in matched))


if __name__ == "__main__":
    unittest.main()
