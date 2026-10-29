"""State-transition and recovery tests, independent of reference policies."""

from copy import deepcopy
import unittest

from stateful_tool_lab.environment import BookingEnvironment


def initial_state():
    return {
        "slots": {"slot-a": {"capacity": 2}, "slot-b": {"capacity": 1}, "slot-full": {"capacity": 1}},
        "bookings": [
            {"id": "b001", "customer_id": "customer-a", "slot_id": "slot-a", "status": "active"},
            {"id": "b009", "customer_id": "customer-b", "slot_id": "slot-full", "status": "active"},
        ],
    }


class BookingEnvironmentTests(unittest.TestCase):
    def test_after_write_timeout_is_indistinguishable_but_commit_is_recoverable(self):
        args = {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "request-1"}
        before = BookingEnvironment(initial_state(), [{"tool": "create_booking", "phase": "before", "occurrence": 1}])
        after = BookingEnvironment(initial_state(), [{"tool": "create_booking", "phase": "after", "occurrence": 1}])
        self.assertEqual(before.call("create_booking", args), {"ok": False, "code": "timeout", "data": None})
        self.assertEqual(after.call("create_booking", args), {"ok": False, "code": "timeout", "data": None})
        self.assertEqual(len(before.snapshot()["bookings"]), 2)
        self.assertEqual(len(after.snapshot()["bookings"]), 3)
        self.assertEqual(before.call("get_operation", {"idempotency_key": "request-1"})["code"], "not_found")
        found = after.call("get_operation", {"idempotency_key": "request-1"})
        self.assertTrue(found["ok"])
        self.assertEqual(found["data"]["data"]["id"], "b002")
        self.assertTrue(after.events[0]["committed"])

    def test_same_key_retry_cannot_create_second_booking(self):
        env = BookingEnvironment(initial_state(), [{"tool": "create_booking", "phase": "after", "occurrence": 1}])
        args = {"customer_id": "customer-c", "slot_id": "slot-a", "idempotency_key": "request-1"}
        env.call("create_booking", args)
        result = env.call("create_booking", dict(reversed(list(args.items()))))
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["id"], "b002")
        self.assertEqual(len(env.snapshot()["bookings"]), 3)
        self.assertFalse(env.events[-1]["committed"])

    def test_without_key_retry_can_create_a_duplicate_intent(self):
        state = initial_state()
        state["slots"]["slot-b"]["capacity"] = 2
        env = BookingEnvironment(state, [{"tool": "create_booking", "phase": "after", "occurrence": 1}])
        args = {"customer_id": "customer-c", "slot_id": "slot-b"}
        self.assertEqual(env.call("create_booking", args)["code"], "timeout")
        self.assertTrue(env.call("create_booking", args)["ok"])
        self.assertEqual(len([b for b in env.snapshot()["bookings"] if b["customer_id"] == "customer-c"]), 2)

    def test_key_conflict_covers_changed_arguments_and_changed_tool(self):
        env = BookingEnvironment(initial_state())
        args = {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "request-1"}
        env.call("create_booking", args)
        saved = env.snapshot()
        changed = {**args, "customer_id": "customer-d"}
        self.assertEqual(env.call("create_booking", changed)["code"], "key_conflict")
        self.assertEqual(env.call("cancel_booking", {"booking_id": "b001", "idempotency_key": "request-1"})["code"], "key_conflict")
        self.assertEqual(env.snapshot(), saved)

    def test_before_timeout_occurs_once_and_does_not_cache_failure(self):
        env = BookingEnvironment(initial_state(), [{"tool": "create_booking", "phase": "before", "occurrence": 1}])
        args = {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "request-1"}
        self.assertEqual(env.call("create_booking", args)["code"], "timeout")
        self.assertFalse(env.events[-1]["committed"])
        self.assertTrue(env.call("create_booking", args)["ok"])
        self.assertTrue(env.call("create_booking", args)["ok"])
        self.assertEqual(len(env.snapshot()["bookings"]), 3)

    def test_fault_occurrence_counts_only_the_named_tool(self):
        state = initial_state()
        state["slots"]["slot-b"]["capacity"] = 2
        env = BookingEnvironment(state, [{"tool": "create_booking", "phase": "after", "occurrence": 2}])
        first = {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "first"}
        second = {"customer_id": "customer-d", "slot_id": "slot-b", "idempotency_key": "second"}
        env.call("list_bookings", {})
        self.assertTrue(env.call("create_booking", first)["ok"])
        env.call("list_bookings", {})
        self.assertEqual(env.call("create_booking", second)["code"], "timeout")
        self.assertTrue(env.call("get_operation", {"idempotency_key": "second"})["ok"])
        self.assertTrue(env.call("create_booking", second)["ok"])
        self.assertEqual(len(env.snapshot()["bookings"]), 4)

    def test_malformed_calls_cannot_consume_a_fault_occurrence(self):
        for phase in ("before", "after"):
            with self.subTest(phase=phase):
                env = BookingEnvironment(initial_state(), [{"tool": "create_booking", "phase": phase, "occurrence": 1}])
                saved = env.snapshot()
                for invalid in ({}, {"customer_id": "customer-c", "slot_id": "slot-b", "extra": "bad"}):
                    self.assertEqual(env.call("create_booking", invalid)["code"], "invalid_arguments")
                args = {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "request-1"}
                self.assertEqual(env.call("create_booking", args), {"ok": False, "code": "timeout", "data": None})
                self.assertEqual(env.events[-1]["committed"], phase == "after")
                if phase == "before":
                    self.assertEqual(env.snapshot(), saved)
                self.assertTrue(env.call("create_booking", args)["ok"])

    def test_event_snapshots_preserve_intermediate_state_without_exposing_it(self):
        env = BookingEnvironment(initial_state())
        saved = env.snapshot()
        result = env.call("move_booking", {"booking_id": "b001", "slot_id": "slot-b"})
        self.assertEqual(set(result), {"ok", "code", "data"})
        after_move = deepcopy(env.events[-1]["state_after"])
        self.assertNotEqual(after_move, saved)
        env.call("move_booking", {"booking_id": "b001", "slot_id": "slot-a"})
        self.assertEqual(env.snapshot(), saved)
        self.assertEqual(env.events[-2]["state_after"], after_move)
        self.assertEqual(env.events[-1]["state_after"], saved)
        env.events[-1]["state_after"]["bookings"].clear()
        self.assertEqual(env.snapshot(), saved)

    def test_after_fault_does_not_turn_a_rejected_mutation_into_timeout(self):
        env = BookingEnvironment(initial_state(), [{"tool": "create_booking", "phase": "after", "occurrence": 1}])
        saved = env.snapshot()
        result = env.call("create_booking", {"customer_id": "customer-c", "slot_id": "slot-full", "idempotency_key": "rejected"})
        self.assertEqual(result["code"], "capacity")
        self.assertFalse(env.events[-1]["committed"])
        self.assertEqual(env.snapshot(), saved)
        self.assertEqual(env.call("get_operation", {"idempotency_key": "rejected"})["code"], "not_found")

    def test_failed_atomic_move_preserves_old_booking_and_unrelated_records(self):
        env = BookingEnvironment(initial_state())
        saved = env.snapshot()
        response = env.call("move_booking", {"booking_id": "b001", "slot_id": "slot-full", "idempotency_key": "move-1"})
        self.assertEqual(response["code"], "capacity")
        self.assertEqual(env.snapshot(), saved)
        self.assertEqual(env.call("get_operation", {"idempotency_key": "move-1"})["code"], "not_found")
        self.assertTrue(env.call("move_booking", {"booking_id": "b001", "slot_id": "slot-b", "idempotency_key": "move-1"})["ok"])

    def test_move_and_cancel_after_timeout_have_recoverable_results(self):
        for tool, args in [
            ("move_booking", {"booking_id": "b001", "slot_id": "slot-b", "idempotency_key": "operation-1"}),
            ("cancel_booking", {"booking_id": "b001", "idempotency_key": "operation-1"}),
        ]:
            with self.subTest(tool=tool):
                env = BookingEnvironment(initial_state(), [{"tool": tool, "phase": "after", "occurrence": 1}])
                self.assertEqual(env.call(tool, args)["code"], "timeout")
                committed = env.snapshot()
                self.assertTrue(env.call(tool, args)["ok"])
                self.assertEqual(env.snapshot(), committed)
                self.assertFalse(env.events[-1]["committed"])

    def test_same_slot_move_and_repeated_cancel_are_safe_noops(self):
        env = BookingEnvironment(initial_state())
        self.assertTrue(env.call("move_booking", {"booking_id": "b001", "slot_id": "slot-a"})["ok"])
        self.assertFalse(env.events[-1]["committed"])
        self.assertTrue(env.call("cancel_booking", {"booking_id": "b001"})["ok"])
        self.assertTrue(env.events[-1]["committed"])
        self.assertTrue(env.call("cancel_booking", {"booking_id": "b001"})["ok"])
        self.assertFalse(env.events[-1]["committed"])
        self.assertEqual(env.call("move_booking", {"booking_id": "b001", "slot_id": "slot-b"})["code"], "invalid_arguments")

    def test_capacity_cannot_be_exceeded(self):
        env = BookingEnvironment(initial_state())
        self.assertTrue(env.call("create_booking", {"customer_id": "customer-c", "slot_id": "slot-b"})["ok"])
        saved = env.snapshot()
        self.assertEqual(env.call("create_booking", {"customer_id": "customer-d", "slot_id": "slot-b"})["code"], "capacity")
        self.assertEqual(env.snapshot(), saved)

    def test_unknown_records_and_tools_do_not_mutate_state(self):
        env = BookingEnvironment(initial_state())
        saved = env.snapshot()
        for tool, args in [
            ("create_booking", {"customer_id": "customer-c", "slot_id": "missing"}),
            ("cancel_booking", {"booking_id": "missing"}),
            ("move_booking", {"booking_id": "missing", "slot_id": "slot-b"}),
            ("get_operation", {"idempotency_key": "missing"}),
        ]:
            with self.subTest(tool=tool):
                self.assertEqual(env.call(tool, args)["code"], "not_found")
        self.assertEqual(env.call("unknown", {})["code"], "invalid_arguments")
        self.assertEqual(env.snapshot(), saved)

    def test_malformed_arguments_never_mutate_state(self):
        env = BookingEnvironment(initial_state())
        saved = env.snapshot()
        for args in [None, [], {}, {"customer_id": "c"},
                     {"customer_id": "c", "slot_id": "slot-b", "extra": "oops"},
                     {"customer_id": 1, "slot_id": "slot-b"},
                     {"customer_id": "c", "slot_id": "slot-b", "idempotency_key": None},
                     {"customer_id": "c", "slot_id": "slot-b", "idempotency_key": " "}]:
            with self.subTest(args=args):
                self.assertEqual(env.call("create_booking", args)["code"], "invalid_arguments")
        self.assertEqual(env.call([], {})["code"], "invalid_arguments")
        self.assertEqual(env.snapshot(), saved)

    def test_all_read_and_response_objects_are_independent_copies(self):
        state = initial_state()
        original = deepcopy(state)
        env = BookingEnvironment(state)
        state["slots"]["slot-a"]["capacity"] = 0
        snapshot = env.snapshot()
        snapshot["bookings"].clear()
        listed = env.call("list_bookings", {"customer_id": "customer-a"})
        self.assertEqual(len(listed["data"]), 1)
        listed["data"][0]["status"] = "cancelled"
        self.assertEqual(env.snapshot(), original)
        created = env.call("create_booking", {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "request-1"})
        created["data"]["status"] = "cancelled"
        operation = env.call("get_operation", {"idempotency_key": "request-1"})
        self.assertEqual(operation["data"]["data"]["status"], "active")
        operation["data"]["data"]["customer_id"] = "changed"
        replay = env.call("create_booking", {"customer_id": "customer-c", "slot_id": "slot-b", "idempotency_key": "request-1"})
        self.assertEqual(replay["data"]["customer_id"], "customer-c")

    def test_invalid_fixture_state_and_faults_fail_early(self):
        for state in [None, {}, {"slots": {}, "bookings": {}},
                      {"slots": {"a": {"capacity": True}}, "bookings": []},
                      {"slots": {"a": {"capacity": -1}}, "bookings": []}]:
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    BookingEnvironment(state)
        overfull = initial_state()
        overfull["slots"]["slot-full"]["capacity"] = 0
        with self.assertRaises(ValueError):
            BookingEnvironment(overfull)
        for faults in [{}, [{"tool": "list_bookings", "phase": "after", "occurrence": 1}],
                       [{"tool": "create_booking", "phase": "after", "occurrence": True}],
                       [{"tool": "create_booking", "phase": "bad", "occurrence": 1}],
                       [{"tool": "create_booking", "phase": "before", "occurrence": 1},
                        {"tool": "create_booking", "phase": "after", "occurrence": 1}]]:
            with self.subTest(faults=faults):
                with self.assertRaises(ValueError):
                    BookingEnvironment(initial_state(), faults)


if __name__ == "__main__":
    unittest.main()
