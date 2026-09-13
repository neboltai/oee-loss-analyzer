#!/usr/bin/env python3
"""Full OEE loss analysis: validate, calculate, classify, gate on evidence.

Usage:
    python3 analyse.py dataset.json                 # JSON result (default)
    python3 analyse.py dataset.json --report        # rendered markdown report
    python3 analyse.py dataset.json --ruleset v0.1  # benchmark baseline
    python3 analyse.py dataset.json --config cfg.json

Output contract: references/output-schema.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oee_lib import DEFAULT_RULESET, RULESETS, analyse, load_dataset  # noqa: E402

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "report-template.md"


def pct(v, nd=1):
    return "n/a" if v is None else f"{v * 100:.{nd}f}%"


def render_report(res: dict) -> str:
    meta = res.get("meta") or {}
    head = (f"# OEE loss analysis - {meta.get('machine_id', 'unknown asset')}"
            f"{' / ' + str(meta.get('shift')) if meta.get('shift') else ''}"
            f"{' / ' + str(meta.get('date')) if meta.get('date') else ''}")
    lines = [head, ""]
    lines.append(f"**Status:** `{res['status']}`"
                 + (f" - {res.get('reason')}" if res.get("reason") else ""))
    lines.append(f"**Data source:** {meta.get('source', 'not stated')}  |  "
                 f"**Engine:** {res['engine_version']} ({res['ruleset']})")
    lines.append("")

    if res["status"] == "data_error":
        lines.append("## The data blocks the analysis")
        lines.append("")
        lines.append("No metrics are reported: computing around a data integrity error "
                     "produces numbers that look usable and are not.")
        lines.append("")
        for i in res["issues"]:
            if i["severity"] == "error":
                lines.append(f"- **{i['code']}** (`{i['field']}`): {i['message']}")
        lines.append("")
        lines.append("### To unblock")
        for m in res.get("missing_evidence", []):
            lines.append(f"- {m}")
        return "\n".join(lines) + "\n"

    m = res["metrics"]
    lines += [
        "## Metrics", "",
        "| Metric | Value | World class | Gap |",
        "|---|---|---|---|",
        f"| Availability | {pct(m['availability'], 2)} | 90.0% | "
        f"{(m['availability'] - 0.90) * 100:+.1f} pt |",
        f"| Performance | {pct(m['performance'], 2)} | 95.0% | "
        f"{(m['performance'] - 0.95) * 100:+.1f} pt |",
        f"| Quality | {pct(m['quality'], 2)} | 99.9% | "
        f"{(m['quality'] - 0.999) * 100:+.1f} pt |",
        f"| **OEE** | **{pct(m['oee'], 2)}** | **85.0%** | "
        f"**{(m['oee'] - 0.85) * 100:+.1f} pt** |",
        "",
        f"Planned production time {m['planned_production_time_min']:.0f} min = "
        f"fully productive {m['fully_productive_time_min']:.0f} min + "
        f"losses {m['loss_minutes']['total']:.0f} min "
        f"(availability {m['loss_minutes']['availability']:.0f}, "
        f"performance {m['loss_minutes']['performance']:.0f}, "
        f"quality {m['loss_minutes']['quality']:.0f}). "
        f"Cross-check: {'ok' if m['cross_check_ok'] else 'MISMATCH'}.",
        "",
        "## Top losses", "",
        "| Bucket | Loss | Share | Factor | Six Big Loss | Events | Attributed |",
        "|---|---|---|---|---|---|---|",
    ]
    for l in res["losses"][:8]:
        lines.append(
            f"| {l['bucket'].replace('_', ' ')} | {l['loss_minutes']:.0f} min | "
            f"{l['share_of_total_loss'] * 100:.0f}% | {l['factor']} | "
            f"{l['six_big_loss'] or '-'} | {l['event_count']} | "
            f"{'yes' if l['coverage'] >= 1 else 'no'} |")
    lines.append("")

    lines += ["## Findings", ""]
    if not res["findings"]:
        lines.append("_No loss large enough to report._")
    for f in res["findings"]:
        lines.append(f"### {f['problem']}")
        lines.append("")
        lines.append(f"*Cause established:* {'yes' if f.get('cause_claimed') else 'no - hypothesis stage'}"
                     f"  |  *Confidence:* {f['confidence']:.2f}")
        lines.append("")
        lines.append("**Evidence (verifiable records)**")
        lines += [f"- {e}" for e in f["evidence"]] or ["- none"]
        lines.append("")
        if f.get("corroboration"):
            lines.append("**Corroboration links**")
            for c in f["corroboration"]:
                families = ", ".join(c["family_match"])
                lines.append(
                    f"- {c['type']}: `{c['event_id']}` ↔ `{c['record_id']}`; "
                    f"same machine, {c['temporal_distance_sec']:.0f} s apart, "
                    f"family `{families}`"
                )
            lines.append("")
        lines.append("**Hypotheses (not established)**")
        lines += [f"- {h}" for h in f["hypothesis"]] or ["- none"]
        lines.append("")
        lines.append("**Recommended next step**")
        lines += [f"- {a}" for a in f["recommended_action"]] or ["- none"]
        lines.append("")

    if res.get("missing_evidence"):
        lines += ["## Missing evidence", ""]
        lines += [f"- {x}" for x in res["missing_evidence"]]
        lines.append("")

    warns = [i for i in res["issues"] if i["severity"] == "warning"]
    if warns:
        lines += ["## Data quality flags", ""]
        lines += [f"- **{i['code']}**: {i['message']}" for i in warns]
        lines.append("")

    th = res["thresholds"]
    lines += ["---", "",
              f"Thresholds in force: minor stop {th['minor_stop_threshold_min']:.0f} min, "
              f"significance {th['significant_bucket_ratio']:.0%}, "
              f"attribution floor {th['attribution_coverage_min']:.0%}, "
              f"insufficient evidence below {th['insufficient_evidence_below']:.0%}, "
              f"alarm link {th['alarm_correlation_window_sec']:.0f} s, "
              f"maintenance link {th['maintenance_correlation_window_days']:.0f} days.",
              "",
              "Findings marked *hypothesis stage* are not causes. Correlation in time is "
              "not evidence of causation."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Full OEE loss analysis")
    ap.add_argument("dataset")
    ap.add_argument("--ruleset", default=DEFAULT_RULESET, choices=RULESETS)
    ap.add_argument("--report", action="store_true", help="render the markdown report")
    ap.add_argument("--config", help="JSON file with threshold overrides")
    ap.add_argument("--out", help="write the result to this file instead of stdout")
    args = ap.parse_args()

    ds = load_dataset(args.dataset)
    overrides = None
    if args.config:
        with open(args.config, encoding="utf-8") as fh:
            cfg = json.load(fh)
        overrides = cfg.get("thresholds", cfg)

    res = analyse(ds, ruleset=args.ruleset, threshold_overrides=overrides)
    text = render_report(res) if args.report else json.dumps(res, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written: {args.out}")
    else:
        print(text)
    return 0 if res["status"] != "data_error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
