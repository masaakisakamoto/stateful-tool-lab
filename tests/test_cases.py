"""Dataset integrity checks independent of environment implementation."""

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
import unittest


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "cases" / "booking.json"


class BookingCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.cases = cls.payload["cases"]

    def test_count_and_unique_case_ids(self):
        self.assertEqual(len(self.cases), 24)
        self.assertEqual(len({case["id"] for case in self.cases}), 24)
        self.assertEqual(len({case["scenario_id"] for case in self.cases}), 12)

    def test_paired_variants_share_conditions_and_oracle(self):
        pairs = defaultdict(list)
        for case in self.cases:
            pairs[case["scenario_id"]].append(case)
        for scenario_id, variants in pairs.items():
            with self.subTest(scenario_id=scenario_id):
                self.assertEqual({case["language"] for case in variants}, {"ja", "en"})
                self.assertEqual(len(variants), 2)
                self.assertNotEqual(variants[0]["instruction"], variants[1]["instruction"])
                normalized = []
                for case in variants:
                    item = copy.deepcopy(case)
                    for key in ("id", "language", "instruction"):
                        del item[key]
                    normalized.append(item)
                self.assertEqual(normalized[0], normalized[1])

    def test_state_and_oracle_are_well_formed(self):
        for case in self.cases:
            with self.subTest(case_id=case["id"]):
                self.assertTrue(case["instruction"].strip())
                slots = case["initial_state"]["slots"]
                bookings = case["initial_state"]["bookings"]
                self.assertEqual(len({booking["id"] for booking in bookings}), len(bookings))
                for slot in slots.values():
                    self.assertIs(type(slot["capacity"]), int)
                    self.assertGreater(slot["capacity"], 0)
                for booking in bookings:
                    self.assertIn(booking["slot_id"], slots)
                    self.assertIn(booking["status"], {"active", "cancelled"})
                    self.assertTrue(booking["customer_id"])
                expected = case["expected"]
                self.assertEqual(len(expected["outcomes"]), len(case["requests"]))
                self.assertTrue(set(expected["outcomes"]).issubset({"ok", "capacity", "not_found", "key_conflict"}))
                for booking in expected["active_bookings"]:
                    self.assertEqual(set(booking), {"customer_id", "slot_id"})
                    self.assertIn(booking["slot_id"], slots)
                for booking in expected.get("required_bookings", []):
                    self.assertEqual(set(booking), {"id", "customer_id", "slot_id", "status"})
                    self.assertIn(booking["slot_id"], slots)
                    self.assertIn(booking["status"], {"active", "cancelled"})
                active_counts = Counter(booking["slot_id"] for booking in expected["active_bookings"])
                for slot_id, count in active_counts.items():
                    self.assertLessEqual(count, slots[slot_id]["capacity"])

    def test_faults_are_single_explicit_write_boundaries(self):
        for case in self.cases:
            with self.subTest(case_id=case["id"]):
                self.assertLessEqual(len(case["faults"]), 1)
                for fault in case["faults"]:
                    self.assertIn(fault["tool"], {"create_booking", "cancel_booking", "move_booking"})
                    self.assertIn(fault["phase"], {"before", "after"})
                    self.assertEqual(fault["occurrence"], 1)
                    self.assertEqual(fault["tool"], case["requests"][0]["tool"])

    def test_reference_requests_do_not_contain_the_oracle(self):
        for case in self.cases:
            with self.subTest(case_id=case["id"]):
                for request in case["requests"]:
                    self.assertEqual(set(request), {"tool", "arguments", "operation_id"})
                    self.assertIsInstance(request["arguments"], dict)
                    self.assertTrue(request["operation_id"].strip())
                    self.assertNotIn("idempotency_key", request["arguments"])

    def test_duplicate_and_post_commit_create_can_expose_extra_booking(self):
        for scenario_id in ("duplicate-delivery", "create-after-timeout"):
            case = next(case for case in self.cases if case["scenario_id"] == scenario_id)
            with self.subTest(scenario_id=scenario_id):
                self.assertEqual(case["initial_state"]["bookings"], [])
                self.assertGreaterEqual(case["initial_state"]["slots"]["s1"]["capacity"], 2)
                self.assertEqual(case["expected"]["active_bookings"], [{"customer_id": "c1", "slot_id": "s1"}])
        duplicate = next(case for case in self.cases if case["scenario_id"] == "duplicate-delivery")
        self.assertEqual(duplicate["requests"][0], duplicate["requests"][1])
        self.assertEqual(duplicate["expected"]["outcomes"], ["ok", "ok"])

    def test_occupied_move_preserves_both_booking_identities(self):
        case = next(case for case in self.cases if case["scenario_id"] == "move-occupied")
        self.assertEqual(case["expected"]["outcomes"], ["capacity"])
        self.assertCountEqual(case["expected"]["required_bookings"], case["initial_state"]["bookings"])

    def test_cancellation_and_move_have_identity_oracles(self):
        for case in self.cases:
            if case["scenario_id"].startswith(("cancel-", "move-")):
                with self.subTest(case_id=case["id"]):
                    originals = {booking["id"] for booking in case["initial_state"]["bookings"]}
                    required = {booking["id"] for booking in case["expected"]["required_bookings"]}
                    self.assertTrue(originals.issubset(required))


if __name__ == "__main__":
    unittest.main()
