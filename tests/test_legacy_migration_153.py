"""Regression tests for all-or-nothing legacy migration (#153)."""

import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from legacy_fitness_migration import (
    LegacyMigrationValidationError,
    collect_legacy_session_errors,
    migrate_legacy_sessions,
    run_in_memory_migration,
    session_needs_legacy_migration,
)
from progression.db import FitnessRepository
from vault import save_data_file


def _valid_session(day: int, note: str = "ok") -> dict:
    return {
        "date": f"2026-01-{day:02d}",
        "program_id": "CC1",
        "notes": note,
        "movement_logs": [{"movement_name": "Push-up", "step": 1, "reps_per_set": 5}],
    }


def _legacy_row_count(db_path: str) -> int:
    if not os.path.exists(db_path):
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM workout_sessions WHERE notes LIKE '[LEGACY:%'"
        ).fetchone()
        return int(row["c"])


class TestLegacyMigration153(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_path = os.path.join(self.temp_dir, "data.json")
        self.db_path = os.path.join(self.temp_dir, "fitness.db")

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir)
        except OSError:
            pass

    def _write_sessions(self, sessions: list) -> bytes:
        payload = {"schema_version": 2, "sessions": sessions}
        save_data_file(self.data_path, payload, encrypted=False, passphrase=None)
        with open(self.data_path, "rb") as handle:
            return handle.read()

    def _sessions_twelve_plus_bad(self, bad_index: int, bad_session) -> list:
        sessions = [_valid_session(i) for i in range(1, 13)]
        sessions[bad_index] = bad_session
        return sessions

    def _assert_migration_aborts_clean(
        self,
        sessions: list,
        *,
        data_before: bytes,
        db_before: bytes | None,
    ) -> LegacyMigrationValidationError:
        repo = FitnessRepository(db_path=self.db_path)
        with self.assertRaises(LegacyMigrationValidationError) as ctx:
            migrate_legacy_sessions({"sessions": sessions}, repo)
        self.assertEqual(_legacy_row_count(self.db_path), 0)
        with open(self.data_path, "rb") as handle:
            self.assertEqual(handle.read(), data_before)
        if db_before is not None and os.path.exists(self.db_path):
            with open(self.db_path, "rb") as handle:
                self.assertEqual(handle.read(), db_before)
        for sess in sessions:
            if isinstance(sess, dict):
                self.assertNotIn("migrated_to_fitness_db", sess)
        return ctx.exception

    def test_twelve_sessions_bad_field_inserts_zero_rows(self):
        cases = [
            (0, {"notes": "SECRET_NOTE_XYZ", "program_id": "CC1"}),
            (3, {"date": "not-a-date", "notes": "n", "movement_logs": []}),
            (5, {"date": "2026-01-06", "movement_logs": ["pushup"]}),
            (7, {"date": "2026-01-08", "movement_logs": [{"movement_name": "x", "step": "bad"}]}),
            (11, "oops"),
        ]
        for bad_index, bad_session in cases:
            sessions = self._sessions_twelve_plus_bad(bad_index, bad_session)
            data_before = self._write_sessions(sessions)
            db_before = None
            repo = FitnessRepository(db_path=self.db_path)
            repo.initialize()
            with open(self.db_path, "rb") as handle:
                db_before = handle.read()

            exc = self._assert_migration_aborts_clean(
                sessions, data_before=data_before, db_before=db_before
            )
            msg = "; ".join(exc.errors)
            self.assertIn(f"index {bad_index}", msg)
            self.assertNotIn("SECRET_NOTE_XYZ", msg)

    def test_run_in_memory_migration_all_or_nothing_count(self):
        sessions = [_valid_session(i) for i in range(1, 13)]
        sessions[4] = {"date": "2026-01-05", "movement_logs": ["pushup"]}
        self._write_sessions(sessions)

        with self.assertRaises(LegacyMigrationValidationError):
            run_in_memory_migration(sessions, self.db_path, data_path=self.data_path)

        self.assertEqual(_legacy_row_count(self.db_path), 0)

        sessions[4] = _valid_session(5)
        result = run_in_memory_migration(sessions, self.db_path, data_path=self.data_path)
        self.assertEqual(result["migrated_count"], 12)
        self.assertEqual(_legacy_row_count(self.db_path), 12)
        self.assertTrue(all("migrated_to_fitness_db" in s for s in sessions))

    def test_non_dict_session_safe_for_needs_migration_precheck(self):
        sessions = [_valid_session(1), "oops"]
        self.assertTrue(session_needs_legacy_migration("oops"))
        errors = collect_legacy_session_errors(sessions)
        self.assertTrue(any("index 1" in err for err in errors))

    def test_validation_errors_encode_for_cp1252_console(self):
        sessions = [
            _valid_session(1),
            {"date": "2026-01-02", "notes": "café", "movement_logs": ["bad"]},
        ]
        errors = collect_legacy_session_errors(sessions)
        joined = "\n".join(errors)
        joined.encode("cp1252", errors="replace")

    def test_legacy_count_is_zero_or_full_batch(self):
        sessions = [_valid_session(i) for i in range(1, 13)]
        self._write_sessions(sessions)
        result = run_in_memory_migration(sessions, self.db_path, data_path=self.data_path)
        self.assertEqual(result["migrated_count"], 12)
        legacy_count = _legacy_row_count(self.db_path)
        self.assertIn(legacy_count, (0, 12))
        self.assertEqual(legacy_count, 12)


if __name__ == "__main__":
    unittest.main()
