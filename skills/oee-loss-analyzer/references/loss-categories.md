# Loss categories — the classification table

Step 3 of the workflow classifies against this table. It is the single source of
truth shared by the skill and `scripts/classify_losses.py`.

## Buckets

| Key | OEE factor | Six Big Loss | Source of loss minutes |
|---|---|---|---|
| `breakdowns` | Availability | 1 | Downtime events, Group A, plus escalated Group C |
| `setup_and_adjustments` | Availability | 2 | Downtime events, Group B |
| `idling_and_minor_stops` | Performance* | 3 | Downtime events, Group C below threshold, **plus** micro-stop minutes from the speed log |
| `reduced_speed` | Performance | 4 | Performance loss minutes not explained by micro-stops, **only when speed evidence exists** |
| `process_defects` | Quality | 5 | `ICT x rejects` with `phase: steady_state` |
| `startup_rejects` | Quality | 6 | `ICT x rejects` with `phase: startup` |
| `external_or_management_losses` | Availability | — | Downtime events, Group D |
| `unclassified_downtime` | Availability | — | Group F events, and the gap between `downtime_min` and the sum of events |
| `unclassified_performance` | Performance | — | Performance loss with no speed evidence |
| `unclassified_quality` | Quality | — | Rejects with `phase: unknown` or no `quality_events[]` |

\* Minor stops recorded as downtime land in Availability arithmetically (they are
stop minutes) but are *diagnosed* as loss 3. The engine reports both: the
`factor` field says where the minutes sit in the OEE arithmetic, the
`six_big_loss` field says what kind of loss it is. Do not conflate them.

## Classification algorithm

```
for each downtime event:
    code   = normalise(event.reason_code, code_map)      # → UNKNOWN if unmapped
    group  = group_of(code)                              # A–F
    bucket = bucket_of(group)
    if group == C and duration_min >= minor_stop_threshold:
        bucket = "breakdowns";  note = "escalated_from_minor_stop"
    if group == E:
        bucket = "planned_inside_ppt";  warn PLANNED_EVENT_INSIDE_PPT
    accumulate duration_min into bucket

gap = downtime_min - sum(event durations)
if gap >  tolerance: accumulate gap into unclassified_downtime
if gap < -tolerance: raise error EVENT_DOWNTIME_MISMATCH

performance_loss = run_time - ideal_cycle_time x total_count
if micro_stops evidence present:
    idling_and_minor_stops += micro_stops.total_min
    remainder → reduced_speed
elif speed_log present:
    remainder → reduced_speed
else:
    performance_loss → unclassified_performance

quality_loss = ideal_cycle_time x reject_count
split by quality_events[].phase; unmatched rejects → unclassified_quality
```

## Ranking and significance

1. Rank all buckets by `loss_minutes`, descending.
2. The **primary loss** is the top bucket. Ties break toward the bucket with more
   supporting events; a true tie is reported as a tie, not resolved arbitrarily.
3. A bucket is **significant** at ≥ 20 % of total loss minutes.
4. `unclassified_*` buckets can be primary. When they are, the finding is about
   the data-collection system, and the recommended action is to instrument the
   loss — not to fix a machine nobody has measured.

## Worked example

```
PPT 480 min · DT 62 min · ICT 30 s · TC 760 · GC 742
Run time      = 418 min
Availability  = 418/480          = 0.8708
Performance   = (30 x 760)/60/418 = 0.9091
Quality       = 742/760          = 0.9763
OEE           = 0.7729

Loss minutes
  availability  62.0
  performance   38.0   (418 - 380)
  quality        9.0   (30 s x 18)
  ---------------------------------
  total        109.0   → PPT 480 = 371 fully productive + 109 lost ✓

Events: MECH_FAIL 35 · MECH_FAIL 18 · SETUP 9   (sum 62, gap 0)
Speed log present, micro-stops 22 min

Buckets
  breakdowns                53.0   48.6 %   ← primary, significant
  performance/minor stops   22.0   20.2 %   ← significant
  reduced_speed             16.0   14.7 %
  setup_and_adjustments      9.0    8.3 %
  process_defects            9.0    8.3 %
```

Evidence coverage of the primary bucket is 100 % (53 of 53 minutes carry a
reason code), so a cause statement about the press is permitted — at the level
the evidence supports, which is "two mechanical failures", not yet "the
hydraulic pump is failing".
