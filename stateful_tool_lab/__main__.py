from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import __version__
from .runner import CASE_PATH, load_cases, replay, run_reference, summarize


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline stateful-tool fixture lab; no model/API calls.")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Compare two scripted retry controllers")
    demo.add_argument("--controller", choices=["all", "naive", "idempotent"], default="all")
    demo.add_argument("--output", type=Path, default=Path("results/demo.json"))
    evaluation = sub.add_parser("evaluate", help="Replay normalized tool traces against fresh fixtures")
    evaluation.add_argument("--traces", type=Path, required=True)
    evaluation.add_argument("--output", type=Path, default=Path("results/evaluation.json"))
    args = parser.parse_args()
    cases = load_cases()
    try:
        if args.command == "demo":
            controllers = ["naive", "idempotent"] if args.controller == "all" else [args.controller]
            results = [run_reference(case, controller) for controller in controllers for case in cases]
        else:
            traces = json.loads(args.traces.read_text(encoding="utf-8"))
            if not isinstance(traces, list):
                raise ValueError("Trace file must be an array")
            by_id = {}
            valid_ids = {case["id"] for case in cases}
            for trace in traces:
                if not isinstance(trace, dict) or not isinstance(trace.get("case_id"), str):
                    raise ValueError("Each trace needs a case_id string")
                case_id = trace["case_id"]
                if case_id not in valid_ids or case_id in by_id:
                    raise ValueError(f"Unknown or duplicate case_id: {case_id}")
                by_id[case_id] = trace
            # Missing tasks remain in the denominator, preventing selective reporting.
            results = []
            for case in cases:
                trace = by_id.get(case["id"], {"calls": [], "outcomes": []})
                result = replay(case, trace)
                result["submitted"] = case["id"] in by_id
                if not result["submitted"]:
                    result["checks"]["trace_submitted"] = False
                    result["passed"] = False
                results.append(result)
        report = {
            "version": __version__,
            "mode": "scripted_controller_demo" if args.command == "demo" else "offline_trace_replay",
            "model_evaluated": False,
            "dataset_sha256": hashlib.sha256(CASE_PATH.read_bytes()).hexdigest(),
            "independent_scenarios": len({c["scenario_id"] for c in cases}),
            "tasks_including_translations": len(cases),
            "summary": summarize(results), "results": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"mode": report["mode"], "model_evaluated": False,
                          "summary": report["summary"], "output": str(args.output)}, ensure_ascii=False, indent=2))
        return int(args.command == "evaluate" and any(not r["passed"] for r in results))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
