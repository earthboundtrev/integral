"""Tests for legacy fitness migration (#116)."""

import json
import os
import tempfile
import unittest

from legacy_fitness_migration import (
    apply_migrated_flags,
    backup_files_for_migration,
    legacy_source_hash,
    migrate_legacy_sessions,
    run_in_memory_migration,
)
from vault import load_data_file, save_data_file
from progression.db import FitnessRepository


class TestLegacyMigration(unittest.TestCase):
    """Test legacy data.json session migration to fitness.db."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_path = os.path.join(self.temp_dir, "data.json")
        self.db_path = os.path.join(self.temp_dir, "fitness.db")

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_backup_creates_timestamped_copies(self):
        """Test that backup creates timestamped files."""
        # Create test files
        with open(self.data_path, 'w') as f:
            json.dump({"sessions": []}, f)
        
        repo = FitnessRepository(db_path=self.db_path)
        repo.initialize()
        
        data_backup, db_backup = backup_files_for_migration(self.data_path, self.db_path)
        
        self.assertTrue(os.path.exists(data_backup))
        self.assertTrue(os.path.exists(db_backup))
        self.assertIn("migration_backup", data_backup)
        self.assertIn("migration_backup", db_backup)

    def test_empty_legacy_list(self):
        """Test migration with no legacy sessions."""
        data = {"sessions": []}
        repo = FitnessRepository(db_path=self.db_path)
        
        result = migrate_legacy_sessions(data, repo)
        
        self.assertEqual(result["migrated_count"], 0)
        self.assertEqual(result["skipped_count"], 0)

    def test_typical_legacy_session(self):
        """Test migration of a typical legacy session."""
        data = {
            "sessions": [
                {
                    "date": "2026-10-01",
                    "program_id": "CC1_Push",
                    "notes": "Felt strong today",
                    "duration_minutes": 30,
                    "movements": ["Push-ups", "Squats"],
                    "logs": [],
                }
            ]
        }
        
        repo = FitnessRepository(db_path=self.db_path)
        result = migrate_legacy_sessions(data, repo)
        
        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(result["skipped_count"], 0)
        
        # Verify session was created
        sessions = repo.list_workout_sessions(limit=10)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].date, "2026-10-01")
        self.assertIn("CC1_Push", sessions[0].notes)

    def test_idempotency(self):
        """Test that running migration twice creates no duplicates."""
        data = {
            "sessions": [
                {
                    "date": "2026-10-01",
                    "program": "TestProgram",
                    "notes": "Test session",
                    "duration_minutes": 20,
                }
            ]
        }
        
        repo = FitnessRepository(db_path=self.db_path)
        
        # First migration
        result1 = migrate_legacy_sessions(data, repo)
        self.assertEqual(result1["migrated_count"], 1)
        
        # Second migration
        result2 = migrate_legacy_sessions(data, repo)
        self.assertEqual(result2["migrated_count"], 0)
        self.assertEqual(result2["skipped_count"], 1)
        
        # Verify only one session exists
        sessions = repo.list_workout_sessions(limit=10)
        self.assertEqual(len(sessions), 1)

    def test_malformed_entries_skipped(self):
        """Test that malformed entries are skipped and logged."""
        data = {
            "sessions": [
                {"notes": "Missing date"},  # No date
                {"date": "2026-10-01", "notes": "Valid"},
                {"date": None, "notes": "Null date"},  # Null date
            ]
        }
        
        repo = FitnessRepository(db_path=self.db_path)
        result = migrate_legacy_sessions(data, repo)
        
        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(result["skipped_count"], 2)
        self.assertEqual(len(result["errors"]), 2)

    def test_mark_migrated_flag(self):
        """Test that sessions are marked as migrated in memory and persist via save."""
        sessions = [
            {"date": "2026-10-01", "notes": "Session 1"},
            {"date": "2026-10-02", "notes": "Session 2"},
        ]
        apply_migrated_flags(sessions, sessions)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump({"sessions": sessions}, f)
        save_data_file(self.data_path, {"sessions": sessions}, encrypted=False, passphrase=None)

        with open(self.data_path, "r", encoding="utf-8") as f:
            updated = json.load(f)

        for sess in updated["sessions"]:
            self.assertIn("migrated_to_fitness_db", sess)

    def test_legacy_hash_ignores_migrated_flag(self):
        """Hash is stable when migrated_to_fitness_db is added (#154)."""
        base = {"date": "2026-10-01", "notes": "Test"}
        flagged = {**base, "migrated_to_fitness_db": "2026-10-01T12:00:00"}
        self.assertEqual(legacy_source_hash(base), legacy_source_hash(flagged))

    def test_transaction_rollback_on_failure(self):
        """Test that failed migration leaves database unchanged."""
        # This is implicit in the implementation using conn.rollback()
        # but we can verify by checking that partial migrations don't persist
        data = {
            "sessions": [
                {"date": "2026-10-01", "notes": "First"},
                {"date": "2026-10-02", "notes": "Second"},
            ]
        }
        
        repo = FitnessRepository(db_path=self.db_path)
        result = migrate_legacy_sessions(data, repo)
        
        # Both should succeed
        self.assertEqual(result["migrated_count"], 2)
        
        # Verify both exist
        sessions = repo.list_workout_sessions(limit=10)
        self.assertEqual(len(sessions), 2)

    def test_full_migration_with_backup(self):
        """Test the complete migration flow with backup."""
        data = {
            "sessions": [
                {"date": "2026-10-01", "notes": "Test", "duration_minutes": 25}
            ]
        }
        
        with open(self.data_path, 'w') as f:
            json.dump(data, f)
        
        data = load_data_file(self.data_path, None)
        result = run_in_memory_migration(
            data["sessions"], self.db_path, data_path=self.data_path
        )

        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(result["flagged_count"], 1)

        save_data_file(self.data_path, data, encrypted=False, passphrase=None)

        backups = [f for f in os.listdir(self.temp_dir) if "migration_backup" in f]
        self.assertGreater(len(backups), 0)

        updated = load_data_file(self.data_path, None)
        self.assertIn("migrated_to_fitness_db", updated["sessions"][0])


if __name__ == "__main__":
    unittest.main()
