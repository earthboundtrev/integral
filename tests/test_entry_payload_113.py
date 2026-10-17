"""Golden / unit tests for build_entry_payload (#113)."""

import json
import unittest

from entry_payload import build_entry_payload, clamp_rating, merge_entry_updates


CAT = {
    "checklist": ["A", "B"],
    "metrics": [{"name": "Sleep hours last night", "type": "number", "default": 5}],
}


class TestBuildEntryPayload(unittest.TestCase):
    def test_golden_shape_rating_only(self):
        payload = build_entry_payload(CAT, 7, notes="hello")
        self.assertEqual(payload, {"rating": 7, "notes": "hello"})
        json.dumps(payload)  # serializable

    def test_golden_with_partial_checklist_and_metrics(self):
        payload = build_entry_payload(
            CAT,
            8,
            checklist={"A": True},
            metrics={"Sleep hours last night": 7.5},
            notes="",
        )
        self.assertEqual(
            payload,
            {
                "rating": 8,
                "notes": "",
                "checklist": {"A": True},
                "metrics": {"Sleep hours last night": 7.5},
            },
        )

    def test_unrated_returns_none_never_empty_dict(self):
        self.assertIsNone(build_entry_payload(CAT, None))
        self.assertIsNone(build_entry_payload(CAT, 0))
        self.assertIsNone(build_entry_payload(CAT, ""))

    def test_clamp_rating(self):
        self.assertEqual(clamp_rating(0), None)
        self.assertEqual(clamp_rating(11), 10)
        self.assertEqual(clamp_rating(-3), None)
        self.assertEqual(clamp_rating("7"), 7)

    def test_omit_untouched_checklist_metrics(self):
        payload = build_entry_payload(CAT, 5, checklist=None, metrics=None, notes="x")
        self.assertNotIn("checklist", payload)
        self.assertNotIn("metrics", payload)

    def test_merge_preserves_existing_detail(self):
        existing = {
            "rating": 6,
            "checklist": {"A": True},
            "metrics": {"Sleep hours last night": 8},
            "notes": "old",
        }
        updates = build_entry_payload(CAT, 7, notes="new note")
        merged = merge_entry_updates(existing, updates or {})
        self.assertEqual(merged["rating"], 7)
        self.assertEqual(merged["notes"], "new note")
        self.assertEqual(merged["checklist"], {"A": True})
        self.assertEqual(merged["metrics"]["Sleep hours last night"], 8)


if __name__ == "__main__":
    unittest.main()
