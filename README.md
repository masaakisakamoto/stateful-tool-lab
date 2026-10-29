# Stateful Tool Lab

**A small, reproducible fixture lab for booking-tool failures, with paired Japanese and English tasks.**

[日本語](README.ja.md) · [Research and selection](docs/RESEARCH.md) · [Experiment plan](docs/EXPERIMENTS.md) · [Tool and trace protocol](docs/PROTOCOL.md)

Status: **offline prototype, v0.1.0 — public source**. No external APIs, model calls, or runtime dependencies. Python 3.11+.

[![Verify offline fixtures](https://github.com/masaakisakamoto/stateful-tool-lab/actions/workflows/verify.yml/badge.svg)](https://github.com/masaakisakamoto/stateful-tool-lab/actions/workflows/verify.yml)

## The problem

A booking can be saved even when a tool returns a timeout. Retrying without a stable operation identity can create another booking. A fluent “done” is not enough to establish that the correct business state exists.

This repository makes those cases inspectable: synthetic initial state, explicit faults, tool calls, final-state expectations, and an independent deterministic grader. It is deliberately a small task pack and reference environment, rather than a new general-purpose agent framework.

## Quick start

From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m stateful_tool_lab demo --output results/demo.json
```

No installation, credentials, downloads, or network connection are needed. On Windows, `python` may be the appropriate executable.

The demo compares two **scripted controllers**. Both receive the same structured requests and retry a timeout once. `naive` sends unkeyed writes; `idempotent` reuses the request's operation ID as its idempotency key.

| Controller | Passed translated tasks | Extra active bookings | Tool calls |
|---|---:|---:|---:|
| Naive retry | 20 / 24 | 4 | 38 |
| Stable idempotency key | 24 / 24 | 0 | 38 |

These are fixture checks, **not model performance results**. The 24 tasks contain **12 independent scenarios, each in Japanese and English**. The extra bookings occur across translated copies of two scenarios: post-commit create timeout and duplicate delivery. This comparison is constructed to test whether the environment and grader detect known faults; it establishes neither AI capability nor production reliability.

## What is included

- Twelve manually specified scenarios: clean creation/cancellation/move; before/after-commit timeouts for each operation; occupied-slot creation/move; duplicate delivery.
- Original synthetic fixtures; no customer, employer, or production application data.
- Capacity-aware in-memory tools, atomic moves, an idempotency ledger, and one-shot fault scheduling.
- Final-state multiset checks, booking-identity checks, preservation of unrelated records throughout execution, excess-created-record checks, and evidence for reported failures.
- An offline trace-replay entry point, a 20-call budget, a full-dataset denominator, and a dataset SHA-256 in reports.
- A GitHub Actions workflow for Python 3.11, 3.12, and 3.13. Current hosted validation is shown in the workflow badge and Actions logs.

The grader does not enforce a single correct call sequence. Additional read-only verification calls are allowed.

## Evaluate normalized traces

```bash
python3 -m stateful_tool_lab evaluate --traces examples/reference-traces.json --output results/replayed.json
```

The example file contains traces from the deterministic keyed controller, **not captured model traces**. Replay executes every call against a fresh environment. It ignores any claimed final state. Missing tasks are failures and remain in the denominator; unknown or repeated case IDs are rejected. Exit codes: `0` = demo ran, or all evaluated tasks passed; `1` = evaluation has failures; `2` = invalid input or execution setup.

See [the protocol](docs/PROTOCOL.md) before supplying another controller's traces. This is not a live agent adapter or a secure sandbox. A future live adapter must give an agent only public instructions, tool descriptions, and tool responses, keeping faults, reference requests, gold state, and internal traces outside the agent observation.

## Current limitations

- No LLM has been evaluated. Structured reference requests bypass language understanding. Translated fixture parity does not establish a Japanese/English performance difference.
- No live model adapter, user simulator, ambiguous-date resolution, voice input, auth/permission boundary, external service, concurrency, persistent storage, crash recovery, or payment tool is implemented.
- Atomic `move_booking` is a simplifying environment assumption. Multi-service cancellation/rebooking and compensation are future tasks.
- Only one scheduled failure per scenario is used. There are no random failures or statistical confidence claims.
- Static traces can replay a fixed run, but cannot independently adapt to changed tool responses. Live closed-loop execution is a later milestone.
- The known negative control and keyed controller are constructed examples; they are not representative samples of deployed agents.
- The in-memory environment exposes evaluator methods to its Python host. It is not a security or anti-cheating boundary. Public fixtures may be studied, so these tasks should not be used as an uncontaminated leaderboard.

## Why build this now?

Recent work by LangChain, Google, GitHub, and Sierra points toward evaluating agent behavior and actual state changes. The useful contribution here is a narrow, transparent task pack, clear failure analysis, and reproducible experiments. Similar fault-injection and evaluation systems already exist; this repository does not claim a novel retry algorithm or to be the first Japanese benchmark. See the dated primary sources and alternatives in [RESEARCH.md](docs/RESEARCH.md).

## Next experiment

Add a closed-loop adapter to an existing evaluation runner; freeze the public observations and hidden grader boundary; evaluate selected models with matched settings over repeated runs; publish raw usage, configuration, traces, and failure analysis. API access and spend must be selected before that stage. The first release gate is documented in [EXPERIMENTS.md](docs/EXPERIMENTS.md).

## License and provenance

MIT for original code, documentation, and synthetic fixtures. No source or dataset was copied from the referenced projects. Research links describe inspiration and alternatives; they are not dependencies. Prepared with AI-assisted engineering and checked with local deterministic tests. The source was published on 2026-10-29. No tagged release, live-model result, or third-party adoption is claimed.
