"""Unit tests for fitness progression engine."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fitness.engine import (  # noqa: E402
    compute_program_state,
    evaluate_session_log,
    load_program_definitions,
    meets_sets_reps_standard,
    migrate_data,
    parse_standard,
)


class TestParseStandard(unittest.TestCase):
    def test_sets_reps(self) -> None:
        parsed = parse_standard("3x50")
        self.assertEqual(parsed, {"type": "sets_reps", "sets": 3, "reps": 50})

    def test_hold(self) -> None:
        parsed = parse_standard("30s")
        self.assertEqual(parsed, {"type": "hold_seconds", "seconds": 30})


class TestAdvancement(unittest.TestCase):
    def test_cc_progression_met(self) -> None:
        programs = load_program_definitions()
        program = programs["convict-conditioning"]
        result = evaluate_session_log(
            {
                "movement_key": "cc-pushups",
                "step": 1,
                "reps_per_set": [50, 50, 50],
                "form_quality": 8,
            },
            program,
        )
        self.assertTrue(result["ready_to_advance"])

    def test_cc_form_blocks_advance(self) -> None:
        programs = load_program_definitions()
        program = programs["convict-conditioning"]
        result = evaluate_session_log(
            {
                "movement_key": "cc-pushups",
                "step": 1,
                "reps_per_set": [50, 50, 50],
                "form_quality": 5,
            },
            program,
        )
        self.assertFalse(result["ready_to_advance"])

    def test_tibetan_week_advance(self) -> None:
        programs = load_program_definitions()
        program = programs["tibetan-rites"]
        result = evaluate_session_log(
            {
                "target_reps": 3,
                "reps_per_rite": {
                    "rite-1": 3,
                    "rite-2": 3,
                    "rite-3": 3,
                    "rite-4": 3,
                    "rite-5": 3,
                },
            },
            program,
        )
        self.assertTrue(result["ready_to_advance"])

    def test_meets_sets_reps(self) -> None:
        standard = parse_standard("2x25")
        self.assertTrue(meets_sets_reps_standard([25, 25], standard))
        self.assertFalse(meets_sets_reps_standard([20, 25], standard))


class TestProgramState(unittest.TestCase):
    def test_cc_state_from_sessions(self) -> None:
        programs = load_program_definitions()
        sessions = [
            {
                "date": "2026-07-01",
                "program_id": "convict-conditioning",
                "movement_logs": [
                    {
                        "movement_key": "cc-pushups",
                        "step": 2,
                        "step_name": "Incline Pushups",
                        "reps_per_set": [20, 20],
                    }
                ],
            }
        ]
        state = compute_program_state(programs, sessions)
        pushup_state = state["convict-conditioning"]["cc-pushups"]
        self.assertEqual(pushup_state["current_step"], 2)
        self.assertEqual(pushup_state["step_name"], "Incline Pushups")


class TestMigration(unittest.TestCase):
    def test_migrate_v1_payload(self) -> None:
        programs = load_program_definitions()
        legacy = {"categories": {}, "entries": {}, "settings": {"dark_mode": False}}
        migrated = migrate_data(legacy, programs)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertIn("sessions", migrated)
        self.assertIn("program_state", migrated)


class TestProgramLibrary(unittest.TestCase):
    def test_reference_programs_loaded(self) -> None:
        programs = load_program_definitions()
        expected = {
            "convict-conditioning",
            "convict-conditioning-2",
            "explosive-calisthenics",
            "overcoming-gravity",
            "strong-medicine",
            "super-joints",
            "tibetan-rites",
        }
        self.assertTrue(expected.issubset(set(programs.keys())))
        cc2 = programs["convict-conditioning-2"]
        self.assertEqual(cc2["program_type"], "reference")
        self.assertGreaterEqual(len(cc2["movements"]), 9)
        og = programs["overcoming-gravity"]
        self.assertIn("charts", og)
        sj = programs["super-joints"]
        self.assertGreaterEqual(len(sj["movements"]), 28)


if __name__ == "__main__":
    unittest.main()
