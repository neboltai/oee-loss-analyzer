# Downtime reason-code nomenclature

The canonical code set used by `scripts/classify_losses.py`. Codes are
upper-case, snake-free, stable. Anything not in this table is `UNKNOWN`.

Two attributes decide the bucket: the **code family** and the **duration**
relative to the minor-stop threshold (default 5 min, configurable per site in
`business-rules.md`).

## Group A — Equipment failure → `breakdowns`

| Code | Meaning |
|---|---|
| `MECH_FAIL` | Mechanical failure (bearing, gearbox, drive, guide) |
| `ELEC_FAIL` | Electrical failure (motor, drive, wiring, fuse) |
| `HYD_FAIL` | Hydraulic failure or pressure loss |
| `PNEU_FAIL` | Pneumatic failure or air-pressure loss |
| `CONTROL_FAULT` | PLC / CNC / control system fault |
| `SOFTWARE_FAULT` | HMI, MES client or software crash |
| `TOOL_BREAK` | Tool, die or fixture breakage (unplanned) |
| `SAFETY_TRIP` | Safety circuit, light curtain, E-stop event |

## Group B — Setup and adjustment → `setup_and_adjustments`

| Code | Meaning |
|---|---|
| `SETUP` | Generic setup |
| `CHANGEOVER` | Product changeover |
| `TOOL_CHANGE` | Planned tool or die change (wear-driven) |
| `MAT_CHANGEOVER` | Material or batch change |
| `ADJUST` | Parameter adjustment, centring, alignment |
| `WARMUP` | Warm-up or stabilisation before production |
| `FIRST_ARTICLE` | First-article inspection and approval |

## Group C — Minor stops → `idling_and_minor_stops`

| Code | Meaning |
|---|---|
| `JAM` | Part or material jam |
| `MISFEED` | Feeder misfeed |
| `SENSOR_BLOCK` | Sensor blocked, dirty or misread |
| `PRODUCT_BLOCK` | Product accumulation at the outfeed |
| `CLEAN` | Short in-run cleaning |
| `MINOR_ADJ` | Operator-level minor adjustment |
| `RESET` | Reset or acknowledge after a stop |
| `LUBRICATE` | In-run lubrication |

**Duration rule:** a Group C event lasting ≥ the threshold is reclassified to
`breakdowns` and annotated `escalated_from_minor_stop`. A 45-minute "jam" is a
breakdown that was logged optimistically. Group A events are never demoted, no
matter how short.

## Group D — External / management → `external_or_management_losses`

| Code | Meaning |
|---|---|
| `MAT_SHORT` | Material not available |
| `NO_OPERATOR` | Operator not available |
| `UPSTREAM_BLOCK` | Starved by an upstream process |
| `DOWNSTREAM_BLOCK` | Blocked by a downstream process |
| `NO_ORDER` | No production order to run |
| `POWER_OUT` | Utility / site power failure |
| `QUALITY_HOLD` | Line held for a quality decision |

These are availability losses, but they are not equipment losses. Reporting them
as breakdowns sends the improvement effort to maintenance when it belongs with
planning, logistics or the upstream process.

## Group E — Planned (should sit outside Planned Production Time)

| Code | Meaning |
|---|---|
| `PLANNED_MAINT` | Scheduled maintenance |
| `BREAK` | Sanctioned break |
| `MEETING` | Shift meeting, briefing |
| `TRAINING` | Training on the asset |
| `NO_SHIFT` | Unmanned period |

If a Group E event appears inside the planned production time, the engine raises
warning `PLANNED_EVENT_INSIDE_PPT`. It does not silently remove the time: the
time model is the plant's decision, and moving it changes every historical
comparison. Report it and let the user decide.

## Group F — Unclassified

`UNKNOWN`, `OTHER`, empty string, missing field.

Unclassified downtime is carried to the output as its own bucket. It is never
redistributed across the other buckets, never assumed to be "probably
breakdowns", and never hidden by leaving it out of the Pareto. Above the
`unclassified_downtime_ratio` threshold (default 20 %) the engine raises
`UNCLASSIFIED_DOWNTIME` and every downstream cause statement is capped at
hypothesis level.

## Quality defect codes

Used for the split between loss 5 and loss 6. `phase` decides the bucket, the
defect code characterises it.

| Code | Meaning |
|---|---|
| `DIM_OOT` | Dimension out of tolerance |
| `SURFACE` | Surface defect |
| `BURR` | Burr / flash |
| `CONTAM` | Contamination |
| `ASSY_FAULT` | Assembly fault |
| `MATERIAL_DEF` | Incoming material defect |
| `WELD_FAULT` | Weld or joint defect |
| `COLOR` | Colour or print deviation |
| `STARTUP_SCRAP` | Scrap produced during ramp-up |

`phase` ∈ `startup` | `steady_state` | `unknown`.
`phase: startup` → `startup_rejects`; `steady_state` → `process_defects`;
`unknown` → unclassified quality loss, which blocks a quality root-cause claim.

## Mapping a customer's own code set

Sites arrive with their own nomenclature, often in German or French. Build an
explicit mapping file rather than guessing per event:

```json
{
  "Störung Mechanik": "MECH_FAIL",
  "Rüsten": "SETUP",
  "Werkzeugwechsel": "TOOL_CHANGE",
  "Materialmangel": "MAT_SHORT",
  "Kurzstillstand": "JAM",
  "panne mécanique": "MECH_FAIL",
  "changement de série": "CHANGEOVER",
  "manque matière": "MAT_SHORT"
}
```

Pass it as `code_map` in the dataset or as `--code-map file.json`. Codes that do
not map become `UNKNOWN` — and the count of unmapped events is itself reported,
because a large unmapped share is a finding about the MES configuration.
