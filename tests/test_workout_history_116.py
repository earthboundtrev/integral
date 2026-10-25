"""Tests for workout history feature (#116)."""

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from progression.db import FitnessRepository
from progression.models import Exercise, WorkoutSession, WorkoutSet
from progression.sessions import create_workout_session


class TestWorkoutHistoryPaging(unittest.TestCase):
    """Test keyset paging for workout history."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.repo = FitnessRepository(db_path=self.temp_db.name)
        self.repo.initialize()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_keyset_paging_basic(self):
        """Test that keyset paging returns correct number of sessions."""
        for i in range(50):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            session = WorkoutSession(date=date)
            self.repo.add_workout_session(session)

        first_page = self.repo.list_workout_sessions_page(limit=20)
        self.assertEqual(len(first_page), 20)

        second_page = self.repo.list_workout_sessions_page(
            limit=20,
            before_date=first_page[-1].date,
            before_id=first_page[-1].id,
        )
        self.assertEqual(len(second_page), 20)

        third_page = self.repo.list_workout_sessions_page(
            limit=20,
            before_date=second_page[-1].date,
            before_id=second_page[-1].id,
        )
        self.assertEqual(len(third_page), 10)

    def test_no_duplicates_or_gaps_same_date(self):
        """Test keyset paging with multiple sessions on the same date."""
        date = datetime.now().strftime("%Y-%m-%d")
        session_ids = []
        for i in range(30):
            session = WorkoutSession(date=date, notes=f"Session {i}")
            self.repo.add_workout_session(session)
            session_ids.append(session.id)

        all_sessions = []
        page = self.repo.list_workout_sessions_page(limit=10)
        all_sessions.extend(page)

        while len(page) == 10:
            page = self.repo.list_workout_sessions_page(
                limit=10,
                before_date=page[-1].date,
                before_id=page[-1].id,
            )
            all_sessions.extend(page)

        retrieved_ids = [s.id for s in all_sessions]
        self.assertEqual(len(retrieved_ids), 30)
        self.assertEqual(len(set(retrieved_ids)), 30)  # No duplicates
        self.assertEqual(set(retrieved_ids), set(session_ids))  # No gaps

    def test_all_sessions_reachable(self):
        """Test that all sessions can be reached through paging (AC: every session is reachable)."""
        for i in range(120):
            date = (datetime.now() - timedelta(days=i // 3)).strftime("%Y-%m-%d")
            session = WorkoutSession(date=date, notes=f"Session {i}")
            self.repo.add_workout_session(session)

        all_sessions = []
        page = self.repo.list_workout_sessions_page(limit=20)
        all_sessions.extend(page)

        while len(page) == 20:
            page = self.repo.list_workout_sessions_page(
                limit=20,
                before_date=page[-1].date,
                before_id=page[-1].id,
            )
            all_sessions.extend(page)

        self.assertEqual(len(all_sessions), 120)
        self.assertEqual(len(set(s.id for s in all_sessions)), 120)

    def test_exercise_filter(self):
        """Test filtering by exercise name."""
        ex1 = Exercise(id="ex1", name="Push-up", source_book="CC1", family="push", mastery_criteria={})
        ex2 = Exercise(id="ex2", name="Pull-up", source_book="CC1", family="pull", mastery_criteria={})
        self.repo.add_exercise(ex1)
        self.repo.add_exercise(ex2)

        for i in range(10):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            session = WorkoutSession(date=date)
            self.repo.add_workout_session(session)

            if i % 2 == 0:
                wset = WorkoutSet(session_id=session.id, exercise_id="ex1", sets=3, reps=10)
                self.repo.add_workout_set(wset)
            else:
                wset = WorkoutSet(session_id=session.id, exercise_id="ex2", sets=3, reps=5)
                self.repo.add_workout_set(wset)

        push_sessions = self.repo.list_workout_sessions_page(limit=20, exercise_filter="Push")
        self.assertEqual(len(push_sessions), 5)

        pull_sessions = self.repo.list_workout_sessions_page(limit=20, exercise_filter="Pull")
        self.assertEqual(len(pull_sessions), 5)


class TestDatabaseSchema(unittest.TestCase):
    """Test database schema updates for workout history."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.repo = FitnessRepository(db_path=self.temp_db.name)
        self.repo.initialize()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_workout_sets_has_ordinal_and_created_at(self):
        """Test that workout_sets table has ordinal and created_at columns."""
        with self.repo.connect() as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(workout_sets)").fetchall()
            }
            self.assertIn("ordinal", columns)
            self.assertIn("created_at", columns)
            self.assertIn("form_quality", columns)

    def test_workout_sessions_has_created_at(self):
        """Test that workout_sessions table has created_at column."""
        with self.repo.connect() as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(workout_sessions)").fetchall()
            }
            self.assertIn("created_at", columns)

    def test_exercise_id_index_exists(self):
        """Test that index on workout_sets(exercise_id) exists."""
        with self.repo.connect() as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='workout_sets'"
            ).fetchall()
            index_names = [row["name"] for row in indexes]
            self.assertIn("idx_workout_sets_exercise", index_names)

    def test_ordinal_preserves_order(self):
        """Test that exercises show in logged order using ordinal."""
        ex1 = Exercise(id="ex1", name="Exercise 1", source_book="CC1", family="push", mastery_criteria={})
        ex2 = Exercise(id="ex2", name="Exercise 2", source_book="CC1", family="pull", mastery_criteria={})
        ex3 = Exercise(id="ex3", name="Exercise 3", source_book="CC1", family="core", mastery_criteria={})
        self.repo.add_exercise(ex1)
        self.repo.add_exercise(ex2)
        self.repo.add_exercise(ex3)

        session_date = datetime.now().strftime("%Y-%m-%d")
        sets_data = [
            {"exercise_id": "ex3", "sets": 1, "reps": 10},
            {"exercise_id": "ex1", "sets": 2, "reps": 20},
            {"exercise_id": "ex2", "sets": 3, "reps": 30},
        ]

        session = create_workout_session(
            self.repo,
            date=session_date,
            sets_data=sets_data,
        )

        sets = self.repo.list_workout_sets(session.id)
        self.assertEqual(len(sets), 3)
        self.assertEqual(sets[0].exercise_id, "ex3")
        self.assertEqual(sets[1].exercise_id, "ex1")
        self.assertEqual(sets[2].exercise_id, "ex2")


class TestBatchLoading(unittest.TestCase):
    """Test batch loading of workout sets."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.repo = FitnessRepository(db_path=self.temp_db.name)
        self.repo.initialize()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_batch_loading_performance(self):
        """Test that batch loading uses fewer queries than individual loads."""
        ex = Exercise(id="ex1", name="Exercise 1", source_book="CC1", family="push", mastery_criteria={})
        self.repo.add_exercise(ex)

        session_ids = []
        for i in range(10):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            sets_data = [
                {"exercise_id": "ex1", "sets": 3, "reps": 10},
            ]
            session = create_workout_session(self.repo, date=date, sets_data=sets_data)
            session_ids.append(session.id)

        # Test batch loading
        sets_dict = self.repo.list_workout_sets_batch(session_ids)
        self.assertEqual(len(sets_dict), 10)
        for sid in session_ids:
            self.assertIn(sid, sets_dict)
            self.assertEqual(len(sets_dict[sid]), 1)

    def test_batch_loading_with_trace(self):
        """Test that batch loading uses ≤3 queries per page (AC: ≤3 SQL queries)."""
        ex = Exercise(id="ex1", name="Exercise 1", source_book="CC1", family="push", mastery_criteria={})
        self.repo.add_exercise(ex)

        for i in range(20):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            sets_data = [
                {"exercise_id": "ex1", "sets": 3, "reps": 10},
            ]
            create_workout_session(self.repo, date=date, sets_data=sets_data)

        query_count = 0

        def trace_callback(statement):
            nonlocal query_count
            if not statement.strip().startswith("PRAGMA"):
                query_count += 1

        with self.repo.connect() as conn:
            conn.set_trace_callback(trace_callback)

            # Load first page
            sessions = self.repo.list_workout_sessions_page(limit=20)
            session_ids = [s.id for s in sessions]
            sets_dict = self.repo.list_workout_sets_batch(session_ids)

            conn.set_trace_callback(None)

        # Should be: 1 query for sessions + 1 query for batch sets = 2 total
        # Plus any initialize() calls
        self.assertLessEqual(query_count, 3)


@unittest.skipIf(not os.getenv("DISPLAY"), "Requires X display for tkinter")
class TestWorkoutHistoryUI(unittest.TestCase):
    """Test workout history UI components."""

    def test_format_date_display(self):
        """Test date formatting."""
        try:
            from workout_history_ui import format_date_display
        except ImportError:
            self.skipTest("tkinter not available")

        result = format_date_display("2026-10-14")
        self.assertIn("Oct", result)
        self.assertIn("14", result)

    def test_format_month_header(self):
        """Test month header formatting."""
        try:
            from workout_history_ui import format_month_header
        except ImportError:
            self.skipTest("tkinter not available")

        result = format_month_header("2026-10-14")
        self.assertIn("October", result)
        self.assertIn("2026", result)

    def test_calculate_session_volume(self):
        """Test volume calculation for weighted exercises."""
        try:
            from workout_history_ui import calculate_session_volume
        except ImportError:
            self.skipTest("tkinter not available")

        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        repo = FitnessRepository(db_path=temp_db.name)
        repo.initialize()

        try:
            sets = [
                WorkoutSet(
                    session_id="s1",
                    exercise_id="ex1",
                    sets=3,
                    reps=10,
                    weight_kg=50.0,
                ),
                WorkoutSet(
                    session_id="s1",
                    exercise_id="ex2",
                    sets=2,
                    reps=5,
                    weight_kg=100.0,
                ),
            ]

            volume, unit, weighted_count = calculate_session_volume(sets, repo)
            self.assertEqual(unit, "kg")
            self.assertEqual(weighted_count, 2)
            # 3*10*50 + 2*5*100 = 1500 + 1000 = 2500
            self.assertEqual(volume, 2500.0)
        finally:
            os.unlink(temp_db.name)

    def test_load_more_button_visible_when_has_more(self):
        """Regression (#116): Load more must show after first page while has_more is True."""
        try:
            import tkinter as tk

            from theme import get_theme
            from workout_history_ui import WorkoutHistoryView
        except ImportError:
            self.skipTest("tkinter not available")

        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        repo = FitnessRepository(db_path=temp_db.name)
        repo.initialize()

        root = tk.Tk()
        root.withdraw()
        try:
            for i in range(130):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                repo.add_workout_session(WorkoutSession(date=date))

            view = WorkoutHistoryView(root, repo, get_theme(False))
            view._do_load_first_page()
            root.update_idletasks()

            self.assertTrue(view.has_more)
            self.assertFalse(view.is_loading)
            self.assertEqual(len(view.sessions), 20)
            self.assertEqual(view.load_more_btn.winfo_manager(), "pack")
        finally:
            root.destroy()
            os.unlink(temp_db.name)

    def test_calculate_bodyweight_volume(self):
        """Test volume calculation for bodyweight exercises."""
        try:
            from workout_history_ui import calculate_session_volume
        except ImportError:
            self.skipTest("tkinter not available")

        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        repo = FitnessRepository(db_path=temp_db.name)
        repo.initialize()

        try:
            sets = [
                WorkoutSet(
                    session_id="s1",
                    exercise_id="ex1",
                    sets=3,
                    reps=10,
                ),
            ]

            volume, unit, weighted_count = calculate_session_volume(sets, repo)
            self.assertEqual(unit, "")
            self.assertEqual(weighted_count, 0)
            self.assertEqual(volume, 0.0)
        finally:
            os.unlink(temp_db.name)


class TestRemovedExercise(unittest.TestCase):
    """Test handling of removed/renamed exercises."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.repo = FitnessRepository(db_path=self.temp_db.name)
        self.repo.initialize()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_removed_exercise_shows_id_and_removed(self):
        """Test that workout history gracefully handles deleted exercises."""
        ex = Exercise(id="ex1", name="Old Exercise", source_book="CC1", family="push", mastery_criteria={})
        self.repo.add_exercise(ex)

        session_date = datetime.now().strftime("%Y-%m-%d")
        sets_data = [{"exercise_id": "ex1", "sets": 3, "reps": 10}]
        session = create_workout_session(self.repo, date=session_date, sets_data=sets_data)

        # Delete the exercise using UPDATE (soft delete simulation)
        with self.repo.connect() as conn:
            conn.execute(
                "UPDATE exercises SET deleted_at = ? WHERE id = ?",
                (datetime.now().isoformat(), "ex1"),
            )

        # Fetching exercise should return None for deleted
        deleted_ex = self.repo.get_exercise("ex1")
        self.assertIsNone(deleted_ex)

        # Workout history should still work - sets reference the exercise
        sets = self.repo.list_workout_sets(session.id)
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0].exercise_id, "ex1")


class TestListWorkoutSessionsUnchanged(unittest.TestCase):
    """Test that other callers of list_workout_sessions are unchanged."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.repo = FitnessRepository(db_path=self.temp_db.name)
        self.repo.initialize()

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    def test_list_workout_sessions_still_works(self):
        """Test that list_workout_sessions() still returns sessions correctly."""
        for i in range(60):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            session = WorkoutSession(date=date)
            self.repo.add_workout_session(session)

        # Default limit is 50
        sessions = self.repo.list_workout_sessions()
        self.assertEqual(len(sessions), 50)

        # Custom limit
        sessions = self.repo.list_workout_sessions(limit=20)
        self.assertEqual(len(sessions), 20)


if __name__ == "__main__":
    unittest.main()
