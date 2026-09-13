#!/usr/bin/env python3
"""Step 1 of the workflow: validate a production dataset.

Usage:
    python3 validate.py dataset.json [--ruleset v0.4] [--json]

Exit code 0 = no blocking error, 1 = at least one severity:error issue.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oee_lib import DEFAULT_RULESET, RULESETS, has_errors, load_dataset, thresholds_for, validate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate an OEE production dataset")
    ap.add_argument("dataset")
    ap.add_argument("--ruleset", default=DEFAULT_RULESET, choices=RULESETS)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    ds = load_dataset(args.dataset)
    th = thresholds_for(ds)
    issues = validate(ds, ruleset=args.ruleset, th=th)

    if args.json:
        print(json.dumps({"issues": issues, "blocking": has_errors(issues)}, indent=2))
    else:
        if not issues:
            print("OK - no data integrity issues and no quality flags.")
        for i in issues:
            print(f"[{i['severity'].upper():7}] {i['code']:28} {i['field']}: {i['message']}")
        if has_errors(issues):
            print("\nBLOCKING: do not compute metrics. Report the data problem and stop.")
    return 1 if has_errors(issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
