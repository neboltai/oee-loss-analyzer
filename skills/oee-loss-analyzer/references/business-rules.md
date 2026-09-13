# Business rules — limits, gates and thresholds

These rules bound what the analysis is allowed to assert. They are enforced in
code (`validate.py`, `classify_losses.py`, `analyse.py`) *and* must be honoured
in the prose of the report. Code cannot stop a confident sentence.

## 1. Data integrity gates (severity `error` — computation stops)

| Code | Condition | Why it blocks |
|---|---|---|
| `MISSING_FIELD` | any base field absent, or neither quality-count alternative supplied | the complete KPI contract cannot be evaluated |
| `QUALITY_COUNT_ALTERNATIVES` | both `good_count` and `reject_count` supplied | the canonical contract requires one unambiguous quality-count source |
| `NEGATIVE_VALUE` | any time or count < 0 | physically impossible |
| `ZERO_PLANNED_TIME` | `planned_production_time_min` ≤ 0 | division by zero |
| `ZERO_CYCLE_TIME` | `ideal_cycle_time_sec` ≤ 0 | Performance undefined |
| `DOWNTIME_EXCEEDS_PLANNED` | `downtime_min` > `planned_production_time_min` | negative run time |
| `GOOD_EXCEEDS_TOTAL` | `good_count` > `total_count` | Quality > 100 % |
| `IMPOSSIBLE_CYCLE_TIME` | `ICT x total_count` > run time (beyond tolerance) | Performance > 100 %: either the cycle time or a count is wrong |
| `EVENT_DOWNTIME_MISMATCH` | Σ event durations > `downtime_min` + tolerance | the log contradicts the total |
| `ZERO_TOTAL_COUNT_WITH_RUNTIME` | `total_count` = 0 while run time > 0 | either nothing ran (then run time is wrong) or counting failed |

On any error: return `status: "data_error"`, `metrics: null`, the issue list, and
what to correct. **Do not compute partial metrics around an error.** A reader
who sees three of four numbers will use them.

## 2. Data quality flags (severity `warning` — computation continues, claims are capped)

| Code | Condition | Effect |
|---|---|---|
| `EVENT_DOWNTIME_GAP` | Σ events < `downtime_min` − tolerance | gap → `unclassified_downtime` |
| `UNCLASSIFIED_DOWNTIME` | unclassified share > 20 % of downtime | cause claims capped at hypothesis |
| `NO_DOWNTIME_EVENTS` | downtime > 0 with no event log | availability causes unavailable |
| `NO_QUALITY_EVENTS` | rejects > 0 with no defect log | quality causes unavailable |
| `NO_SPEED_EVIDENCE` | performance loss > 0 with no speed log / micro-stop count | performance causes unavailable |
| `PLANNED_EVENT_INSIDE_PPT` | Group E code inside planned time | time model questioned, nothing removed |
| `LOW_SAMPLE` | single shift, or < 100 units produced | conclusions marked provisional |
| `ICT_SUSPICIOUS` | Performance > 98 % or < 40 % | ideal cycle time likely wrong |
| `UNMAPPED_REASON_CODES` | > 10 % of events unmapped | MES configuration finding |

## 3. The evidence gate

A statement about *why* a loss occurred is permitted only when all three hold
for the bucket it concerns:

1. **Attribution** — ≥ 60 % of the bucket's loss minutes carry a specific reason
   or defect code (`coverage ≥ 0.6`).
2. **Repetition** — ≥ 2 supporting events, or 1 event plus a corroborating record
   (maintenance work order, alarm, order boundary). Corroboration is relational:
   the record must resolve to the same asset, a compatible time window and a
   compatible component/reason family. A record merely present in the analysis
   period does not count. A single unexplained stop is an incident, not a pattern.
3. **Mechanism** — a plausible physical path from the evidence to the loss that
   the data does not contradict.

Fail any of the three → the statement moves from `problem`/`evidence` to
`hypothesis`, and the recommended action becomes an evidence-gathering step.

Fail attribution entirely (`coverage < 0.3`) for the *primary* loss → analysis
status is `insufficient_evidence`.

## 4. Hard prohibitions

- **Never invent missing production data.** No interpolation from neighbouring
  shifts, no plant averages, no "assume the standard 480-minute shift".
- **Never calculate missing production quantities** by inverting OEE or any
  other metric. If neither `good_count` nor `reject_count` is supplied, return
  `data_error`, `metrics: null`, and do not compute partial KPIs.
- **Never infer downtime causes without supporting events.** Unattributed
  minutes stay unattributed.
- **Do not confuse correlation and root cause.** Same-day maintenance, a shift
  boundary, a new operator, a new batch — all are leads, all belong under
  `hypothesis`. Promotion to a cause requires the evidence gate *and* a
  mechanism, not a tighter p-value.
- **Never silently repair inconsistent data.** Flag it, name the field, stop or
  continue per §1/§2 — but never rewrite the input.
- **Never blend measured and estimated values** in the same figure without a
  per-value marker.
- **Never attribute a loss to a named person or shift team.** OEE measures the
  process. Shift-level *differences* may be reported as a signal to investigate
  the process differences between shifts (standard work, staffing, material),
  never as performance appraisal.
- **Never recommend a process change off a single shift of data.** Recommend
  measurement first.

## 5. Insufficient evidence

When the gate fails, return exactly:

```json
{
  "status": "insufficient_evidence",
  "reason": "62 min of downtime carries no reason code; the largest loss cannot be attributed",
  "missing_evidence": [
    "reason codes on stop events DT-0007, DT-0011",
    "maintenance work orders for L1-PRESS-02 over the period",
    "cycle-time log to separate micro-stops from reduced speed"
  ],
  "what_is_still_valid": ["availability", "performance", "quality", "oee"]
}
```

`insufficient_evidence` concerns the *cause*, not the *metrics*. When the data
passes §1, the numbers are still returned and still valid — say so, so nobody
reads the status as "the analysis failed".

## 6. Confidence scoring

`confidence` is computed, never chosen:

```
confidence = 0.30                            # base for a metric-only finding
           + 0.40 x attribution_coverage     # 0..1 for the bucket concerned
           + 0.15 x evidence_channel_ratio   # of: events, quality, speed, maintenance
           + 0.15 x (1 - warning_penalty)    # 0.15 per warning, capped at 1.0
clipped to [0.05, 0.95]
```

Never 1.0. A shift of data does not justify certainty, and a round 1.0 reads as
a machine that has stopped thinking. Report to two decimals.

## 7. Configurable thresholds

Per-site overrides go in `config.thresholds` in the dataset, or `--config`:

| Threshold | Default |
|---|---|
| `minor_stop_threshold_min` | 5 |
| `event_sum_tolerance_min` | 1.0 |
| `cycle_time_tolerance_min` | 1.0 |
| `unclassified_downtime_ratio` | 0.20 |
| `significant_bucket_ratio` | 0.20 |
| `attribution_coverage_min` | 0.60 |
| `insufficient_evidence_below` | 0.30 |
| `low_sample_units` | 100 |
| `alarm_correlation_window_sec` | 300 |
| `maintenance_correlation_window_days` | 7 |
| `order_boundary_window_sec` | 900 |

Changing a threshold changes the findings. Always state the active thresholds in
the report footer.
