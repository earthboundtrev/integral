"""Tests for fitness intelligence helpers."""

import unittest

from fitness.intelligence import (
    classify_metric_trend,
    compute_development_scores,
    get_fitness_settings,
    metric_total,
    smart_defaults_for_program,
    tibetan_consecutive_success_days,
    weekly_fitness_summary,
)


class IntelligenceTests(unittest.TestCase):
    def test_metric_total_reps(self) -> None:
        self.assertEqual(metric_total({"reps_per_set": [10, 12, 8]}), 30.0)

    def test_classify_improving(self) -> None:
        logs = [{"reps_per_set": [5]}, {"reps_per_set": [8]}, {"reps_per_set": [12]}]
        self.assertEqual(classify_metric_trend(logs), "improving")

    def test_tibetan_streak(self) -> None:
        from datetime import datetime, timedelta

        program = {
            "movements": [{"id": "r1"}, {"id": "r2"}],
            "rules": {"start_reps_per_rite": 3},
        }
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        sessions = [
            {
                "date": yesterday.strftime("%Y-%m-%d"),
                "movement_logs": [{"target_reps": 3, "reps_per_rite": {"r1": 3, "r2": 3}}],
            },
            {
                "date": today.strftime("%Y-%m-%d"),
                "movement_logs": [{"target_reps": 3, "reps_per_rite": {"r1": 3, "r2": 3}}],
            },
        ]
        result = tibetan_consecutive_success_days(sessions, program, 3)
        self.assertGreaterEqual(result, 2)

    def test_smart_defaults_cc(self) -> None:
        program = {
            "id": "convict-conditioning",
            "progression_model": "step_ladder",
            "movements": [{"id": "pushups", "steps": [{"name": "Wall"}]}],
        }
        defaults = smart_defaults_for_program(program, [], {})
        self.assertEqual(defaults["movement_key"], "pushups")
        self.assertEqual(defaults["step"], 1)

    def test_development_scores(self) -> None:
        programs = {"p1": {"id": "p1", "name": "Test", "progression_model": "step_ladder"}}
        scores = compute_development_scores(programs, [], {})
        self.assertIn("p1", scores)
        self.assertGreaterEqual(scores["p1"], 0)

    def test_weekly_summary_empty(self) -> None:
        text = weekly_fitness_summary([], {}, ["2026-07-01"])
        self.assertIn("No fitness sessions", text)

    def test_fitness_settings_merge(self) -> None:
        settings = get_fitness_settings({"fitness": {"cc_sessions_for_advance": 3}})
        self.assertEqual(settings["cc_sessions_for_advance"], 3)
        self.assertEqual(settings["tibetan_advance_consecutive_days"], 7)


if __name__ == "__main__":
    unittest.main()
