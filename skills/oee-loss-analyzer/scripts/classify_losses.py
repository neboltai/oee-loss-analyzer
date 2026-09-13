#!/usr/bin/env python3
"""Step 3 of the workflow: classify losses against the Six Big Losses.

Usage:
    python3 classify_losses.py dataset.json [--ruleset v0.4] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oee_lib import (DEFAULT_RULESET, RULESETS, calculate, classify,  # noqa: E402
                     has_errors, load_dataset, thresholds_for, validate)


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify OEE losses into buckets")
    ap.add_argument("dataset")
    ap.add_argument("--ruleset", default=DEFAULT_RULESET, choices=RULESETS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ds = load_dataset(args.dataset)
    th = thresholds_for(ds)
    issues = validate(ds, ruleset=args.ruleset, th=th)
    if has_errors(issues):
        print(json.dumps({"status": "data_error", "issues":
                          [i for i in issues if i["severity"] == "error"]}, indent=2))
        return 1

    metrics = calculate(ds, ruleset=args.ruleset)
    if metrics is None:
        print(json.dumps({"status": "data_error"}, indent=2))
        return 1
    cls = classify(ds, metrics, ruleset=args.ruleset, th=th)

    if args.json:
        print(json.dumps(cls, indent=2))
        return 0

    print(f"total loss {cls['total_loss_minutes']:.1f} min\n")
    print(f"{'bucket':32} {'factor':12} {'min':>8} {'share':>7} {'events':>7} {'cov':>5}")
    for l in cls["losses"]:
        print(f"{l['bucket']:32} {l['factor']:12} {l['loss_minutes']:8.1f} "
              f"{l['share_of_total_loss'] * 100:6.1f}% {l['event_count']:7d} {l['coverage']:5.1f}"
              + ("  *significant" if l["significant"] else ""))
        for n in l["notes"]:
            print(f"{'':32} note: {n}")
    p = cls["primary_loss"]
    if p:
        tie = f" (tie with {', '.join(p['tie_with'])})" if p["tie_with"] else ""
        print(f"\nprimary loss: {p['bucket']} - {p['loss_minutes']:.1f} min, "
              f"{p['share_of_total_loss'] * 100:.0f}% of total loss, coverage {p['coverage']:.0%}{tie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
