# The Six Big Losses

The TPM loss taxonomy. Each loss maps to exactly one OEE factor, which is what
makes the classification auditable.

## Availability losses

### 1. Equipment failure / breakdowns
**Key:** `breakdowns` · **Factor:** Availability

Unplanned stops long enough to be logged as a fault: mechanical or electrical
failure, tool breakage, hydraulic or pneumatic loss, control faults, safety
trips.

*Data signature:* few, long events. Duration ≥ the minor-stop threshold
(default 5 min) with a fault reason code. Often paired with an alarm in the
machine event log and a work order in maintenance history.

*Typical countermeasures:* condition monitoring, autonomous maintenance,
criticality-ranked spares, failure-mode analysis on the repeat offender.

### 2. Setup and adjustments
**Key:** `setup_and_adjustments` · **Factor:** Availability

Changeover, tool change, warm-up, first-article approval, parameter tuning,
material changeover.

*Data signature:* events correlated with an order boundary in `orders[]`. The
tell is a stop whose start is within minutes of an order end.

*Typical countermeasures:* SMED — separate internal from external setup, convert
internal to external, streamline what remains. Standardise the first-article
loop, which is usually the hidden half of the changeover.

## Performance losses

### 3. Idling and minor stops
**Key:** `idling_and_minor_stops` · **Factor:** Performance

Short interruptions, conventionally under 5 minutes, typically cleared by the
operator without maintenance: jams, misfeeds, sensor blockages, product
blockage, starvation, cleaning, minor adjustments.

*Data signature:* many, short, repetitive events — or, more often, **nothing at
all in the downtime log** while performance loss is large. Micro-stops are the
single most under-recorded loss in manufacturing, which is why the engine treats
unexplained performance loss as `reduced_speed` only when speed evidence exists,
and as unattributed otherwise.

*Typical countermeasures:* remove the source of contamination or misfeed, poka-
yoke the feed path, count the stops before trying to fix them.

### 4. Reduced speed
**Key:** `reduced_speed` · **Factor:** Performance

The machine runs, but below the ideal cycle time: deliberate derating, worn
tooling, bad material, operator inexperience, conservative recipe parameters.

*Data signature:* actual cycle time consistently above ideal in the speed log,
with no corresponding stop events.

*Beware:* an inflated or stale ideal cycle time manufactures this loss out of
nothing. Verify the ideal cycle time before acting on a reduced-speed finding.

*Typical countermeasures:* find the cause of derating, restore nameplate
conditions, re-qualify the cycle time.

## Quality losses

### 5. Process defects
**Key:** `process_defects` · **Factor:** Quality

Scrap and rework produced during stable running: out-of-tolerance dimensions,
surface defects, assembly faults, contamination.

*Data signature:* rejects spread across the run, defect codes in
`quality_events[]` with `phase: steady_state`.

*Typical countermeasures:* SPC on the driving parameter, process capability
study, error-proofing at the operation that creates the defect.

### 6. Reduced yield / startup rejects
**Key:** `startup_rejects` · **Factor:** Quality

Scrap between start-up and stable production: warm-up parts, first-article
scrap, post-changeover ramp-up, restart after a breakdown.

*Data signature:* rejects clustered at run start or immediately after a stop,
`phase: startup` in `quality_events[]`.

*Typical countermeasures:* faster stabilisation, keep the process warm, tighten
the startup standard, reduce the number of starts (which links this loss back to
losses 1 and 2).

## Two buckets that are not one of the Six

- **`external_or_management_losses`** — material shortage, no operator, upstream
  or downstream blockage, no order. Real availability losses, but not equipment
  losses. Reporting them as breakdowns sends improvement effort to the wrong
  place. Keep them separate and name them as supply-chain or planning issues.
- **`unclassified`** — downtime with no reason code, or performance loss with no
  speed evidence. This bucket is never explained away. If it is large, the
  finding is about the measurement system, and that is a legitimate finding.

## Ranking rule

Rank losses by **minutes**, never by percentage of their own factor. A Quality of
97 % on a fast line can outweigh an Availability of 88 % in absolute lost output.
The engine's `loss_minutes` field is the ranking key.
