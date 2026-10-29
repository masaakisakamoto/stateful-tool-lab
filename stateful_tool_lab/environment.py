"""Deterministic, in-memory booking tools for offline reliability experiments.

The environment models capacity and atomic changes, but deliberately does not
deduplicate separate requests without an idempotency key. It is a fixture, not a
production scheduler or a security boundary. ``snapshot`` and ``events`` belong
to the evaluator, and must not be exposed as agent tools.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from typing import Any


_MUTATIONS = frozenset({"create_booking", "cancel_booking", "move_booking"})
_TOOLS = _MUTATIONS | {"list_bookings", "get_operation"}
_FIELDS = {
    "create_booking": ({"customer_id", "slot_id"}, {"idempotency_key"}),
    "cancel_booking": ({"booking_id"}, {"idempotency_key"}),
    "move_booking": ({"booking_id", "slot_id"}, {"idempotency_key"}),
    "list_bookings": (set(), {"customer_id"}),
    "get_operation": ({"idempotency_key"}, set()),
}


def _response(code: str = "ok", data: Any = None) -> dict[str, Any]:
    return {"ok": code == "ok", "code": code, "data": deepcopy(data)}


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class BookingEnvironment:
    """Own a fresh state, a private operation ledger, and one-shot faults.

    A fault applies to the specified tool's one-based valid-schema call
    occurrence. Rejected schemas do not consume a fault occurrence. A before
    fault executes no business operation;
    an after fault hides the result only when that call changes booking state.
    Both return exactly the same ``timeout`` response to the caller.

    A successful keyed mutation records the result before a possible after
    fault. Replaying the same key and payload returns that result without a
    second mutation. Reusing the key for a different tool or payload fails.
    Errors are not recorded in the ledger.
    """

    def __init__(self, initial_state: dict, faults: list | None = None):
        self._state = self._validated_state(initial_state)
        self._faults = self._validated_faults(faults)
        self._fired: set[int] = set()
        self._counts: Counter[str] = Counter()
        self._operations: dict[str, tuple[str, dict[str, Any]]] = {}
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def _validated_state(state: dict) -> dict[str, Any]:
        if not isinstance(state, dict) or set(state) != {"slots", "bookings"}:
            raise ValueError("initial_state requires slots and bookings")
        slots, bookings = state["slots"], state["bookings"]
        if not isinstance(slots, dict) or not isinstance(bookings, list):
            raise ValueError("slots must be an object and bookings must be a list")
        for slot_id, slot in slots.items():
            if (
                not _identifier(slot_id)
                or not isinstance(slot, dict)
                or set(slot) != {"capacity"}
                or type(slot["capacity"]) is not int
                or slot["capacity"] < 0
            ):
                raise ValueError("each slot requires a nonnegative integer capacity")
        ids: set[str] = set()
        occupancy: Counter[str] = Counter()
        for booking in bookings:
            if (
                not isinstance(booking, dict)
                or set(booking) != {"id", "customer_id", "slot_id", "status"}
                or not all(_identifier(booking[field]) for field in booking)
                or booking["id"] in ids
                or booking["slot_id"] not in slots
                or booking["status"] not in {"active", "cancelled"}
            ):
                raise ValueError("invalid or duplicate booking record")
            ids.add(booking["id"])
            if booking["status"] == "active":
                occupancy[booking["slot_id"]] += 1
        if any(count > slots[key]["capacity"] for key, count in occupancy.items()):
            raise ValueError("initial bookings exceed a slot's capacity")
        return deepcopy(state)

    @staticmethod
    def _validated_faults(faults: list | None) -> list[dict[str, Any]]:
        if faults is None:
            return []
        if not isinstance(faults, list):
            raise ValueError("faults must be a list")
        seen: set[tuple[str, int]] = set()
        for fault in faults:
            if (
                not isinstance(fault, dict)
                or set(fault) != {"tool", "phase", "occurrence"}
                or not isinstance(fault["tool"], str)
                or fault["tool"] not in _MUTATIONS
                or not isinstance(fault["phase"], str)
                or fault["phase"] not in {"before", "after"}
                or type(fault["occurrence"]) is not int
                or fault["occurrence"] < 1
            ):
                raise ValueError("faults require a mutation tool, phase, and occurrence >= 1")
            key = (fault["tool"], fault["occurrence"])
            if key in seen:
                raise ValueError("only one fault may target a tool occurrence")
            seen.add(key)
        return deepcopy(faults)

    def snapshot(self) -> dict[str, Any]:
        """Return a stable, independent business-state copy for the grader."""
        return {
            "slots": {key: deepcopy(self._state["slots"][key]) for key in sorted(self._state["slots"])},
            "bookings": sorted(deepcopy(self._state["bookings"]), key=lambda booking: booking["id"]),
        }

    def _fault(self, tool: str, phase: str) -> bool:
        for index, fault in enumerate(self._faults):
            if (
                index not in self._fired
                and fault["tool"] == tool
                and fault["phase"] == phase
                and fault["occurrence"] == self._counts[tool]
            ):
                self._fired.add(index)
                return True
        return False

    def _record(self, tool: Any, args: Any, response: dict, committed: bool = False) -> dict:
        self.events.append({
            "tool": deepcopy(tool),
            "args": deepcopy(args),
            "response": deepcopy(response),
            "committed": committed,
            "state_after": self.snapshot(),
        })
        return deepcopy(response)

    def call(self, tool: str, arguments: dict) -> dict[str, Any]:
        """Call a documented tool; failures use data=None and never raise."""
        if not isinstance(tool, str) or tool not in _TOOLS:
            return self._record(tool, arguments, _response("invalid_arguments"))
        required, optional = _FIELDS[tool]
        if (
            not isinstance(arguments, dict)
            or not required <= arguments.keys()
            or not arguments.keys() <= required | optional
            or not all(_identifier(value) for value in arguments.values())
        ):
            return self._record(tool, arguments, _response("invalid_arguments"))
        self._counts[tool] += 1
        args = deepcopy(arguments)
        if tool in _MUTATIONS and self._fault(tool, "before"):
            return self._record(tool, args, _response("timeout"))

        key = args.get("idempotency_key") if tool in _MUTATIONS else None
        fingerprint = json.dumps(
            {"tool": tool, "arguments": {field: value for field, value in args.items() if field != "idempotency_key"}},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if key is not None and key in self._operations:
            old_fingerprint, old_response = self._operations[key]
            response = old_response if old_fingerprint == fingerprint else _response("key_conflict")
            return self._record(tool, args, response)

        response, committed = self._execute(tool, args)
        if key is not None and response["ok"]:
            self._operations[key] = (fingerprint, deepcopy(response))
        if committed and self._fault(tool, "after"):
            response = _response("timeout")
        return self._record(tool, args, response, committed)

    def _has_capacity(self, slot_id: str, excluding: str | None = None) -> bool:
        used = sum(
            booking["status"] == "active"
            and booking["slot_id"] == slot_id
            and booking["id"] != excluding
            for booking in self._state["bookings"]
        )
        return used < self._state["slots"][slot_id]["capacity"]

    def _execute(self, tool: str, args: dict[str, str]) -> tuple[dict[str, Any], bool]:
        if tool == "list_bookings":
            bookings = self.snapshot()["bookings"]
            if "customer_id" in args:
                bookings = [booking for booking in bookings if booking["customer_id"] == args["customer_id"]]
            return _response(data=bookings), False
        if tool == "get_operation":
            operation = self._operations.get(args["idempotency_key"])
            return (_response(data=operation[1]) if operation else _response("not_found")), False

        if tool in {"create_booking", "move_booking"}:
            slot_id = args["slot_id"]
            if slot_id not in self._state["slots"]:
                return _response("not_found"), False
        if tool == "create_booking":
            if not self._has_capacity(slot_id):
                return _response("capacity"), False
            ids = {booking["id"] for booking in self._state["bookings"]}
            index = 1
            while f"b{index:03d}" in ids:
                index += 1
            booking = {
                "id": f"b{index:03d}",
                "customer_id": args["customer_id"],
                "slot_id": slot_id,
                "status": "active",
            }
            self._state["bookings"].append(booking)
            return _response(data=booking), True

        booking = next((item for item in self._state["bookings"] if item["id"] == args["booking_id"]), None)
        if booking is None:
            return _response("not_found"), False
        if tool == "cancel_booking":
            changed = booking["status"] != "cancelled"
            booking["status"] = "cancelled"
            return _response(data=booking), changed
        if booking["status"] != "active":
            return _response("invalid_arguments"), False
        if not self._has_capacity(slot_id, excluding=booking["id"]):
            return _response("capacity"), False
        changed = booking["slot_id"] != slot_id
        booking["slot_id"] = slot_id
        return _response(data=booking), changed
