# OEE — definitions, time model, formulas

## The time model

OEE is only meaningful against an explicit time model. Use this one.

```
All Time (calendar)
└── Plant Operating Time                (plant is open)
    ├── Planned Shut Down               (no shift, holidays, planned maintenance,
    │                                    no demand, sanctioned breaks)
    └── Planned Production Time  (PPT)  ← denominator of OEE
        ├── Down Time                   (unplanned stops: breakdowns, setups,
        │                                minor stops, material starvation)
        └── Run Time                    (machine is producing)
            ├── Speed Loss              (running slower than ideal cycle time)
            └── Net Run Time            (theoretical time for all units made)
                ├── Quality Loss        (time spent making rejects)
                └── Fully Productive Time
```

Every minute in Planned Production Time ends up in exactly one of four places:
Down Time, Speed Loss, Quality Loss, Fully Productive Time. That identity is the
audit check of the whole analysis — if the four do not sum to PPT, something is
wrong with the data, not with the formula.

## Formulas

With `PPT` = planned production time, `DT` = downtime, `ICT` = ideal cycle time,
`TC` = total count, `GC` = good count:

```
Run Time        = PPT - DT
Availability    = Run Time / PPT
Performance     = (ICT x TC) / Run Time
Quality         = GC / TC
OEE             = Availability x Performance x Quality
```

The simplified identity, used as a cross-check in `calculate_oee.py`:

```
OEE = (ICT x GC) / PPT
```

Both paths must agree to within floating-point tolerance. A disagreement means
the inputs are internally inconsistent.

### Loss decomposition in minutes

Converting every loss to minutes is what makes losses comparable and rankable.
Percentages are not comparable across the three factors.

```
Availability loss (min) = DT
Performance loss  (min) = Run Time - (ICT x TC)
Quality loss      (min) = ICT x (TC - GC)
Fully productive  (min) = ICT x GC
```

### TEEP and utilisation

```
Utilisation = PPT / All Time
TEEP        = OEE x Utilisation
```

TEEP answers "what share of the calendar did this asset convert into good
product". Report it only when `all_time_min` is supplied; never assume 1440
minutes per day.

### Related metrics

- **OOE** (Overall Operations Effectiveness) uses Plant Operating Time as the
  denominator — it charges unplanned idle capacity to the line.
- **NEE** (Net Equipment Effectiveness) includes setup time in Run Time.
- Do not mix them in one report. State which denominator is in use.

## Benchmarks

| Metric | World class | Typical discrete manufacturing |
|---|---|---|
| Availability | 90 % | 75–85 % |
| Performance | 95 % | 80–90 % |
| Quality | 99.9 % | 97–99.5 % |
| **OEE** | **85 %** | **55–70 %** |

Treat 85 % as a reference point, not a target to impose. A high-mix job shop
with frequent changeovers has a structurally different ceiling than a
single-product line, and the correct comparison is almost always this asset
against itself over time, not against 85 %.

A metric more than 10 percentage points below its world-class value is a
**significant deviation** and triggers step 4 of the workflow.

## Common traps

- **Ideal cycle time inflated to the achievable rate.** Then Performance reads
  ~100 % and the speed loss disappears into thin air. Use the nameplate or the
  best demonstrated sustained cycle, and record which.
- **Planned production time padded with breaks.** Availability rises without
  anything changing on the floor. Breaks belong in Planned Shut Down — unless
  the plant's own standard is to run through them, which must be stated.
- **Rework counted as good.** Quality must be first-pass yield.
- **Micro-stops absent from the downtime log.** They reappear as speed loss and
  get misdiagnosed as a machine capability problem. See
  `six-big-losses.md`, loss 3.
- **OEE compared across different products** on the same machine without
  normalising ideal cycle time per product.
- **Averaging OEE across machines.** OEE does not average meaningfully; aggregate
  the underlying minutes and counts instead, or report the constraint machine.
- **OEE used as an operator performance metric.** It measures the process, not
  the people, and using it that way corrupts the data at the source.
