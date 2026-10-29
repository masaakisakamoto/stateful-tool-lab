# Offline tool and trace protocol

The environment is a synthetic in-memory fixture. This file is the future agent-facing tool contract; it contains no scenario-specific expected answers. Machine-readable input schemas are in `cases/tools.json`; the runtime also rejects whitespace-only identifiers.

## Tool calls

Every tool returns `{ "ok": true|false, "code": "...", "data": ... }`.

| Tool | Required string arguments | Optional string arguments |
|---|---|---|
| `create_booking` | `customer_id`, `slot_id` | `idempotency_key` |
| `cancel_booking` | `booking_id` | `idempotency_key` |
| `move_booking` | `booking_id`, `slot_id` | `idempotency_key` |
| `list_bookings` | none | `customer_id` |
| `get_operation` | `idempotency_key` | none |

Blank strings, unknown fields, and unknown tools return `invalid_arguments`. Identifiers are exact strings. Successful mutations return the booking record in `data`. Records have `id`, `customer_id`, `slot_id`, and `status` (`active` or `cancelled`). Listing includes cancelled records. `get_operation` returns the original successful response in `data`, or `not_found` if no successful keyed operation is recorded.

Codes: `ok`, `timeout`, `capacity`, `not_found`, `key_conflict`, `invalid_arguments`. Errors have `data: null`. Fault occurrence counts valid-schema calls of the named tool; malformed arguments do not consume a scheduled occurrence. A before fault applies before business execution; an after fault hides a response only when the call actually changes state.

A timeout does not establish whether a write committed. Reusing a successful idempotency key with the same tool and payload returns the original result; using that key with another payload or tool yields `key_conflict`. Errors are not cached. A failed move preserves the existing booking. Repeated cancellation of an existing cancelled booking is an `ok` no-op.

## Replay input

The JSON file is an array of entries:

```json
[
  {
    "case_id": "create-clean-en",
    "calls": [
      {
        "tool": "create_booking",
        "arguments": {"customer_id": "c1", "slot_id": "s1", "idempotency_key": "op-1"}
      }
    ],
    "outcomes": ["ok"]
  }
]
```

`outcomes` is the controller's report, one code per user request, not a trusted source of business truth. Calls are replayed in order against a fresh fixture. Submitted response objects and claimed final state are never used for grading. Failed outcomes need a matching observed tool response; a `list_bookings` observation establishing a full slot is also valid evidence for `capacity`. Creating and cancelling an extra booking does not erase that extra write for grading. Unrelated records must remain unchanged throughout execution. All 24 tasks are scored, including omitted tasks as failures. At most 20 calls per task are accepted. Any malformed trace, duplicate/unknown case ID, or exceeded budget invalidates the submission rather than producing a partial report.

The single example above is intentionally an incomplete submission and therefore fails the complete suite. `examples/reference-traces.json` supplies a complete deterministic submission.

## Separation for a future live adapter

- Agent-visible: language-specific instruction, public tool definitions, public slot catalogue with capacities, current tool responses, its own conversation.
- Evaluator-only: fault plan, structured reference requests, expected state, `snapshot()`, and the internal event log (`committed` included).
- Tool execution: a host-owned `BookingEnvironment.call` dispatcher, with a fixed call budget.

The current replay command is not an isolation layer. Public fixture files and Python objects are accessible to the host. A trusted evaluation runner or process boundary is required before publishing live results. Do not pass the whole case dictionary to a model. Capacity and slot identifiers must be presented to a future agent through a public catalogue or additional read tool; the current scripted demo obtains them from its structured requests.
