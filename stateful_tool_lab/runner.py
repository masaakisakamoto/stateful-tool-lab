"""Reference controllers, state-based grading, and trace replay.

These controllers consume structured requests. They do not understand language
and must never be presented as LLM benchmark results.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .environment import BookingEnvironment


CASE_PATH = Path(__file__).resolve().parent.parent / "cases" / "booking.json"


def load_cases(path: Path = CASE_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _active(state: dict) -> Counter:
    return Counter(
        (b["customer_id"], b["slot_id"])
        for b in state["bookings"] if b["status"] == "active"
    )


def grade(case: dict, env: BookingEnvironment, outcomes: list[str]) -> dict:
    """Check outcomes and final records, allowing any valid tool trajectory."""
    state = env.snapshot()
    expected = case["expected"]
    desired = Counter((b["customer_id"], b["slot_id"]) for b in expected["active_bookings"])
    observed = _active(state)
    by_id = {b["id"]: b for b in state["bookings"]}
    addressed = {
        r["arguments"].get("booking_id") for r in case["requests"]
        if r["tool"] in {"cancel_booking", "move_booking"}
    }
    protected = [b for b in case["initial_state"]["bookings"] if b["id"] not in addressed]
    initial_ids = {b["id"] for b in case["initial_state"]["bookings"]}
    allowed_creations = {
        r["operation_id"] for r, outcome in zip(case["requests"], expected["outcomes"])
        if r["tool"] == "create_booking" and outcome == "ok"
    }

    def has_evidence(request: dict, outcome: str) -> bool:
        if outcome == "ok":
            return True  # Business state and record identity supply independent checks.
        for event in env.events:
            response = event["response"]
            if (event["tool"] == request["tool"] and response["code"] == outcome
                    and all(event["args"].get(k) == v for k, v in request["arguments"].items())):
                return True
            # A read proving the slot is full is also a valid alternative to a rejected write.
            if outcome == "capacity" and event["tool"] == "list_bookings" and response["ok"]:
                slot = request["arguments"]["slot_id"]
                capacity = state["slots"][slot]["capacity"]
                observed_occupancy = sum(b["slot_id"] == slot and b["status"] == "active"
                                         for b in response["data"])
                if observed_occupancy >= capacity:
                    return True
        return False

    checks = {
        "active_state": observed == desired,
        "reported_outcomes": outcomes == expected["outcomes"],
        "required_records": all(
            by_id.get(b["id"]) == b for b in expected.get("required_bookings", [])
        ),
        "unrelated_records_preserved": all(by_id.get(b["id"]) == b for b in protected),
        "no_extra_created_records": len(set(by_id) - initial_ids) <= len(allowed_creations),
        "unrelated_records_never_changed": all(
            all({b["id"]: b for b in event["state_after"]["bookings"]}.get(p["id"]) == p
                for p in protected) for event in env.events
        ),
        "outcome_evidence": all(has_evidence(request, outcome)
                                for request, outcome in zip(case["requests"], expected["outcomes"])),
    }
    return {
        "case_id": case["id"], "scenario_id": case["scenario_id"],
        "language": case["language"], "passed": all(checks.values()),
        "checks": checks, "outcomes": outcomes,
        "extra_active_bookings": sum((observed - desired).values()),
        "missing_active_bookings": sum((desired - observed).values()),
        "tool_calls": len(env.events),
        "committed_calls": sum(bool(e["committed"]) for e in env.events),
        "final_state": state, "events": copy.deepcopy(env.events),
    }


def run_reference(case: dict, controller: str) -> dict:
    if controller not in {"naive", "idempotent"}:
        raise ValueError("Unknown reference controller")
    env = BookingEnvironment(case["initial_state"], case.get("faults", []))
    outcomes = []
    for request in case["requests"]:
        arguments = copy.deepcopy(request["arguments"])
        if controller == "idempotent":
            arguments["idempotency_key"] = request["operation_id"]
        response = env.call(request["tool"], arguments)
        # Both retry once; only one keeps a stable operation identity.
        if response["code"] == "timeout":
            response = env.call(request["tool"], arguments)
        outcomes.append(response["code"])
    result = grade(case, env, outcomes)
    result["controller"] = controller
    return result


def replay(case: dict, trace: dict, max_calls: int = 20) -> dict:
    """Re-execute submitted tool calls; never trust a submitted final state."""
    calls = trace.get("calls")
    outcomes = trace.get("outcomes")
    if not isinstance(calls, list) or not isinstance(outcomes, list):
        raise ValueError("Each trace needs calls and outcomes arrays")
    if len(calls) > max_calls:
        raise ValueError(f"Trace exceeds the {max_calls}-call budget")
    if not all(isinstance(x, str) for x in outcomes):
        raise ValueError("Trace outcomes must be strings")
    env = BookingEnvironment(case["initial_state"], case.get("faults", []))
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("tool"), str):
            raise ValueError("Every call needs a tool string")
        if not isinstance(call.get("arguments"), dict):
            raise ValueError("Every call needs an arguments object")
        env.call(call["tool"], call["arguments"])
    return grade(case, env, outcomes)


def summarize(results: list[dict]) -> dict:
    groups: dict[str, dict] = {}
    for result in results:
        key = result.get("controller", "submitted_trace")
        group = groups.setdefault(key, {"passed": 0, "tasks": 0, "extra_active_bookings": 0,
                                        "missing_active_bookings": 0, "tool_calls": 0})
        group["tasks"] += 1
        group["passed"] += int(result["passed"])
        for metric in ("extra_active_bookings", "missing_active_bookings", "tool_calls"):
            group[metric] += result[metric]
    return groups
