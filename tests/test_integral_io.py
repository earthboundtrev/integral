"""Tests for export and backup I/O."""

import json
import os
import tempfile
import unittest
import zipfile

from integral_io import (
    export_creative_documents_zip,
    export_fitness_sessions_csv,
    export_journal_csv,
    export_life_entries_csv,
    load_backup,
    restore_backup_file,
    restore_backup_to_path,
    write_backup,
    write_full_backup,
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

    def test_full_backup_roundtrips_creative_documents(self) -> None:
        payload = {
            "schema_version": 2,
            "entries": {},
            "settings": {},
            "creative_projects": {
                "schema_version": 1,
                "projects": [{"id": "proj001", "title": "Novel", "status": "drafting"}],
            },
            "todos": {"items": [{"id": "t1", "text": "Write", "done": False}]},
            "practices": {"items": []},
            "day_plans": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            creative_src = os.path.join(tmp, "creative_src")
            creative_dst = os.path.join(tmp, "creative_dst")
            project_dir = os.path.join(creative_src, "proj001")
            os.makedirs(project_dir)
            with open(os.path.join(project_dir, "inspiration.txt"), "w", encoding="utf-8") as handle:
                handle.write("Premise here")
            with open(os.path.join(project_dir, "manuscript.txt"), "w", encoding="utf-8") as handle:
                handle.write("Chapter one")

            fitness_src = os.path.join(tmp, "fitness.db")
            with open(fitness_src, "wb") as handle:
                handle.write(b"SQLite stub")

            zip_path = os.path.join(tmp, "full.zip")
            target_data = os.path.join(tmp, "restored", "data.json")
            fitness_dst = os.path.join(tmp, "restored", "fitness.db")
            manifest = write_full_backup(
                payload,
                zip_path,
                creative_root=creative_src,
                fitness_db_path=fitness_src,
            )
            self.assertEqual(manifest["creative_file_count"], 2)
            self.assertTrue(manifest["has_fitness"])

            result = restore_backup_file(
                zip_path,
                target_data,
                creative_root=creative_dst,
                fitness_db_path=fitness_dst,
                make_copy=False,
            )
            self.assertEqual(result["restored_creative_files"], 2)
            self.assertTrue(result["restored_fitness"])
            with open(target_data, encoding="utf-8") as handle:
                restored = json.load(handle)
            self.assertEqual(restored["todos"]["items"][0]["text"], "Write")
            with open(
                os.path.join(creative_dst, "proj001", "manuscript.txt"), encoding="utf-8"
            ) as handle:
                self.assertEqual(handle.read(), "Chapter one")
            with open(fitness_dst, "rb") as handle:
                self.assertEqual(handle.read(), b"SQLite stub")

    def test_legacy_json_restore_warns_about_creative(self) -> None:
        payload = {"schema_version": 2, "entries": {}, "settings": {}}
        with tempfile.TemporaryDirectory() as tmp:
            backup_path = os.path.join(tmp, "legacy.json")
            target = os.path.join(tmp, "data.json")
            write_backup(payload, backup_path)
            result = restore_backup_file(backup_path, target, make_copy=False)
            self.assertEqual(result["backup_kind"], "legacy_json")
            self.assertIn("creative", result["warning"].lower())

    def test_export_creative_documents_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            creative = os.path.join(tmp, "creative")
            os.makedirs(os.path.join(creative, "p1"))
            with open(os.path.join(creative, "p1", "manuscript.txt"), "w", encoding="utf-8") as handle:
                handle.write("hello")
            out = os.path.join(tmp, "creative.zip")
            count = export_creative_documents_zip(creative, out)
            self.assertEqual(count, 1)
            with zipfile.ZipFile(out, "r") as zf:
                self.assertIn("creative/p1/manuscript.txt", zf.namelist())

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
