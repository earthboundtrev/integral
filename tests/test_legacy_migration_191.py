"""Legacy movement_logs → workout_sets migration (#191)."""

import os
import shutil
import sqlite3
import tempfile
import unittest

from legacy_fitness_migration import (
    LegacyMigrationValidationError,
    backfill_legacy_workout_sets,
    build_legacy_session_notes,
    legacy_source_hash,
    migrate_legacy_sessions,
    run_in_memory_migration,
)
from progression.db import FitnessRepository
from progression.seed_loader import seed_from_file


def _sample_legacy_session() -> dict:
    return {
        "date": "2026-03-15",
        "program_id": "convict-conditioning",
        "notes": "Felt solid",
        "movement_logs": [
            {
                "movement_key": "cc-pushups",
                "movement_name": "Pushups",
                "step": 3,
                "reps_per_set": [10, 8, 8],
                "form_quality": 7,
                "height_cm": 42,
            }
        ],
    }


class TestLegacyMigration191(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_path = os.path.join(self.temp_dir, "data.json")
        self.db_path = os.path.join(self.temp_dir, "fitness.db")
        with open(self.data_path, "w", encoding="utf-8") as handle:
            handle.write('{"sessions": []}')

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir)
        except OSError:
            pass

    def _sets_for_session(self, session_id: str) -> list[sqlite3.Row]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                """
                SELECT reps, hold_seconds, form_quality, ordinal, exercise_id
                FROM workout_sets
                WHERE session_id = ?
                ORDER BY ordinal
                """,
                (session_id,),
            ).fetchall()

    def test_reps_per_set_creates_one_row_per_rep(self):
        repo = FitnessRepository(db_path=self.db_path)
        seed_from_file(repo, "cc1_push.json")
        sess = _sample_legacy_session()
        result = migrate_legacy_sessions({"sessions": [sess]}, repo)
        self.assertEqual(result["migrated_count"], 1)
        session_id = result["session_ids"][0]
        rows = self._sets_for_session(session_id)
        self.assertEqual(len(rows), 3)
        self.assertEqual([row["reps"] for row in rows], [10, 8, 8])
        self.assertEqual([row["ordinal"] for row in rows], [0, 1, 2])
        self.assertTrue(all(row["form_quality"] == 7 for row in rows))

    def test_hold_seconds_creates_duration_set(self):
        repo = FitnessRepository(db_path=self.db_path)
        sess = {
            "date": "2026-03-16",
            "movement_logs": [
                {
                    "movement_key": "unknown-hold",
                    "step": 2,
                    "hold_seconds": 30,
                    "form_quality": 8,
                }
            ],
        }
        result = migrate_legacy_sessions({"sessions": [sess]}, repo)
        session_id = result["session_ids"][0]
        rows = self._sets_for_session(session_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hold_seconds"], 30.0)
        self.assertEqual(rows[0]["form_quality"], 8)

    def test_field_by_field_notes_and_sets(self):
        repo = FitnessRepository(db_path=self.db_path)
        seed_from_file(repo, "cc1_push.json")
        sess = _sample_legacy_session()
        source_hash = legacy_source_hash(sess)
        notes = build_legacy_session_notes(sess, source_hash, include_free_text_notes=True)
        self.assertIn(f"[LEGACY:{source_hash}]", notes)
        self.assertIn("Pushups", notes)
        self.assertIn("Step 3", notes)
        self.assertIn("[10, 8, 8]", notes)
        self.assertIn("Height: 42cm", notes)
        self.assertIn("Form: 7/10", notes)
        self.assertIn("Felt solid", notes)

        result = migrate_legacy_sessions({"sessions": [sess]}, repo)
        session_id = result["session_ids"][0]
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            note_row = conn.execute(
                "SELECT notes FROM workout_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        self.assertEqual(note_row["notes"], notes)

    def test_idempotent_second_run_adds_no_sets(self):
        repo = FitnessRepository(db_path=self.db_path)
        seed_from_file(repo, "cc1_push.json")
        sess = _sample_legacy_session()
        migrate_legacy_sessions({"sessions": [sess]}, repo)
        migrate_legacy_sessions({"sessions": [sess]}, repo)
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        self.assertEqual(count, 3)

    def test_unknown_movement_key_creates_legacy_exercise(self):
        repo = FitnessRepository(db_path=self.db_path)
        sess = {
            "date": "2026-03-17",
            "movement_logs": [
                {
                    "movement_key": "mystery-move",
                    "step": 1,
                    "reps_per_set": [5],
                }
            ],
        }
        migrate_legacy_sessions({"sessions": [sess]}, repo)
        exercises = repo.list_exercises()
        legacy = [ex for ex in exercises if ex.source_book == "Legacy"]
        self.assertEqual(len(legacy), 1)
        self.assertIn("mystery-move", legacy[0].name)

    def test_bad_movement_log_aborts_with_no_sets(self):
        repo = FitnessRepository(db_path=self.db_path)
        repo.initialize()
        sessions = [
            _sample_legacy_session(),
            {"date": "2026-03-18", "movement_logs": ["pushup"]},
        ]
        with self.assertRaises(LegacyMigrationValidationError):
            migrate_legacy_sessions({"sessions": sessions}, repo)
        with sqlite3.connect(self.db_path) as conn:
            session_count = conn.execute(
                "SELECT COUNT(*) FROM workout_sessions"
            ).fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        self.assertEqual(session_count, 0)
        self.assertEqual(set_count, 0)

    def test_backfill_sets_for_existing_legacy_session_without_duplicating(self):
        repo = FitnessRepository(db_path=self.db_path)
        seed_from_file(repo, "cc1_push.json")
        sess = _sample_legacy_session()
        source_hash = legacy_source_hash(sess)
        notes = build_legacy_session_notes(sess, source_hash)
        repo.initialize()
        with repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO workout_sessions (id, date, notes)
                VALUES ('existing-session', ?, ?)
                """,
                (sess["date"], notes),
            )
            conn.commit()

        sess["migrated_to_fitness_db"] = "2026-01-01T00:00:00"
        backfill = backfill_legacy_workout_sets([sess], repo)
        self.assertEqual(backfill["sets_inserted"], 3)
        self.assertEqual(backfill["sessions_updated"], 1)

        with sqlite3.connect(self.db_path) as conn:
            session_count = conn.execute(
                "SELECT COUNT(*) FROM workout_sessions"
            ).fetchone()[0]
        self.assertEqual(session_count, 1)
        rows = self._sets_for_session("existing-session")
        self.assertEqual(len(rows), 3)

    def test_run_in_memory_migration_marks_version_and_backfills(self):
        repo = FitnessRepository(db_path=self.db_path)
        seed_from_file(repo, "cc1_push.json")
        sess = _sample_legacy_session()
        source_hash = legacy_source_hash(sess)
        notes = build_legacy_session_notes(sess, source_hash)
        repo.initialize()
        with repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO workout_sessions (id, date, notes)
                VALUES ('existing-session', ?, ?)
                """,
                (sess["date"], notes),
            )
            conn.commit()
        sess["migrated_to_fitness_db"] = "2026-01-01T00:00:00"
        app_settings = {"fitness": {}}
        result = run_in_memory_migration(
            [sess],
            self.db_path,
            data_path=self.data_path,
            app_settings=app_settings,
        )
        self.assertEqual(result.get("sets_backfilled"), 3)
        self.assertEqual(
            app_settings["fitness"].get("legacy_movement_sets_version"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
