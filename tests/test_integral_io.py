"""Tests for export and backup I/O."""

import json
import os
import tempfile
import unittest

from integral_io import (
    export_fitness_sessions_csv,
    export_journal_csv,
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

    def test_backup_roundtrip_preserves_journal_and_creative(self) -> None:
        payload = {
            "schema_version": 2,
            "entries": {
                "2026-07-12": {
                    "Body & Presence": {
                        "rating": 8,
                        "checklist": {},
                        "metrics": {},
                        "notes": "export check",
                    }
                }
            },
            "settings": {"dark_mode": False},
            "journal": {
                "prompts": ["Free write — no prompt"],
                "entries": [
                    {
                        "id": "abcdef123456",
                        "entry_date": "2026-07-12",
                        "written_at": "2026-07-12T12:00:00",
                        "prompt": "Free write — no prompt",
                        "title": "Stack",
                        "body": "See [[journal:abcdef123456|self]] later.",
                        "backdate_reason": None,
                    }
                ],
            },
            "creative_projects": {
                "schema_version": 1,
                "projects": [{"id": "aabbccddeeff", "title": "Novel", "status": "drafting"}],
            },
            "day_plans": {},
            "sessions": [{"date": "2026-07-11", "program_id": "cc1", "movement_logs": []}],
            "milestones": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            backup_path = os.path.join(tmp, "backup.json")
            target_path = os.path.join(tmp, "data.json")
            write_backup(payload, backup_path)
            backup = load_backup(backup_path)
            restore_backup_to_path(backup, target_path, make_copy=False)
            with open(target_path, encoding="utf-8") as handle:
                restored = json.load(handle)
            self.assertNotIn("backup_app", restored)
            self.assertEqual(
                restored["entries"]["2026-07-12"]["Body & Presence"]["notes"],
                "export check",
            )
            self.assertEqual(restored["journal"]["entries"][0]["id"], "abcdef123456")
            self.assertEqual(restored["creative_projects"]["projects"][0]["title"], "Novel")
            self.assertEqual(restored["sessions"][0]["date"], "2026-07-11")

    def test_export_journal_csv(self) -> None:
        journal = {
            "prompts": [],
            "entries": [
                {
                    "entry_date": "2026-07-12",
                    "written_at": "2026-07-12T12:00:00",
                    "prompt": "Free write",
                    "title": "Hello",
                    "body": "World",
                    "backdate_reason": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "journal.csv")
            rows = export_journal_csv(journal, path)
            self.assertEqual(rows, 1)
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Hello", content)
            self.assertIn("World", content)

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
