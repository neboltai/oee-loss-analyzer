#!/usr/bin/env python3
"""Score the analysis engine against the evaluation cases in tests/.

Usage:
    python3 run_evals.py                       # current ruleset (v0.4)
    python3 run_evals.py --ruleset v0.1        # baseline
    python3 run_evals.py --all                 # every ruleset side by side
    python3 run_evals.py --verbose             # list every failing case
    python3 run_evals.py --json results.json

Four scored dimensions, matching references/business-rules.md:

  correct numerical analysis   metrics match the independently computed
                               expectation to 4 decimals, or are correctly null
  correct classification       the primary loss bucket is the expected one
  unsupported assumptions      a root cause was claimed where the evidence gate
                               forbids it  (lower is better)
  correct uncertainty handling status matches AND confidence falls in the
                               expected band

A fifth, unscored line reports whether the expected data-quality flags were
raised, because a flag that never fires is a rule that does not exist.
The relation check is also reported separately: it verifies the exact
event-to-record corroboration pairs expected by adversarial cases.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oee_lib import DEFAULT_RULESET, RULESETS, analyse  # noqa: E402

TESTS = Path(__file__).resolve().parent.parent / "tests"
TOL = 1e-4


def load_cases(directory: Path) -> list[dict]:
    cases = []
    for p in sorted(directory.glob("*.json")):
        with open(p, encoding="utf-8") as fh:
            c = json.load(fh)
        if "expected" in c and "dataset" in c:
            c["_path"] = str(p)
            cases.append(c)
    return cases


def metrics_match(expected, actual) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    for k in ("availability", "performance", "quality", "oee"):
        a, e = actual.get(k), expected.get(k)
        if e is None or a is None:
            if e is not a:
                return False
            continue
        if abs(float(a) - float(e)) > TOL:
            return False
    return True


def score_case(case: dict, ruleset: str) -> dict:
    exp = case["expected"]
    res = analyse(case["dataset"], ruleset=ruleset)

    numerical = metrics_match(exp["metrics"], res.get("metrics"))

    got_primary = (res.get("primary_loss") or {}).get("bucket")
    classification = got_primary == exp["primary_loss_bucket"]

    claimed = bool(res.get("root_cause_claimed"))
    unsupported = claimed and not exp["root_cause_claim_allowed"]

    lo, hi = exp["confidence_range"]
    conf = res.get("confidence", 0.0)
    uncertainty = (res["status"] == exp["status"]) and (lo - 1e-9 <= conf <= hi + 1e-9)

    raised = {i["code"] for i in res.get("issues", [])}
    flags_ok = all(f in raised for f in exp.get("must_flag", []))

    tie_ok = True
    if exp.get("tie_with"):
        tie_ok = sorted((res.get("primary_loss") or {}).get("tie_with", [])) == sorted(exp["tie_with"])

    got_pairs = sorted(
        (m.get("type"), m.get("event_id"), m.get("record_id"))
        for m in res.get("corroboration_matches", [])
    )
    expected_pairs = sorted(tuple(x) for x in exp.get("corroboration_pairs", []))
    links_ok = got_pairs == expected_pairs if "corroboration_pairs" in exp else True

    return {
        "id": case["id"], "category": case["category"],
        "numerical": numerical, "classification": classification,
        "unsupported": unsupported, "uncertainty": uncertainty,
        "flags": flags_ok, "tie": tie_ok, "links": links_ok,
        "got": {"status": res["status"], "primary": got_primary,
                "claimed": claimed, "confidence": conf,
                "corroboration_pairs": got_pairs,
                "metrics": res.get("metrics"),
                "missing_flags": sorted(set(exp.get("must_flag", [])) - raised)},
        "expected": {"status": exp["status"], "primary": exp["primary_loss_bucket"],
                     "claim_allowed": exp["root_cause_claim_allowed"],
                     "confidence_range": exp["confidence_range"],
                     "metrics": exp["metrics"]},
    }


def run(ruleset: str, cases: list[dict]) -> dict:
    rows = [score_case(c, ruleset) for c in cases]
    n = len(rows)
    agg = {
        "ruleset": ruleset,
        "cases": n,
        "correct_numerical": sum(r["numerical"] for r in rows),
        "correct_classification": sum(r["classification"] for r in rows),
        "unsupported_assumptions": sum(r["unsupported"] for r in rows),
        "correct_uncertainty": sum(r["uncertainty"] for r in rows),
        "expected_flags_raised": sum(r["flags"] for r in rows),
        "ties_correct": sum(r["tie"] for r in rows),
        "corroboration_links_correct": sum(r["links"] for r in rows),
    }
    # overall = mean of the four scored dimensions (unsupported inverted)
    agg["overall"] = round(
        (agg["correct_numerical"] + agg["correct_classification"]
         + (n - agg["unsupported_assumptions"]) + agg["correct_uncertainty"])
        / (4.0 * n), 4)
    agg["rows"] = rows
    return agg


def print_report(agg: dict, verbose: bool) -> None:
    n = agg["cases"]
    print(f"\n=== ruleset {agg['ruleset']} - {n} test cases ===")
    print(f"Correct classification        {agg['correct_classification']:3d} / {n}")
    print(f"Correct numerical analysis    {agg['correct_numerical']:3d} / {n}")
    print(f"Unsupported assumptions       {agg['unsupported_assumptions']:3d} / {n}   (lower is better)")
    print(f"Correct uncertainty handling  {agg['correct_uncertainty']:3d} / {n}")
    print(f"Expected flags raised         {agg['expected_flags_raised']:3d} / {n}   (unscored)")
    print(f"Corroboration links correct   {agg['corroboration_links_correct']:3d} / {n}   (unscored)")
    print(f"OVERALL                       {agg['overall'] * 100:.0f}%")
    if verbose:
        for r in agg["rows"]:
            bad = [k for k in ("numerical", "classification", "uncertainty") if not r[k]]
            if r["unsupported"]:
                bad.append("unsupported_assumption")
            if not r["flags"]:
                bad.append(f"flags_missing={r['got']['missing_flags']}")
            if not r["tie"]:
                bad.append("tie")
            if not r["links"]:
                bad.append("corroboration_links")
            if bad:
                print(f"  FAIL {r['id']:38} {', '.join(bad)}")
                print(f"       expected {r['expected']}")
                print(f"       got      {r['got']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Score the OEE engine against the eval set")
    ap.add_argument("--ruleset", default=DEFAULT_RULESET, choices=RULESETS)
    ap.add_argument("--all", action="store_true", help="run every ruleset")
    ap.add_argument("--tests", default=str(TESTS))
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", help="write full results to this file")
    args = ap.parse_args()

    cases = load_cases(Path(args.tests))
    if not cases:
        print(f"no test cases found in {args.tests}", file=sys.stderr)
        return 2

    rulesets = list(RULESETS) if args.all else [args.ruleset]
    results = []
    for rs in rulesets:
        agg = run(rs, cases)
        results.append(agg)
        print_report(agg, args.verbose)

    if len(results) > 1:
        print("\n=== version comparison ===")
        print(f"{'ruleset':10} {'class':>8} {'numeric':>8} {'unsupp':>8} {'uncert':>8} {'overall':>9}")
        for a in results:
            print(f"{a['ruleset']:10} {a['correct_classification']:5d}/{a['cases']:<2d} "
                  f"{a['correct_numerical']:5d}/{a['cases']:<2d} "
                  f"{a['unsupported_assumptions']:5d}/{a['cases']:<2d} "
                  f"{a['correct_uncertainty']:5d}/{a['cases']:<2d} "
                  f"{a['overall'] * 100:8.0f}%")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwritten: {args.json}")

    failing = results[-1]["cases"] - results[-1]["correct_classification"]
    return 0 if failing == 0 else 0  # scoring run never fails the shell


if __name__ == "__main__":
    raise SystemExit(main())
