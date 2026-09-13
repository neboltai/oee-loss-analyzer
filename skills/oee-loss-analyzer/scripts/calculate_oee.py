#!/usr/bin/env python3
"""Step 2 of the workflow: calculate OEE and the loss decomposition.

Usage:
    python3 calculate_oee.py dataset.json [--ruleset v0.4] [--json] [--force]

Refuses to compute when validation returns a blocking error, unless --force is
given (which is never the right answer in a report - it exists for debugging).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oee_lib import (DEFAULT_RULESET, RULESETS, calculate, has_errors,  # noqa: E402
                     load_dataset, thresholds_for, validate)


def main() -> int:
    ap = argparse.ArgumentParser(description="Calculate OEE from a validated dataset")
    ap.add_argument("dataset")
    ap.add_argument("--ruleset", default=DEFAULT_RULESET, choices=RULESETS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--force", action="store_true", help="compute despite blocking errors")
    args = ap.parse_args()

    ds = load_dataset(args.dataset)
    issues = validate(ds, ruleset=args.ruleset, th=thresholds_for(ds))
    if has_errors(issues) and not args.force:
        payload = {"status": "data_error", "metrics": None,
                   "issues": [i for i in issues if i["severity"] == "error"]}
        print(json.dumps(payload, indent=2) if args.json else
              "data_error - " + "; ".join(i["message"] for i in payload["issues"]))
        return 1

    m = calculate(ds, ruleset=args.ruleset)
    if m is None:
        print(json.dumps({"status": "data_error", "metrics": None}, indent=2)
              if args.json else "data_error - metrics are not computable from these fields")
        return 1

    if args.json:
        print(json.dumps(m, indent=2))
        return 0

    pct = lambda v: "n/a" if v is None else f"{v * 100:.2f}%"  # noqa: E731
    print(f"Availability {pct(m['availability'])}   "
          f"Performance {pct(m['performance'])}   "
          f"Quality {pct(m['quality'])}")
    print(f"OEE          {pct(m['oee'])}"
          + (f"   TEEP {pct(m['teep'])}" if m["teep"] is not None else ""))
    lm = m["loss_minutes"]
    print(f"\nPlanned production time {m['planned_production_time_min']:.1f} min "
          f"= fully productive {m['fully_productive_time_min']:.1f} + losses {lm['total']:.1f}")
    print(f"  availability loss {lm['availability']:.1f} min")
    print(f"  performance  loss {lm['performance']:.1f} min")
    print(f"  quality      loss {lm['quality']:.1f} min")
    print(f"\ncross-check (A x P x Q vs ICT x good / PPT): "
          f"{'ok' if m['cross_check_ok'] else 'MISMATCH - inputs are inconsistent'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
