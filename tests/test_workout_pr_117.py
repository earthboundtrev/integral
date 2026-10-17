"""Tests for workout PR badges and per-exercise history (#117)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta

from progression.db import FitnessRepository
from progression.models import Exercise, UserExerciseProgress, WorkoutSession, WorkoutSet
from progression.sessions import create_workout_session
from progression.workout_pr import (
    ExerciseBests,
    aggregate_bests_from_sets,
    classify_set_pr,
    pr_badges_for_sets,
    pr_badge_label,
    resolve_display_bests,
    stored_bests_consistent,
    update_rolling_bests,
)
from workout_history_sparkline import (
    format_metric_number,
    sparkline_accessibility_summary,
)


def _set(**kwargs) -> WorkoutSet:
    return WorkoutSet(id="s1", session_id="sess", exercise_id="ex1", **kwargs)


class TestPrBadgeLogic(unittest.TestCase):
    def test_beat_weight(self):
        prior = ExerciseBests(best_weight=50.0, best_reps=5)
        self.assertEqual(classify_set_pr(_set(weight_kg=52.0, reps=3), prior), "beat")

    def test_tie_weight_and_reps(self):
        prior = ExerciseBests(best_weight=50.0, best_reps=5)
        self.assertEqual(classify_set_pr(_set(weight_kg=50.0, reps=5), prior), "tie")

    def test_weight_tie_fewer_reps_still_equal_pr(self):
        prior = ExerciseBests(best_weight=50.0, best_reps=10)
        self.assertEqual(classify_set_pr(_set(weight_kg=50.0, reps=6), prior), "tie")

    def test_reps_only_beat_and_tie(self):
        prior = ExerciseBests(best_reps=8)
        self.assertEqual(classify_set_pr(_set(reps=10), prior), "beat")
        self.assertEqual(classify_set_pr(_set(reps=8), prior), "tie")
        self.assertEqual(classify_set_pr(_set(reps=6), prior), "none")

    def test_hold_seconds(self):
        prior = ExerciseBests(best_hold_time=30.0)
        self.assertEqual(classify_set_pr(_set(hold_seconds=35.0), prior), "beat")
        self.assertEqual(classify_set_pr(_set(hold_seconds=30.0), prior), "tie")

    def test_two_sets_both_beat_old_best(self):
        prior = ExerciseBests(best_reps=5)
        sets = [_set(reps=6), _set(reps=8)]
        badges = pr_badges_for_sets(sets, prior)
        self.assertEqual(badges, ["beat", "beat"])

    def test_badge_labels(self):
        self.assertEqual(pr_badge_label("beat"), "PR")
        self.assertEqual(pr_badge_label("tie"), "=PR")
        self.assertEqual(pr_badge_label("none"), "")


class TestStoredBestsConsistency(unittest.TestCase):
    def test_resolve_prefers_stored_when_consistent(self):
        stored = ExerciseBests(best_reps=10)
        computed = ExerciseBests(best_reps=10)
        self.assertTrue(stored_bests_consistent(stored, computed))
        self.assertEqual(resolve_display_bests(stored, computed).best_reps, 10)

    def test_resolve_uses_history_when_stale(self):
        stored = ExerciseBests(best_reps=8)
        computed = ExerciseBests(best_reps=12)
        resolved = resolve_display_bests(stored, computed)
        self.assertEqual(resolved.best_reps, 12)


class TestExerciseHistoryQueries(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.repo = FitnessRepository(db_path=self.temp_db.name)
        self.repo.initialize()
        self.ex = Exercise(
            id="ex1",
            name="Pull-up",
            source_book="CC1",
            family="pull",
            mastery_criteria={},
        )
        self.repo.add_exercise(self.ex)

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_fetch_exercise_page_query_count(self):
        for i in range(25):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            create_workout_session(
                self.repo,
                date=date,
                sets_data=[{"exercise_id": "ex1", "sets": 1, "reps": 5 + i % 3}],
            )

        query_count = 0

        def trace(statement):
            nonlocal query_count
            if not statement.strip().upper().startswith("PRAGMA"):
                query_count += 1

        with self.repo.connect() as conn:
            conn.set_trace_callback(trace)
            self.repo.fetch_exercise_history_page("ex1", limit=20)
            conn.set_trace_callback(None)

        self.assertLessEqual(query_count, 3)

    def test_removed_exercise_still_lists_sessions(self):
        date = datetime.now().strftime("%Y-%m-%d")
        create_workout_session(
            self.repo,
            date=date,
            sets_data=[{"exercise_id": "ex1", "sets": 2, "reps": 6}],
        )
        with self.repo.connect() as conn:
            conn.execute(
                "UPDATE exercises SET deleted_at = ? WHERE id = ?",
                (datetime.now().isoformat(), "ex1"),
            )
        sessions, sets_map, name, _stored, _computed = self.repo.fetch_exercise_history_page("ex1")
        self.assertEqual(len(sessions), 1)
        self.assertIn("(removed)", name)
        self.assertEqual(len(sets_map[sessions[0].id]), 1)

    def test_prior_bests_before_session(self):
        d1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        d2 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        s1 = create_workout_session(
            self.repo, date=d1, sets_data=[{"exercise_id": "ex1", "reps": 5, "weight_kg": 20.0}]
        )
        s2 = create_workout_session(
            self.repo, date=d2, sets_data=[{"exercise_id": "ex1", "reps": 8, "weight_kg": 25.0}]
        )
        prior = self.repo.get_prior_bests_before_session(
            ["ex1"], s2.date, s2.created_at, s2.id
        )["ex1"]
        self.assertEqual(prior.best_reps, 5)
        self.assertEqual(prior.best_weight, 20.0)
        self.assertIsNotNone(s1.id)


class TestExerciseHistoryPerformance(unittest.TestCase):
    def test_heavy_dataset_page_fetch_under_100ms(self):
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        repo = FitnessRepository(db_path=temp_db.name)
        repo.initialize()
        ex = Exercise(id="hex", name="Heavy", source_book="CC1", family="push", mastery_criteria={})
        repo.add_exercise(ex)
        base = datetime.now()
        for i in range(1000):
            day = (base - timedelta(days=i)).strftime("%Y-%m-%d")
            sets_data = [
                {"exercise_id": "hex", "sets": 1, "reps": 5, "weight_kg": 20.0 + (j % 3)}
                for j in range(8)
            ]
            create_workout_session(repo, date=day, sets_data=sets_data)

        timings: list[float] = []
        for _ in range(5):
            t0 = time.perf_counter()
            repo.fetch_exercise_history_page("hex", limit=20)
            timings.append(time.perf_counter() - t0)
        timings.sort()
        median_ms = timings[2] * 1000.0
        try:
            os.unlink(temp_db.name)
        except Exception:
            pass
        self.assertLess(median_ms, 100.0, f"median fetch {median_ms:.1f} ms")


class TestSparklineSummary(unittest.TestCase):
    def test_locale_neutral_numbers(self):
        self.assertEqual(format_metric_number(62.5), "62.5")
        text = sparkline_accessibility_summary(
            [10.0, 12.5, 11.0],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
            "weighted",
        )
        self.assertIn("12.5 kg·vol", text)
        self.assertIn("10 kg·vol", text)


class TestRollingBests(unittest.TestCase):
    def test_update_rolling_weight_reps(self):
        prior = ExerciseBests(best_weight=40.0, best_reps=5)
        nxt = update_rolling_bests(prior, _set(weight_kg=45.0, reps=3))
        self.assertEqual(nxt.best_weight, 45.0)
        self.assertEqual(nxt.best_reps, 3)


if __name__ == "__main__":
    unittest.main()
