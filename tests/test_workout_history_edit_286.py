"""Tests for in-place edit of saved workout sets (#286)."""

from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fitness.set_field_validation import (
    SetFieldValidationError,
    parse_optional_hold_text,
    parse_optional_weight_text,
    parse_required_reps,
)
from progression.db import FitnessRepository
from progression.models import Exercise, UserExerciseProgress, WorkoutSession, WorkoutSet
from progression.session_edit import (
    SessionEditPayload,
    SetEditPayload,
    build_session_edit_payload,
    update_saved_workout_session,
)
from progression.sessions import create_workout_session


def _temp_repo() -> tuple[FitnessRepository, str]:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    handle.close()
    repo = FitnessRepository(db_path=handle.name)
    repo.initialize()
    return repo, handle.name


def _dispose_temp_repo(repo: FitnessRepository | None, path: str) -> None:
    """Release Windows SQLite file locks before deleting the temp db."""
    if repo is not None:
        del repo
    gc.collect()
    try:
        os.unlink(path)
    except OSError:
        pass


class TestSetFieldValidation(unittest.TestCase):
    def test_weight_comma_decimal(self):
        self.assertEqual(parse_optional_weight_text("40,5"), 40.5)

    def test_weight_round_trip(self):
        self.assertEqual(parse_optional_weight_text("40.5"), 40.5)

    def test_weight_thousands_comma_rejected(self):
        with self.assertRaises(SetFieldValidationError):
            parse_optional_weight_text("1,000")

    def test_hold_thousands_comma_rejected(self):
        with self.assertRaises(SetFieldValidationError):
            parse_optional_hold_text("1,000")

    def test_reps_range_rejected(self):
        with self.assertRaises(SetFieldValidationError):
            parse_required_reps("8-10")


class TestUpdateSavedSession(unittest.TestCase):
    def setUp(self):
        self.repo, self.path = _temp_repo()
        self.ex_a = Exercise(id="ex_a", name="Bench", source_book="SS", family="push", mastery_criteria={})
        self.ex_b = Exercise(id="ex_b", name="Row", source_book="SS", family="pull", mastery_criteria={})
        self.repo.add_exercise(self.ex_a)
        self.repo.add_exercise(self.ex_b)
        self.session = WorkoutSession(
            date="2026-06-01",
            notes="Note",
            duration_minutes=30,
            created_at="2026-06-01T12:00:00+00:00",
        )
        self.repo.add_workout_session(self.session)
        self.set1 = WorkoutSet(
            id="set-1",
            session_id=self.session.id,
            exercise_id="ex_a",
            sets=3,
            reps=8,
            weight_kg=50.0,
            ordinal=0,
            created_at="2026-06-01T12:00:01+00:00",
        )
        self.set2 = WorkoutSet(
            id="set-2",
            session_id=self.session.id,
            exercise_id="ex_b",
            sets=3,
            reps=10,
            ordinal=1,
            created_at="2026-06-01T12:00:02+00:00",
        )
        self.repo.add_workout_set(self.set1)
        self.repo.add_workout_set(self.set2)
        self.repo.upsert_user_progress(
            UserExerciseProgress(
                exercise_id="ex_a",
                status="in_progress",
                best_weight=50.0,
                best_reps=8,
                last_logged_at="2026-06-01T12:00:00+00:00",
            )
        )

    def tearDown(self):
        _dispose_temp_repo(self.repo, self.path)

    def test_form_quality_preserved_when_editing_reps_only(self):
        self.set1 = WorkoutSet(
            id="set-1",
            session_id=self.session.id,
            exercise_id="ex_a",
            sets=3,
            reps=8,
            weight_kg=50.0,
            form_quality=7,
            ordinal=0,
        )
        self.set2 = WorkoutSet(
            id="set-2",
            session_id=self.session.id,
            exercise_id="ex_b",
            sets=3,
            reps=10,
            form_quality=9,
            ordinal=1,
        )
        with self.repo.connect() as conn:
            conn.execute("DELETE FROM workout_sets WHERE session_id = ?", (self.session.id,))
        self.repo.add_workout_set(self.set1)
        self.repo.add_workout_set(self.set2)
        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="Note",
            duration_minutes=30,
            body_weight_kg=None,
            sets=[
                SetEditPayload("set-1", "ex_a", 3, 12, None, 50.0),
                SetEditPayload("set-2", "ex_b", 3, 10, None, None),
            ],
        )
        update_saved_workout_session(self.repo, payload)
        by_id = {r.id: r for r in self.repo.list_workout_sets(self.session.id)}
        self.assertEqual(by_id["set-1"].reps, 12)
        self.assertEqual(by_id["set-1"].form_quality, 7)
        self.assertEqual(by_id["set-2"].form_quality, 9)

    def test_immutable_columns_unchanged_after_save(self):
        session_date = "2026-06-01"
        session_created = "2026-06-01T12:00:00+00:00"
        set_created = "2026-06-01T12:00:03+00:00"
        with self.repo.connect() as conn:
            conn.execute(
                """
                UPDATE workout_sessions SET date = ?, created_at = ? WHERE id = ?
                """,
                (session_date, session_created, self.session.id),
            )
            conn.execute(
                """
                UPDATE workout_sets SET ordinal = 5, created_at = ? WHERE id = ?
                """,
                (set_created, "set-2"),
            )
        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="Changed note",
            duration_minutes=45,
            body_weight_kg=None,
            sets=[
                SetEditPayload("set-1", "ex_a", 3, 9, None, 50.0),
                SetEditPayload("set-2", "ex_b", 3, 11, None, None),
            ],
        )
        update_saved_workout_session(self.repo, payload)
        session = self.repo.get_workout_session(self.session.id)
        self.assertEqual(session.date, session_date)
        self.assertEqual(session.created_at, session_created)
        row2 = next(r for r in self.repo.list_workout_sets(self.session.id) if r.id == "set-2")
        self.assertEqual(row2.ordinal, 5)
        self.assertEqual(row2.created_at, set_created)

    def test_swap_to_exercise_without_progress_does_not_insert_row(self):
        self.assertIsNone(self.repo.get_user_progress("ex_b"))
        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="Note",
            duration_minutes=30,
            body_weight_kg=None,
            sets=[
                SetEditPayload("set-1", "ex_b", 3, 8, None, 50.0),
                SetEditPayload("set-2", "ex_b", 3, 10, None, None),
            ],
        )
        update_saved_workout_session(self.repo, payload)
        self.assertIsNone(self.repo.get_user_progress("ex_b"))

    def test_update_reps_keeps_ids_and_ordinals(self):
        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="Note",
            duration_minutes=30,
            body_weight_kg=None,
            sets=[
                SetEditPayload("set-1", "ex_a", 3, 12, None, 50.0),
                SetEditPayload("set-2", "ex_b", 3, 10, None, None),
            ],
        )
        update_saved_workout_session(self.repo, payload)
        rows = self.repo.list_workout_sets(self.session.id)
        by_id = {r.id: r for r in rows}
        self.assertEqual(by_id["set-1"].reps, 12)
        self.assertEqual(by_id["set-1"].ordinal, 0)
        self.assertEqual(by_id["set-2"].reps, 10)
        self.assertEqual(by_id["set-2"].ordinal, 1)

    def test_weight_typo_fix_recomputes_best_weight(self):
        heavy = WorkoutSet(
            id="set-heavy",
            session_id=self.session.id,
            exercise_id="ex_a",
            sets=1,
            reps=5,
            weight_kg=500.0,
            ordinal=2,
        )
        self.repo.add_workout_set(heavy)
        with self.repo.connect() as conn:
            self.repo._recompute_progress_bests_in_conn(conn, "ex_a")
        progress = self.repo.get_user_progress("ex_a")
        self.assertEqual(progress.best_weight, 500.0)

        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="Note",
            duration_minutes=30,
            body_weight_kg=None,
            sets=[
                SetEditPayload("set-1", "ex_a", 3, 8, None, 50.0),
                SetEditPayload("set-2", "ex_b", 3, 10, None, None),
                SetEditPayload("set-heavy", "ex_a", 1, 5, None, 50.0),
            ],
        )
        status_before = self.repo.get_user_progress("ex_a").status
        update_saved_workout_session(self.repo, payload)
        progress = self.repo.get_user_progress("ex_a")
        self.assertEqual(progress.best_weight, 50.0)
        self.assertEqual(progress.status, status_before)

    def test_exercise_swap_does_not_rename_catalog(self):
        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="Note",
            duration_minutes=30,
            body_weight_kg=None,
            sets=[
                SetEditPayload("set-1", "ex_b", 3, 8, None, 50.0),
                SetEditPayload("set-2", "ex_b", 3, 10, None, None),
            ],
        )
        update_saved_workout_session(self.repo, payload)
        still_a = self.repo.get_exercise("ex_a")
        self.assertEqual(still_a.name, "Bench")
        row = next(r for r in self.repo.list_workout_sets(self.session.id) if r.id == "set-1")
        self.assertEqual(row.exercise_id, "ex_b")

    def test_invalid_exercise_rejected(self):
        payload = SessionEditPayload(
            session_id=self.session.id,
            notes="",
            duration_minutes=None,
            body_weight_kg=None,
            sets=[SetEditPayload("set-1", "missing", 3, 8, None, None)],
        )
        with self.assertRaises(ValueError):
            self.repo.update_saved_workout_session(
                self.session.id,
                {"notes": "", "duration_minutes": None, "body_weight_kg": None},
                [
                    {
                        "id": "set-1",
                        "exercise_id": "missing",
                        "sets": 3,
                        "reps": 8,
                        "hold_seconds": None,
                        "weight_kg": None,
                        "form_quality": None,
                    }
                ],
                ["missing"],
            )
        row = next(r for r in self.repo.list_workout_sets(self.session.id) if r.id == "set-1")
        self.assertEqual(row.exercise_id, "ex_a")

    def test_stale_set_id_writes_nothing(self):
        before = self.repo.list_workout_sets(self.session.id)
        with self.assertRaises(ValueError):
            self.repo.update_saved_workout_session(
                self.session.id,
                {"notes": "changed", "duration_minutes": 99, "body_weight_kg": None},
                [
                    {
                        "id": "gone",
                        "exercise_id": "ex_a",
                        "sets": 3,
                        "reps": 8,
                        "hold_seconds": None,
                        "weight_kg": None,
                        "form_quality": None,
                    }
                ],
                ["ex_a"],
            )
        session = self.repo.get_workout_session(self.session.id)
        self.assertEqual(session.notes, "Note")
        self.assertEqual(session.duration_minutes, 30)
        after = self.repo.list_workout_sets(self.session.id)
        self.assertEqual([(s.id, s.reps) for s in before], [(s.id, s.reps) for s in after])

    def test_atomicity_on_mid_update_failure(self):
        original = FitnessRepository._recompute_progress_bests_in_conn
        calls = {"n": 0}

        def flaky(self, conn, exercise_id):
            calls["n"] += 1
            if calls["n"] > 1:
                raise sqlite3.OperationalError("injected")
            return original(self, conn, exercise_id)

        with patch.object(FitnessRepository, "_recompute_progress_bests_in_conn", flaky):
            with self.assertRaises(sqlite3.OperationalError):
                self.repo.update_saved_workout_session(
                    self.session.id,
                    {"notes": "oops", "duration_minutes": 30, "body_weight_kg": None},
                    [
                        {
                            "id": "set-1",
                            "exercise_id": "ex_a",
                            "sets": 3,
                            "reps": 99,
                            "hold_seconds": None,
                            "weight_kg": 50.0,
                            "form_quality": None,
                        },
                        {
                            "id": "set-2",
                            "exercise_id": "ex_b",
                            "sets": 3,
                            "reps": 10,
                            "hold_seconds": None,
                            "weight_kg": None,
                            "form_quality": None,
                        },
                    ],
                    ["ex_a", "ex_b"],
                )
        row = next(r for r in self.repo.list_workout_sets(self.session.id) if r.id == "set-1")
        self.assertEqual(row.reps, 8)
        session = self.repo.get_workout_session(self.session.id)
        self.assertEqual(session.notes, "Note")

    def test_archived_exercise_rejected(self):
        with self.repo.connect() as conn:
            conn.execute(
                "UPDATE exercises SET deleted_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), "ex_b"),
            )
        with self.assertRaises(ValueError):
            self.repo.update_saved_workout_session(
                self.session.id,
                {"notes": "Note", "duration_minutes": 30, "body_weight_kg": None},
                [
                    {
                        "id": "set-2",
                        "exercise_id": "ex_b",
                        "sets": 3,
                        "reps": 10,
                        "hold_seconds": None,
                        "weight_kg": None,
                        "form_quality": None,
                    }
                ],
                ["ex_b"],
            )


class TestBuildPayload(unittest.TestCase):
    def setUp(self):
        self.repo, self.path = _temp_repo()
        self.ex = Exercise(id="ex1", name="Squat", source_book="SS", family="legs", mastery_criteria={})
        self.repo.add_exercise(self.ex)

    def tearDown(self):
        _dispose_temp_repo(self.repo, self.path)

    def test_unknown_typed_name_rejected(self):
        with self.assertRaises(SetFieldValidationError):
            build_session_edit_payload(
                self.repo,
                "sess",
                notes_text="",
                duration_text="",
                body_weight_text="",
                set_rows=[
                    {
                        "set_id": "s1",
                        "exercise_name": "Not In Catalog",
                        "sets": "3",
                        "reps": "8",
                        "hold": "",
                        "weight": "",
                    }
                ],
            )


class TestOrdinalBackfillDb(unittest.TestCase):
    def test_update_preserves_backfilled_ordinal(self):
        repo, path = _temp_repo()
        try:
            ex = Exercise(id="ex1", name="Pull", source_book="CC", family="pull", mastery_criteria={})
            repo.add_exercise(ex)
            session = WorkoutSession(date="2026-01-01", created_at="2026-01-01T10:00:00Z")
            repo.add_workout_session(session)
            with repo.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO workout_sets (
                        id, session_id, exercise_id, sets, reps, hold_seconds,
                        weight_kg, form_quality, ordinal, created_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, 7, ?)
                    """,
                    ("legacy-set", session.id, ex.id, 2, 6, "2026-01-01T10:01:00Z"),
                )
            payload = SessionEditPayload(
                session_id=session.id,
                notes="",
                duration_minutes=None,
                body_weight_kg=None,
                sets=[SetEditPayload("legacy-set", "ex1", 2, 7, None, None)],
            )
            update_saved_workout_session(repo, payload)
            row = repo.list_workout_sets(session.id)[0]
            self.assertEqual(row.ordinal, 7)
            self.assertEqual(row.reps, 7)
        finally:
            _dispose_temp_repo(repo, path)


class TestWorkoutSessionEditEsc(unittest.TestCase):
    def test_reps_entry_binds_escape_on_toplevel_and_widget(self):
        try:
            import tkinter as tk

            from theme import get_theme
            from workout_history_edit_ui import WorkoutSessionEditPanel
        except ImportError:
            self.skipTest("tkinter not available")

        repo, path = _temp_repo()
        ex = Exercise(id="ex1", name="Pull", source_book="CC", family="pull", mastery_criteria={})
        repo.add_exercise(ex)
        session = WorkoutSession(date="2026-06-15", created_at="2026-06-15T10:00:00Z")
        repo.add_workout_session(session)
        wset = WorkoutSet(
            id="s1",
            session_id=session.id,
            exercise_id="ex1",
            sets=3,
            reps=10,
            ordinal=0,
        )
        repo.add_workout_set(wset)
        root = tk.Tk()
        root.withdraw()
        try:
            panel = WorkoutSessionEditPanel(
                root,
                repo,
                get_theme(False),
                on_saved=lambda: None,
                on_cancel=lambda: None,
            )
            panel.pack()
            root.update_idletasks()
            panel.load_session(session, [wset])
            reps_entry = panel._row_widgets[0]["reps"]
            self.assertTrue(
                reps_entry.bind("<Escape>"),
                "Esc must be bound on the reps entry (not only the panel frame)",
            )
            self.assertTrue(
                panel.winfo_toplevel().bind("<Escape>"),
                "Esc must be bound on the toplevel while editing",
            )
        finally:
            panel.unload_shortcuts()
            panel.destroy()
            root.destroy()
            _dispose_temp_repo(repo, path)

    def test_escape_handler_cancels_without_persisting_reps(self):
        try:
            import tkinter as tk

            from theme import get_theme
            from workout_history_ui import WorkoutHistoryView
        except ImportError:
            self.skipTest("tkinter not available")

        repo, path = _temp_repo()
        ex = Exercise(id="ex1", name="Pull", source_book="CC", family="pull", mastery_criteria={})
        repo.add_exercise(ex)
        session = WorkoutSession(date="2026-06-15", created_at="2026-06-15T10:00:00Z")
        repo.add_workout_session(session)
        wset = WorkoutSet(
            id="s1",
            session_id=session.id,
            exercise_id="ex1",
            sets=3,
            reps=10,
            ordinal=0,
        )
        repo.add_workout_set(wset)
        root = tk.Tk()
        root.withdraw()
        try:
            view = WorkoutHistoryView(root, repo, get_theme(False))
            view.selected_session = session
            view.sets_by_session[session.id] = [wset]
            view._enter_edit_mode()
            panel = view._edit_panel
            assert panel is not None
            panel._row_widgets[0]["vars"]["reps"].set("99")
            panel._on_cancel_event()
            root.update()
            self.assertFalse(view._session_editing)
            self.assertEqual(repo.list_workout_sets(session.id)[0].reps, 10)
        finally:
            view.destroy()
            root.destroy()
            _dispose_temp_repo(repo, path)


class TestWorkoutHistoryAltEBinding(unittest.TestCase):
    def test_destroy_leaves_other_alt_e_handlers(self):
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
        repo.add_workout_session(WorkoutSession(date="2026-06-01"))
        root = tk.Tk()
        root.withdraw()
        other_hits: list[int] = []

        def other_handler(_event) -> None:
            other_hits.append(1)

        other_funcid = root.bind_all("<Alt-e>", other_handler, add="+")
        try:
            view = WorkoutHistoryView(root, repo, get_theme(False))
            view._do_load_first_page()
            root.update_idletasks()
            view.destroy()
            script = root.bind_class("all", "<Alt-e>") or ""
            self.assertIn(
                other_funcid,
                script,
                "Other Alt+E handler should survive history view destroy",
            )
        finally:
            from more_menu_ui import unbind_all_func

            unbind_all_func(root, "<Alt-e>", other_funcid)
            root.destroy()
            try:
                os.unlink(temp_db.name)
            except OSError:
                pass


class TestLogThenEditIntegration(unittest.TestCase):
    def test_create_workout_session_not_used_on_edit(self):
        repo, path = _temp_repo()
        try:
            ex = Exercise(id="ex1", name="Push", source_book="CC", family="push", mastery_criteria={})
            repo.add_exercise(ex)
            session = create_workout_session(
                repo,
                "2026-03-01",
                [{"exercise_id": "ex1", "sets": 3, "reps": 10}],
            )
            sets = repo.list_workout_sets(session.id)
            set_id = sets[0].id
            count_before = len(repo.list_workout_sessions(limit=100))
            payload = SessionEditPayload(
                session_id=session.id,
                notes="",
                duration_minutes=None,
                body_weight_kg=None,
                sets=[SetEditPayload(set_id, "ex1", 3, 11, None, None)],
            )
            update_saved_workout_session(repo, payload)
            self.assertEqual(len(repo.list_workout_sessions(limit=100)), count_before)
            self.assertEqual(repo.list_workout_sets(session.id)[0].id, set_id)
            self.assertEqual(repo.list_workout_sets(session.id)[0].reps, 11)
        finally:
            _dispose_temp_repo(repo, path)