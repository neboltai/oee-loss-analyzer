# Output schema

The contract between the engine, the skill and any downstream consumer.
`scripts/analyse.py` emits exactly this object. Schemas:
`assets/finding.schema.json`, `assets/dataset.schema.json`.

## Top level

```json
{
  "schema_version": "1.0",
  "engine_version": "0.4.0",
  "ruleset": "v0.4",
  "meta": { "machine_id": "L1-PRESS-02", "shift": "S2", "date": "2026-09-08" },
  "status": "ok",
  "issues": [],
  "metrics": { },
  "losses": [ ],
  "primary_loss": { },
  "corroboration_matches": [ ],
  "findings": [ ],
  "missing_evidence": [ ],
  "thresholds": { }
}
```

### `status` — three values, no others

| Value | Meaning | `metrics` | `findings` |
|---|---|---|---|
| `ok` | data valid, primary loss attributable | populated | cause-level findings permitted |
| `insufficient_evidence` | data valid, primary loss **not** attributable | populated and valid | hypotheses only; actions are evidence-gathering |
| `data_error` | a §1 integrity gate failed | `null` | none; the finding is the data problem |

`insufficient_evidence` never means "no answer". The metrics are returned and
are correct — `what_is_still_valid` names them explicitly.

### `issues[]`

```json
{"code": "UNCLASSIFIED_DOWNTIME", "severity": "warning",
 "field": "downtime_events", "message": "38 of 62 downtime minutes carry no reason code (61%)"}
```

`severity` ∈ `error` | `warning` | `info`. Codes are the ones listed in
`business-rules.md` §1–2. Messages state the magnitude, not just the condition.

### `metrics`

```json
{
  "availability": 0.8708, "performance": 0.9091,
  "quality": 0.9763, "oee": 0.7729,
  "utilisation": 0.3333, "teep": 0.2576,
  "planned_production_time_min": 480.0,
  "run_time_min": 418.0,
  "net_run_time_min": 380.0,
  "fully_productive_time_min": 371.0,
  "loss_minutes": {"availability": 62.0, "performance": 38.0,
                   "quality": 9.0, "total": 109.0},
  "cross_check_ok": true
}
```

Ratios are fractions in `[0,1]`, rounded to 4 decimals — never pre-formatted as
percentage strings. `teep` and `utilisation` are `null` unless `all_time_min` is
given. `cross_check_ok` compares `A x P x Q` against `ICT x GC / PPT`; `false`
means the inputs are internally inconsistent and everything downstream is
suspect.

Any metric whose inputs are missing is `null`, and `null` propagates: a `null`
Quality makes OEE `null`. Never substitute 0 for `null` — 0 is a measurement.

### `losses[]`

One entry per bucket with non-zero minutes, sorted descending.

```json
{
  "bucket": "breakdowns",
  "factor": "availability",
  "six_big_loss": 1,
  "loss_minutes": 53.0,
  "share_of_total_loss": 0.4862,
  "event_count": 2,
  "coverage": 1.0,
  "significant": true,
  "notes": ["1 event escalated_from_minor_stop"]
}
```

`factor` says where the minutes sit in the OEE arithmetic; `six_big_loss` says
what kind of loss it is; they differ for minor stops (see
`loss-categories.md`). `coverage` is the share of the bucket's minutes carrying a
specific code — it is what the evidence gate reads.

### `primary_loss`

```json
{"bucket": "breakdowns", "loss_minutes": 53.0, "share_of_total_loss": 0.4862,
 "coverage": 1.0, "tie_with": []}
```

`null` when total loss is zero. A genuine tie lists the other bucket(s) in
`tie_with` and is reported as a tie — never resolved arbitrarily.

### `findings[]` — the semantic payload

```json
{
  "problem": "Availability loss of 53 min from two mechanical failures on L1-PRESS-02",
  "evidence": [
    "DT-0031 MECH_FAIL 35 min at 14:12",
    "DT-0034 MECH_FAIL 18 min at 17:40",
    "alarm A-317 'Hydraulic pressure low' 20 s before DT-0031"
  ],
  "hypothesis": [
    "Hydraulic pressure loss recurring after tool change (correlation with order boundary SO-9912, not established as cause)"
  ],
  "recommended_action": [
    "Record hydraulic pressure at each tool change for 5 shifts",
    "Pull work-order history for the hydraulic pump over 6 months"
  ],
  "confidence": 0.82,
  "corroboration": [
    {
      "type": "alarm",
      "event_id": "DT-0031",
      "record_id": "A-317",
      "temporal_distance_sec": 20.0,
      "machine_match": true,
      "family_match": ["hydraulic"],
      "match_basis": ["same_machine", "compatible_time_window", "compatible_family"]
    }
  ]
}
```

Rules, enforced in review as well as in code:

- `problem` — one sentence, quantified, naming the asset. No causal claim unless
  the evidence gate passed.
- `evidence[]` — **only** verifiable items: event ids, field values, alarm codes,
  work-order numbers. If it cannot be traced to a record, it is not evidence.
  Empty `evidence` forbids any causal language in `problem`.
- `hypothesis[]` — explicitly unproven, each with the correlation it rests on.
- `recommended_action[]` — an action; under `insufficient_evidence`, an
  evidence-gathering action only.
- `confidence` — computed per `business-rules.md` §6, two decimals, never 1.0.
- `corroboration[]` — explicit event-to-record relations. Each entry identifies
  both records and the machine/time/family basis. An unrelated record never
  appears here and never promotes a single event into a causal claim.

### `missing_evidence[]`

Plain strings naming exactly what would resolve the open question:
`"reason codes for stop events DT-0007, DT-0011"`. Generic entries such as
`"more data"` are not acceptable.

### `thresholds`

Echo of the active configuration, so any finding can be reproduced:

```json
{"minor_stop_threshold_min": 5, "attribution_coverage_min": 0.6,
 "significant_bucket_ratio": 0.2, "insufficient_evidence_below": 0.3}
```

## Minimal `insufficient_evidence` response

```json
{
  "status": "insufficient_evidence",
  "reason": "62 of 62 downtime minutes carry no reason code",
  "metrics": { },
  "what_is_still_valid": ["availability", "performance", "quality", "oee"],
  "missing_evidence": ["reason codes on stop events", "maintenance work orders for the period"],
  "findings": [ ]
}
```

## Minimal `data_error` response

```json
{
  "status": "data_error",
  "metrics": null,
  "issues": [
    {"code": "IMPOSSIBLE_CYCLE_TIME", "severity": "error", "field": "ideal_cycle_time_sec",
     "message": "760 units x 30 s = 380 min exceeds run time 310 min; performance would be 123%"}
  ],
  "findings": [],
  "missing_evidence": ["corrected ideal cycle time or corrected total count"]
}
```
