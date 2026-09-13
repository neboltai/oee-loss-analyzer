# Evaluation cases

55 JSON files, one case each. Every file is self-contained:

```json
{
  "id": "high-downtime",
  "title": "Severe availability loss from two failures",
  "category": "downtime",
  "note": "optional - what this case is really testing",
  "dataset": { "meta": {}, "production": {}, "downtime_events": [] },
  "expected": {
    "status": "ok",
    "metrics": {"availability": 0.625, "performance": 0.9667, "quality": 0.9828, "oee": 0.5937},
    "primary_loss_bucket": "breakdowns",
    "root_cause_claim_allowed": true,
    "confidence_range": [0.7, 0.95],
    "must_flag": [],
    "tie_with": [],
    "corroboration_pairs": [["alarm", "DT-0031", "A-317"]]
  }
}
```

The `dataset` object is a valid input for every script in `../scripts/`, so any
case can also be run on its own:

```bash
python3 ../scripts/analyse.py high-downtime.json --report
```

Scoring and the measured version-over-version results are in
`../../../EVALUATION.md`. The named cases from the original specification —
`normal-production`, `high-downtime`, `bad-quality`, `microstops`,
`missing-data`, `impossible-cycle-time` — are all present under those exact
names.

The corroboration cases are deliberately adversarial: same-period but unrelated
alarms/work orders, correct family on the wrong machine, and a genuinely linked
maintenance record. This prevents a future change from reverting to
presence-based corroboration.

All cases are fictional and contain no customer or plant data.
