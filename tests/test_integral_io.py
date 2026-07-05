"""Tests for export and backup I/O."""

import json
import os
import tempfile
import unittest

from integral_io import (
    export_fitness_sessions_csv,
    export_life_entries_csv,
    load_backup,
    restore_backup_to_path,
    write_backup,
)


class IntegralIoTests(unittest.TestCase):
    def test_export_life_csv(self) -> None:
        entries = {
            "2026-07-01": {
                "Body": {"rating": 7, "checklist": {"a": True}, "metrics": {}, "notes": "felt good"},
            }
        }
        categories = {"Body": {"checklist": ["a"], "metrics": []}}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.csv")
            rows = export_life_entries_csv(entries, categories, path)
            self.assertEqual(rows, 1)
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Body", content)

    def test_backup_roundtrip(self) -> None:
        payload = {"schema_version": 2, "entries": {}, "settings": {"dark_mode": False}}
        with tempfile.TemporaryDirectory() as tmp:
            backup_path = os.path.join(tmp, "backup.json")
            target_path = os.path.join(tmp, "data.json")
            write_backup(payload, backup_path)
            backup = load_backup(backup_path)
            self.assertEqual(backup["backup_app"], "Integral")
            restore_backup_to_path(backup, target_path, make_copy=False)
            with open(target_path, encoding="utf-8") as handle:
                restored = json.load(handle)
            self.assertEqual(restored["schema_version"], 2)

    def test_export_fitness_csv(self) -> None:
        sessions = [
            {
                "date": "2026-07-01",
                "program_id": "convict-conditioning",
                "movement_logs": [
                    {
                        "movement_key": "pushups",
                        "step": 2,
                        "reps_per_set": [10, 10, 10],
                    }
                ],
            }
        ]
        programs = {"convict-conditioning": {"name": "CC", "id": "convict-conditioning"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fitness.csv")
            rows = export_fitness_sessions_csv(sessions, programs, path)
            self.assertEqual(rows, 1)


if __name__ == "__main__":
    unittest.main()
