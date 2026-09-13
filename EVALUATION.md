# Evaluation

55 cases with known expected behaviour, in
`skills/oee-loss-analyzer/tests/`. Run them:

```bash
python3 skills/oee-loss-analyzer/scripts/run_evals.py --all --verbose
```

## What is measured

| Dimension | Passes when |
|---|---|
| **Correct classification** | the primary loss bucket is the expected one (and a tie is reported as a tie) |
| **Correct numerical analysis** | Availability, Performance, Quality and OEE match the expectation to 4 decimals — or are correctly `null` |
| **Unsupported assumptions** | *lower is better*: a root cause was claimed where the evidence gate forbids it |
| **Correct uncertainty handling** | `status` matches (`ok` / `insufficient_evidence` / `data_error`) **and** confidence falls inside the expected band |
| Expected flags raised | *unscored*: every data-quality flag the case should trigger was raised |
| Corroboration links | *unscored*: exact `(type, event_id, record_id)` relations match the adversarial expectation |

Expected metrics are computed in the case generator straight from the OEE
formulas, independently of the engine, so the numerical dimension is a real
cross-check and not the engine grading itself. The behavioural expectations
(bucket, status, claim allowed, flags) were written per case from the rules in
`references/business-rules.md` before the engine was run against them.

## Results, measured

Four rulesets ship in `scripts/oee_lib.py` so the skill can be benchmarked
against its own earlier behaviour. All four run the same 55 cases.

```
ruleset       class  numeric   unsupp   uncert   overall
v0.1          26/55    48/55    22/55    43/55       68%
v0.2          43/55    54/55    11/55    49/55       86%
v0.3          54/55    54/55     4/55    54/55       97%
v0.4          55/55    55/55     0/55    55/55      100%
```

`overall` is the mean of the four scored dimensions, with unsupported
assumptions inverted.

### Version 0.1 — naive baseline (68 %)

Computes OEE, ranks losses, always names a cause. No validation, no reason-code
classification, no notion of missing evidence.

| Result | Why |
|---|---|
| classification 26/55 | every stop treated as a breakdown; setup, external and micro-stop cases are misfiled |
| numerical 48/55 | computes through impossible data: Performance above 100 %, negative run time |
| unsupported assumptions 22/55 | asserts a cause on datasets with no support or unrelated records |
| uncertainty 43/55 | no `insufficient_evidence`, no `data_error` — it is never unsure |

### Version 0.2 — validated and code-aware (86 %)

Added the integrity gates and classification by reason-code family, plus the
data-quality flags.

| Result | Why the rest still failed |
|---|---|
| classification 43/55 | no duration escalation; performance and quality evidence are not yet split |
| numerical 54/55 | integrity gates catch the original impossible-data cases, but not the new dual-count contract case |
| unsupported assumptions 11/55 | claims a cause whenever any event exists — no coverage floor, no repetition rule |
| uncertainty 49/55 | `data_error` exists, `insufficient_evidence` does not |

### Version 0.3 — presence-based corroboration (97 %)

Added, in this order, each for a failure class above:

1. **Duration escalation** — a Group C code at or above the minor-stop threshold
   becomes a breakdown (fixed `breakdown-escalated-jam`, `microstops-escalation-boundary`).
2. **Evidence-typed performance split** — micro-stop minutes and speed-log
   minutes are separated; performance loss with neither becomes
   `unclassified_performance` (fixed `microstops`, `microstops-unrecorded`,
   `reduced-speed-partial-micro`).
3. **Quality phase split** — `startup` vs `steady_state` separates loss 6 from
   loss 5; `unknown` blocks the split (fixed `quality-mixed-phase`,
   `startup-rejects-dominant`, `quality-phase-unknown`).
4. **The evidence gate** — attribution coverage ≥ 60 %, ≥ 2 supporting events or
   one plus corroboration, and a cap when unclassified downtime exceeds 20 % or
   the cycle-time basis is in doubt (removed all 7 remaining unsupported
   assumptions).
5. **`insufficient_evidence` as a first-class status** — with the metrics still
   reported and the missing records named (fixed the last 5 uncertainty cases).

Its remaining weakness is exactly the one addressed in v0.4: any alarm or work
order anywhere in the dataset counted as corroboration. The new adversarial
cases expose four unsupported claims, and the strict dual-count case exposes
one contract gap.

### Version 0.4 — current (100 %)

1. **Relational corroboration** — an alarm, maintenance record or order boundary
   counts only when it is joined to a specific primary-loss event by machine,
   compatible time window and technical family/mechanism.
2. **Auditable relation output** — each match returns `type`, `event_id`,
   `record_id`, time distance, matched family and the exact match basis.
3. **Strict quality-count contract** — exactly one of `good_count` or
   `reject_count` is required; neither or both produce `data_error` with no
   partial KPI block.
4. **Adversarial coverage** — same-period unrelated alarms/work orders and a
   technically matching alarm on the wrong machine are rejected.

## Honest reading of the 100 %

The harness is deterministic: it scores the rule engine in
`scripts/oee_lib.py`, not a model's judgement. 55/55 means the rules are
implemented as specified and are self-consistent across the case set — it does
**not** mean an LLM following `SKILL.md` will be right 55 times out of 55 on
free-form plant data. The two things it does buy:

- every number in a report comes from code that has been checked against
  independently computed expectations;
- the refusal behaviour (`data_error`, `insufficient_evidence`, no cause claim)
  is mechanical, so it does not depend on the model resisting the pull toward a
  confident answer.

What it does not cover, and where a judged eval is still needed: input
normalisation from messy CSV, Excel, PDF and images; the quality of the
prose in the report; hypothesis relevance; and whether the recommended
investigation is the one a plant would actually run.

## Case inventory

| Category | Cases | What they exercise |
|---|---|---|
| normal | 5 | healthy shifts, different dominant buckets |
| downtime | 8 | breakdowns, corroboration, escalation, partial coverage, exact tie |
| setup | 5 | changeover, first article, tool change, material changeover |
| quality | 5 | process defects, startup rejects, phase split, unknown phase |
| microstops | 5 | logged and unlogged micro-stops, threshold boundary |
| speed | 4 | reduced speed, suspicious ideal cycle time, partial micro-stop split |
| external | 4 | material shortage, no operator, upstream block, planned event inside PPT |
| missing | 7 | absent fields, dual quality counts, uncoded downtime, no defect log, unstructured intake |
| impossible | 7 | cycle time, downtime, counts, negative values, event mismatch, zero values |
| mapping | 1 | German reason texts through `code_map` |
| corroboration | 4 | unrelated alarm/work order, wrong machine, valid maintenance link |

## Adding a case

Copy any file in `tests/`, change the `dataset` and the `expected` block, and
re-run. The expected block is:

```json
{
  "status": "ok | insufficient_evidence | data_error",
  "metrics": {"availability": 0.0, "performance": 0.0, "quality": 0.0, "oee": 0.0},
  "primary_loss_bucket": "breakdowns",
  "root_cause_claim_allowed": true,
  "confidence_range": [0.70, 0.95],
  "must_flag": ["UNCLASSIFIED_DOWNTIME"],
  "tie_with": []
}
```

Set `metrics` to `null` for a `data_error` case. Compute the expected metrics by
hand or from the formulas — never by running the engine and pasting its output,
which turns the numerical dimension into a tautology.
