"""Regression tests for issue #227 — scalar / malformed reps_per_set at startup."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fitness.engine import (  # noqa: E402
    compute_program_state,
    evaluate_session_log,
    load_program_definitions,
    migrate_data,
)
from fitness.reps_normalization import (  # noqa: E402
    classify_reps_per_set,
    drain_unreadable_reps_warnings,
    logger as reps_logger,
    normalize_reps_per_set,
    reset_unreadable_reps_warnings,
)
from fitness.intelligence import get_fitness_settings  # noqa: E402
from personal_dev_tracker import format_unreadable_reps_banner_message  # noqa: E402
from tests.mock_tracker import mock_tracker_init  # noqa: E402


def _cc_session(reps_per_set) -> dict:
    return {
        "date": "2026-07-01",
        "program_id": "convict-conditioning",
        "movement_logs": [
            {
                "movement_key": "cc-pushups",
                "step": 1,
                "step_name": "Wall Pushups",
                "reps_per_set": reps_per_set,
            }
        ],
    }


class TestRepsNormalization(unittest.TestCase):
    def test_logger_under_integral_hierarchy(self) -> None:
        self.assertEqual(reps_logger.name, "integral.fitness.reps")
        self.assertTrue(reps_logger.name.startswith("integral."))

    def test_scalar_int_becomes_single_element_list(self) -> None:
        self.assertEqual(normalize_reps_per_set(10), [10])

    def test_string_numeric_becomes_single_element_list(self) -> None:
        self.assertEqual(normalize_reps_per_set("10"), [10])

    def test_list_passthrough(self) -> None:
        self.assertEqual(normalize_reps_per_set([10, 8]), [10, 8])

    def test_none_and_empty(self) -> None:
        self.assertEqual(normalize_reps_per_set(None), [])
        self.assertEqual(classify_reps_per_set(None)[1], False)
        self.assertEqual(classify_reps_per_set({})[1], True)
        self.assertEqual(classify_reps_per_set("abc")[1], True)


class TestEvaluateSessionLogReps(unittest.TestCase):
    def setUp(self) -> None:
        reset_unreadable_reps_warnings()
        self.program = load_program_definitions()["convict-conditioning"]

    def _evaluate(self, reps_per_set) -> dict:
        return evaluate_session_log(
            {
                "movement_key": "cc-pushups",
                "step": 1,
                "reps_per_set": reps_per_set,
                "form_quality": 8,
            },
            self.program,
        )

    def test_int_reps_does_not_raise(self) -> None:
        self._evaluate(10)

    def test_string_and_garbage_do_not_raise(self) -> None:
        for value in ("10", "abc", None, {}):
            with self.subTest(value=value):
                self._evaluate(value)

    def test_scalar_int_normalized_for_standard_check(self) -> None:
        self.assertTrue(self._evaluate([50, 50, 50])["ready_to_advance"])
        self.assertFalse(self._evaluate(10)["ready_to_advance"])


class TestStartupProgramState(unittest.TestCase):
    def setUp(self) -> None:
        reset_unreadable_reps_warnings()
        self.programs = load_program_definitions()

    def test_compute_program_state_with_scalar_reps(self) -> None:
        sessions = [_cc_session(10)]
        state = compute_program_state(self.programs, sessions)
        self.assertIn("convict-conditioning", state)
        self.assertIn("cc-pushups", state["convict-conditioning"])

    def test_migrate_data_v2_payload_with_scalar_reps(self) -> None:
        sessions = [_cc_session(10)]
        payload = {
            "schema_version": 2,
            "categories": {},
            "entries": {},
            "settings": {"dark_mode": False},
            "sessions": sessions,
            "milestones": [],
        }
        sessions_snapshot = hashlib.sha256(
            json.dumps(sessions, sort_keys=True).encode()
        ).hexdigest()
        migrated = migrate_data(payload, self.programs)
        sessions_after = hashlib.sha256(json.dumps(sessions, sort_keys=True).encode()).hexdigest()
        self.assertEqual(sessions_snapshot, sessions_after)
        self.assertIn("program_state", migrated)
        self.assertIn("convict-conditioning", migrated["program_state"])

    def test_malformed_reps_collected_not_raised(self) -> None:
        sessions = [_cc_session("abc")]
        compute_program_state(self.programs, sessions)
        warnings = drain_unreadable_reps_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["date"], "2026-07-01")


class TestUnreadableRepsBanner(unittest.TestCase):
    def test_banner_message_singular_and_plural(self) -> None:
        self.assertIn("entry had", format_unreadable_reps_banner_message(1))
        self.assertIn("was skipped", format_unreadable_reps_banner_message(1))
        self.assertIn("entries had", format_unreadable_reps_banner_message(2))
        self.assertIn("were skipped", format_unreadable_reps_banner_message(2))

    def test_restart_with_persisted_dismissed_ids_suppresses_banner(self) -> None:
        import personal_dev_tracker

        root = tk.Tk()
        root.withdraw()
        try:
            with mock.patch.object(
                personal_dev_tracker.PersonalDevelopmentTracker,
                "__init__",
                mock_tracker_init,
            ):
                tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
            entry_id = "2026-07-01|cc-pushups|'abc'"
            drained = [
                {
                    "id": entry_id,
                    "date": "2026-07-01",
                    "movement": "cc-pushups",
                    "raw": "'abc'",
                }
            ]
            tracker.settings = {"dark_mode": False}
            self.assertEqual(len(tracker._collect_unread_unreadable_reps_warnings(drained)), 1)
            tracker.settings["fitness"] = get_fitness_settings(
                {"fitness": {"dismissed_unreadable_reps": [entry_id]}}
            )
            pending = tracker._collect_unread_unreadable_reps_warnings(drained)
            self.assertEqual(pending, [])
            tracker._pending_unreadable_reps_warnings = pending
            tracker._banner_host = tk.Frame(root)
            tracker._show_unreadable_reps_banner_if_needed()
            self.assertIsNone(tracker._status_banner)
        finally:
            root.destroy()

    def test_banner_once_per_entry(self) -> None:
        import personal_dev_tracker

        root = tk.Tk()
        root.withdraw()
        try:
            with mock.patch.object(
                personal_dev_tracker.PersonalDevelopmentTracker,
                "__init__",
                mock_tracker_init,
            ):
                tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
            tracker.settings = {"dark_mode": False, "fitness": {"dismissed_unreadable_reps": []}}
            tracker._banner_host = tk.Frame(root)
            tracker._pending_unreadable_reps_warnings = [
                {
                    "id": "2026-07-01|cc-pushups|\"abc\"",
                    "date": "2026-07-01",
                    "movement": "cc-pushups",
                    "raw": "'abc'",
                }
            ]
            warnings = list(tracker._pending_unreadable_reps_warnings)
            tracker._show_unreadable_reps_banner_if_needed()
            self.assertIsNotNone(tracker._status_banner)
            with mock.patch.object(tracker, "save_data") as save_mock:
                tracker._dismiss_unreadable_reps_warnings(warnings)
            dismissed = tracker.settings["fitness"]["dismissed_unreadable_reps"]
            self.assertIn("2026-07-01|cc-pushups|\"abc\"", dismissed)
            save_mock.assert_called()
            tracker.settings["fitness"] = get_fitness_settings(
                {"fitness": {"dismissed_unreadable_reps": dismissed}}
            )
            tracker._pending_unreadable_reps_warnings = tracker._collect_unread_unreadable_reps_warnings(
                warnings
            )
            tracker._show_unreadable_reps_banner_if_needed()
            self.assertEqual(tracker._pending_unreadable_reps_warnings, [])
        finally:
            root.destroy()


class TestLoadDataStartupPath(unittest.TestCase):
    def test_migrate_data_matches_startup_chain(self) -> None:
        programs = load_program_definitions()
        data = {
            "schema_version": 2,
            "categories": {},
            "entries": {},
            "settings": {},
            "sessions": [_cc_session(10)],
            "milestones": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            with open(path, "rb") as handle:
                digest_before = hashlib.sha256(handle.read()).hexdigest()
            migrated = migrate_data(data, programs)
            with open(path, "rb") as handle:
                digest_after = hashlib.sha256(handle.read()).hexdigest()
            self.assertEqual(digest_before, digest_after)
            self.assertIn("cc-pushups", migrated["program_state"]["convict-conditioning"])


if __name__ == "__main__":
    unittest.main()
