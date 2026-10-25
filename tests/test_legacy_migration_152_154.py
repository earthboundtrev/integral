"""Regression tests for legacy migration flag persistence (#152, #154)."""

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from legacy_fitness_migration import (
    backup_files_for_migration,
    migrate_legacy_sessions,
    prune_migration_backups,
    run_in_memory_migration,
)
from progression.db import FitnessRepository
from vault import encrypt_payload, load_data_file, save_data_file


class TestLegacyMigration152154(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_path = os.path.join(self.temp_dir, "data.json")
        self.db_path = os.path.join(self.temp_dir, "fitness.db")

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir)
        except OSError:
            pass

    def _write_plain_data(self, sessions):
        payload = {"schema_version": 2, "sessions": sessions}
        save_data_file(self.data_path, payload, encrypted=False, passphrase=None)
        return payload

    def _write_encrypted_data(self, sessions, passphrase: str):
        payload = {"schema_version": 2, "sessions": sessions}
        envelope = encrypt_payload(payload, passphrase)
        with open(self.data_path, "w", encoding="utf-8") as handle:
            json.dump(envelope, handle)
        return payload

    def test_second_launch_skips_backup_and_insert(self):
        sessions = [{"date": "2026-10-01", "program_id": "CC1", "notes": "Strong"}]
        self._write_plain_data(sessions)

        result1 = run_in_memory_migration(
            sessions, self.db_path, data_path=self.data_path
        )
        self.assertEqual(result1["migrated_count"], 1)
        self.assertEqual(result1["flagged_count"], 1)
        backups_after_first = [
            f for f in os.listdir(self.temp_dir) if "migration_backup" in f
        ]
        self.assertEqual(len(backups_after_first), 2)

        with mock.patch(
            "legacy_fitness_migration.backup_files_for_migration"
        ) as backup_mock:
            result2 = run_in_memory_migration(
                sessions, self.db_path, data_path=self.data_path
            )
            backup_mock.assert_not_called()
        self.assertEqual(result2["migrated_count"], 0)
        self.assertEqual(result2["flagged_count"], 0)

        repo = FitnessRepository(db_path=self.db_path)
        self.assertEqual(len(repo.list_workout_sessions(limit=50)), 1)

    def test_self_heal_flags_when_db_already_has_rows(self):
        sessions = [{"date": "2026-10-01", "notes": "Already in DB"}]
        self._write_plain_data(sessions)
        repo = FitnessRepository(db_path=self.db_path)
        migrate_legacy_sessions({"sessions": sessions}, repo, dry_run=False)
        self.assertNotIn("migrated_to_fitness_db", sessions[0])

        result = run_in_memory_migration(
            sessions, self.db_path, data_path=self.data_path
        )
        self.assertEqual(result["migrated_count"], 0)
        self.assertEqual(result["flagged_count"], 1)
        self.assertIn("migrated_to_fitness_db", sessions[0])

    def test_encrypted_data_json_backup_is_ciphertext(self):
        secret_note = "pässwörd-secret-note-ü"
        passphrase = "pässwörd"
        sessions = [{"date": "2026-10-01", "notes": secret_note}]
        self._write_encrypted_data(sessions, passphrase)
        with open(self.data_path, "rb") as handle:
            encrypted_bytes = handle.read()

        result = run_in_memory_migration(
            sessions,
            self.db_path,
            data_path=self.data_path,
            include_free_text_notes=False,
        )
        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(result["flagged_count"], 1)

        backups = [
            os.path.join(self.temp_dir, name)
            for name in os.listdir(self.temp_dir)
            if name.startswith("data.json.migration_backup_")
        ]
        self.assertEqual(len(backups), 1)
        with open(backups[0], "rb") as handle:
            backup_bytes = handle.read()
        self.assertEqual(backup_bytes, encrypted_bytes)
        self.assertNotIn(secret_note.encode("utf-8"), backup_bytes)

        with open(self.db_path, "rb") as handle:
            db_bytes = handle.read()
        self.assertNotIn(secret_note.encode("utf-8"), db_bytes)

    def test_encrypted_migration_via_passphrase_load(self):
        passphrase = "pässwörd"
        sessions = [{"date": "2026-10-02", "notes": "vault session"}]
        self._write_encrypted_data(sessions, passphrase)
        data = load_data_file(self.data_path, passphrase)

        result = run_in_memory_migration(
            data["sessions"],
            self.db_path,
            data_path=self.data_path,
            include_free_text_notes=False,
        )
        self.assertEqual(result["migrated_count"], 1)
        self.assertIn("migrated_to_fitness_db", data["sessions"][0])

    def test_prune_keeps_single_backup_pair(self):
        for i in range(5):
            path = os.path.join(self.temp_dir, f"data.json.migration_backup_2026010{i}_120000_00000{i}")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{}")
            db_path = os.path.join(
                self.temp_dir, f"fitness.db.migration_backup_2026010{i}_120000_00000{i}"
            )
            with open(db_path, "w", encoding="utf-8") as handle:
                handle.write("")

        prune_migration_backups(self.temp_dir)
        remaining = [f for f in os.listdir(self.temp_dir) if "migration_backup" in f]
        self.assertEqual(len(remaining), 2)

    def test_backup_uses_microsecond_suffixes(self):
        self._write_plain_data([{"date": "2026-10-01", "notes": "x"}])
        FitnessRepository(db_path=self.db_path).initialize()
        data_backup, db_backup = backup_files_for_migration(self.data_path, self.db_path)
        self.assertIn("_", data_backup.split("migration_backup_")[-1])
        parts = data_backup.split("migration_backup_")[-1].split("_")
        self.assertGreaterEqual(len(parts), 3)

    def test_persist_flags_through_save_path(self):
        sessions = [{"date": "2026-10-03", "notes": "persist me"}]
        payload = self._write_plain_data(sessions)
        run_in_memory_migration(sessions, self.db_path, data_path=self.data_path)
        payload["sessions"] = sessions
        save_data_file(self.data_path, payload, encrypted=False, passphrase=None)

        reloaded = load_data_file(self.data_path, None)
        self.assertIn("migrated_to_fitness_db", reloaded["sessions"][0])

        result = run_in_memory_migration(
            reloaded["sessions"], self.db_path, data_path=self.data_path
        )
        self.assertFalse(result.get("backed_up"))


if __name__ == "__main__":
    unittest.main()
