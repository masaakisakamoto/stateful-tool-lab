import copy
import unittest

from stateful_tool_lab.environment import BookingEnvironment
from stateful_tool_lab.runner import grade, load_cases, replay, run_reference


class GraderTests(unittest.TestCase):
    def test_reference_and_negative_control(self):
        cases = load_cases()
        self.assertTrue(all(run_reference(c, "idempotent")["passed"] for c in cases))
        self.assertTrue(any(not run_reference(c, "naive")["passed"] for c in cases))

    def test_wrong_success_claim_does_not_override_state(self):
        case = next(c for c in load_cases() if c["scenario_id"] == "create-clean" and c["language"] == "en")
        result = replay(case, {"calls": [], "outcomes": ["ok"]})
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["active_state"])

    def test_read_calls_do_not_change_grade(self):
        case = next(c for c in load_cases() if c["scenario_id"] == "create-clean" and c["language"] == "en")
        request = case["requests"][0]
        args = dict(request["arguments"], idempotency_key=request["operation_id"])
        result = replay(case, {"calls": [
            {"tool": "list_bookings", "arguments": {}},
            {"tool": request["tool"], "arguments": args},
            {"tool": "list_bookings", "arguments": {}}
        ], "outcomes": ["ok"]})
        self.assertTrue(result["passed"])

    def test_replay_budget_and_input_validation(self):
        case = load_cases()[0]
        with self.assertRaises(ValueError):
            replay(case, {"calls": [{}] * 21, "outcomes": []})
        with self.assertRaises(ValueError):
            replay(case, {"calls": [{"tool": "create_booking", "arguments": []}], "outcomes": []})

    def test_multiset_detects_duplicate(self):
        case = copy.deepcopy(load_cases()[0])
        env = BookingEnvironment(case["initial_state"], [])
        request = case["requests"][0]
        env.call(request["tool"], request["arguments"])
        env.call(request["tool"], request["arguments"])
        self.assertFalse(grade(case, env, ["ok"])["checks"]["active_state"])

    def test_cancel_and_recreate_cannot_pass_as_an_in_place_move(self):
        case = next(c for c in load_cases() if c["scenario_id"] == "move-clean" and c["language"] == "en")
        request = case["requests"][0]
        target = request["arguments"]
        customer = next(b["customer_id"] for b in case["initial_state"]["bookings"]
                        if b["id"] == target["booking_id"])
        result = replay(case, {"calls": [
            {"tool": "cancel_booking", "arguments": {"booking_id": target["booking_id"]}},
            {"tool": "create_booking", "arguments": {"customer_id": customer, "slot_id": target["slot_id"]}}
        ], "outcomes": ["ok"]})
        self.assertTrue(result["checks"]["active_state"])
        self.assertFalse(result["checks"]["required_records"])
        self.assertFalse(result["passed"])

    def test_creating_duplicate_then_cancelling_it_still_fails(self):
        case = next(c for c in load_cases() if c["id"] == "create-clean-en")
        args = case["requests"][0]["arguments"]
        result = replay(case, {"calls": [
            {"tool": "create_booking", "arguments": args},
            {"tool": "create_booking", "arguments": args},
            {"tool": "cancel_booking", "arguments": {"booking_id": "b002"}}
        ], "outcomes": ["ok"]})
        self.assertTrue(result["checks"]["active_state"])
        self.assertFalse(result["checks"]["no_extra_created_records"])
        self.assertFalse(result["passed"])

    def test_failure_claim_needs_observed_evidence(self):
        case = next(c for c in load_cases() if c["id"] == "create-occupied-en")
        result = replay(case, {"calls": [], "outcomes": ["capacity"]})
        self.assertFalse(result["passed"])
        read_result = replay(case, {"calls": [{"tool": "list_bookings", "arguments": {}}],
                                    "outcomes": ["capacity"]})
        self.assertTrue(read_result["passed"])

    def test_unrelated_temporary_move_and_restore_is_detected(self):
        case = next(c for c in load_cases() if c["id"] == "create-occupied-en")
        booking_id = case["initial_state"]["bookings"][0]["id"]
        result = replay(case, {"calls": [
            {"tool": "move_booking", "arguments": {"booking_id": booking_id, "slot_id": "s3"}},
            {"tool": "move_booking", "arguments": {"booking_id": booking_id, "slot_id": "s2"}},
            {"tool": "list_bookings", "arguments": {}}
        ], "outcomes": ["capacity"]})
        self.assertTrue(result["checks"]["active_state"])
        self.assertFalse(result["checks"]["unrelated_records_never_changed"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
