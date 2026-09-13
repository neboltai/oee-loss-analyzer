---
name: oee-loss-analyzer
description: >
  Analyze manufacturing OEE data and identify significant availability,
  performance and quality losses. Use when the user provides production data,
  machine events, downtime logs, shift reports or another production record, or
  asks for an OEE loss analysis, an OEE calculation, a downtime Pareto, a
  Six Big Losses breakdown, or "why is this line losing output".
allowed-tools: Read, Write, Bash, Glob, Grep
---

# OEE Loss Analyzer

## Objective

Turn raw production data into a defensible loss analysis: correct OEE numbers,
losses classified against the Six Big Losses, and a clear separation between
what the data proves and what is still a hypothesis.

Never optimise for a confident-sounding answer. Optimise for an answer a plant
manager can take to the shopfloor without being contradicted by the data.

## Required inputs

Minimum viable dataset (the analysis cannot start without the first four fields
and exactly one of the two quality-count alternatives):

| Field | Unit | Notes |
|---|---|---|
| `planned_production_time_min` | minutes | scheduled time, excluding planned non-production |
| `downtime_min` | minutes | all unplanned stop time inside the planned time |
| `ideal_cycle_time_sec` | seconds/unit | theoretical fastest cycle, not the average |
| `total_count` | units | everything produced, good and bad |
| `good_count` **or** `reject_count` | units | exactly one; first-pass-good or rejects, never both |

Strengthening evidence (optional, but they are what turns a hypothesis into a
finding): `downtime_events[]` with reason codes, `quality_events[]` with defect
codes and phase, `micro_stops`/`speed_log`, `orders[]`, `maintenance_history[]`.

## Workflow

Follow in order. Do not skip steps, do not reorder.

1. **Validate the production dataset.** Run
   `scripts/validate.py <dataset.json>`. Read every issue it returns. Any
   `severity: error` stops the analysis — report the data problem, do not
   compute around it.
2. **Run the calculation.** Run `scripts/calculate_oee.py <dataset.json>`.
   It returns Availability, Performance, Quality, OEE, TEEP where computable,
   and the loss decomposition in minutes. Never compute OEE by hand and never
   restate numbers the script did not produce.
3. **Classify losses** according to `references/loss-categories.md` and the
   reason-code nomenclature in `references/downtime-classification.md`. Run
   `scripts/classify_losses.py <dataset.json>`.
4. **Investigate significant deviations.** A deviation is significant when a
   single bucket holds ≥ 20 % of total loss minutes, or a metric is more than
   10 points below its world-class benchmark (`references/oee.md`). Work the
   largest loss first; ignore the rest for now.
5. **Do not infer root causes without supporting evidence.** Apply the evidence
   rules in `references/business-rules.md`. A corroborating record must be tied
   to a specific loss event by asset, compatible time window and technical
   family; mere presence of an alarm or work order is not corroboration.
   If the dominant loss has no classified events behind it, the analysis status
   is `insufficient_evidence` and the output names the evidence that is missing.
6. **Return findings using the report template** in `assets/report-template.md`,
   plus the machine-readable finding objects specified in
   `references/output-schema.md`.

`scripts/analyse.py <dataset.json>` runs steps 1–3 and 5 in one pass and emits
the full JSON result; prefer it for normal runs and use the individual scripts
when a step needs isolating.

## Rules

These are hard constraints. Violating one invalidates the analysis.

- **Never invent missing production data.** No interpolation, no "assume a
  typical shift", no back-calculating `total_count` from OEE. Missing is missing.
- **Never calculate missing production quantities** from other metrics. If
  neither `good_count` nor `reject_count` exists, validation returns
  `data_error`, no KPI block is calculated, and the missing alternative is
  named. Supplying both alternatives is also a blocking contract error.
- **Never infer downtime causes without supporting events.** Unattributed
  downtime stays `unclassified`; it never becomes "probably a breakdown".
- **Do not confuse correlation and root cause.** A maintenance entry on the same
  day, a shift change near a stop, a new batch number — these are leads, listed
  under `hypothesis`, never under a root-cause claim.
- **Clearly distinguish facts from hypotheses** in every sentence you write.
  Facts cite a field or an event id. Hypotheses are labelled as such.
- **Flag inconsistent data** rather than silently correcting it: Performance
  > 100 %, downtime exceeding planned time, good count above total count,
  events summing to more than the reported downtime.
- **If evidence is insufficient, return `"insufficient_evidence"`** for that
  finding, with the concrete data that would resolve it. An honest
  `insufficient_evidence` beats a plausible guess every time.
- **Never present a measured number and an estimated number in the same list
  without marking which is which.**

## Getting the data

The Community Edition does not connect to a production system. When the user
has not attached a canonical dataset, ask for a reviewed JSON dataset or a
reviewed export that can be normalised first.

The bundled `shopfloor-data` MCP server is a local demonstration over
fictional records only. It exposes the intended production-tool contract:

| Tool | Returns |
|---|---|
| `get_production_data(machine_id, date_from, date_to, shift?)` | counts, planned time, cycle times |
| `get_downtime(machine_id, date_from, date_to)` | stop events with reason codes |
| `get_machine_events(machine_id, date_from, date_to)` | telemetry, speed log, micro-stops, alarms |
| `get_orders(machine_id, date_from, date_to)` | order/changeover context |
| `get_maintenance_history(machine_id, date_from, date_to)` | work orders, part replacements |

For a demo, call `get_production_data` and `get_downtime` first; add the
other tools when step 4 needs evidence. Merge tool results into one dataset and
run the workflow on it. Never describe this mock MCP as a connection to the
user's MES, ERP or database.

`references/input-formats.md` provides review and normalisation guidance for
CSV, Excel, JSON, PDF shift reports, images, system exports and free text. It
does not represent bundled production-ready parsers or connectors.

## Output

Return both, in this order:

1. The rendered report from `assets/report-template.md`: OEE, Availability,
   Performance, Quality, top losses, probable causes, missing evidence,
   recommended investigation.
2. A `findings[]` array of objects validating against
   `assets/finding.schema.json`:

```json
{
  "problem": "Availability loss of 62 min concentrated on press L1-PRESS-02",
  "evidence": ["DT-0031 MECH_FAIL 35 min", "DT-0034 MECH_FAIL 18 min"],
  "hypothesis": ["Hydraulic pressure drop recurring after tool change"],
  "recommended_action": ["Log hydraulic pressure at each tool change for 5 shifts"],
  "confidence": 0.82,
  "cause_claimed": true,
  "corroboration": [
    {
      "type": "alarm",
      "event_id": "DT-0031",
      "record_id": "AL-9182",
      "temporal_distance_sec": 18,
      "machine_match": true,
      "family_match": ["hydraulic"],
      "match_basis": ["same_machine", "compatible_time_window", "compatible_family"]
    }
  ]
}
```

`confidence` is a deterministic evidence-coverage score produced by the
scripts; it is not a statistically calibrated probability and must not be set
by feel. `cause_claimed` only means that the encoded evidence gate passed; it
does not replace a verified root-cause investigation. When the status is
`insufficient_evidence`, `hypothesis` may be populated but
`recommended_action` must be an evidence-gathering step, never a change to the
process.

## Reference library

Load on demand, not upfront:

- `references/oee.md` — definitions, formulas, TEEP, benchmarks, time model
- `references/six-big-losses.md` — the six losses and how each shows up in data
- `references/downtime-classification.md` — reason-code nomenclature
- `references/loss-categories.md` — mapping table used in step 3
- `references/business-rules.md` — evidence gating, thresholds, refusal rules
- `references/lean-analysis-method.md` — Pareto, 5 Why, Ishikawa, PDCA discipline
- `references/toyota-production-system.md` — jidoka, genchi genbutsu, muda/mura/muri
- `references/input-formats.md` — how to normalise each input type
- `references/output-schema.md` — exact JSON contract
- `tests/` — 55 evaluation cases with known expected behaviour;
  `scripts/run_evals.py` scores the engine against them
