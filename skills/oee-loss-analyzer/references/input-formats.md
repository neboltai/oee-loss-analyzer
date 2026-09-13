# Input formats — normalising anything into the dataset

Every intake path ends at the same canonical dataset
(`assets/dataset.schema.json`). Normalise first, analyse second. Never analyse
directly out of a raw export.

The Community Edition ships no production-ready CSV, Excel, PDF or image parser
and no MES, ERP, SQL or API connector. The sections below are review guidance
for creating canonical JSON. Every transformation must remain traceable to its
source and must be reviewed before analysis.

## Canonical dataset

```json
{
  "meta": {
    "machine_id": "L1-PRESS-02",
    "line": "Line 1",
    "shift": "S2",
    "date": "2026-09-08",
    "product": "ART-4471",
    "source": "MES",
    "collected_at": "2026-09-08T22:10:00+02:00"
  },
  "production": {
    "planned_production_time_min": 480,
    "downtime_min": 62,
    "ideal_cycle_time_sec": 30,
    "total_count": 760,
    "good_count": 742,
    "all_time_min": 1440
  },
  "downtime_events": [
    {"id": "DT-0031", "start": "2026-09-08T14:12:00+02:00", "duration_min": 35,
     "reason_code": "MECH_FAIL", "description": "Hydraulik Druckabfall"}
  ],
  "quality_events": [
    {"id": "Q-0007", "defect_code": "BURR", "count": 12, "phase": "steady_state"}
  ],
  "machine_events": [
    {"ts": "2026-09-08T14:11:40+02:00", "type": "alarm", "code": "A-317",
     "text": "Hydraulic pressure low"}
  ],
  "micro_stops": {"count": 34, "total_min": 22.0, "source": "cycle_log"},
  "speed_log": [{"ts": "...", "actual_cycle_time_sec": 33.4}],
  "orders": [{"order_id": "SO-9912", "product": "ART-4471",
              "start": "...", "end": "...", "qty": 760}],
  "maintenance_history": [
    {"wo_id": "WO-2251", "date": "2026-09-05", "type": "corrective",
     "component": "hydraulic pump", "text": "seal replaced"}
  ],
  "code_map": {"Rüsten": "SETUP"},
  "config": {"thresholds": {"minor_stop_threshold_min": 5}}
}
```

`production` must contain planned time, downtime, ideal cycle time, total count,
and exactly one of `good_count` or `reject_count`. `meta.machine_id` is required
for event-to-record corroboration. Everything else is optional evidence.

## CSV

Typical MES export: one row per stop, or one row per shift.

1. Read the header; do not assume column order.
2. Map columns explicitly. Common German/French headers:
   `Schicht`→shift, `Stückzahl`→total_count, `Gutteile`→good_count,
   `Ausschuss`→reject_count, `Stillstand`/`Störzeit`→downtime_min,
   `Taktzeit`→ideal_cycle_time_sec, `Grund`→reason_code;
   `quantité`→total_count, `rebuts`→reject_count, `arrêt`→downtime_min,
   `temps de cycle`→ideal_cycle_time_sec, `motif`→reason_code.
3. Watch the decimal separator (`,` vs `.`) and the thousands separator.
4. Watch the time unit: seconds, minutes and `hh:mm:ss` all appear in the wild.
   Convert explicitly, state the assumption, and if the unit is ambiguous —
   ask, do not guess.
5. Aggregate stop rows into `downtime_events[]`; never sum them into
   `downtime_min` if the export already carries a separate total — compare the
   two instead, that comparison is a data-quality check.

## Excel

Same as CSV plus: multiple sheets (find the data sheet, not the pivot), merged
header cells, hidden rows (they are often the corrections), totals rows that
must be excluded from event lists, and formula cells — read values, not formulas.
Use `pandas.read_excel` with `header=` set explicitly after inspecting the sheet.

## JSON

Usually already close to canonical. Validate against
`assets/dataset.schema.json`, map field names, and check units before trusting
key names that look familiar (`cycle_time` is as often the actual as the ideal).

## PDF shift report

1. Extract text (`pdfplumber`), keep the table structure.
2. Locate the metric block and the stop table separately.
3. Scanned PDF → OCR, and then treat every number as uncertain: flag
   `source: "ocr"` in `meta` and add `LOW_CONFIDENCE_INPUT` to the issue list.
4. Never resolve an OCR-ambiguous digit by picking the value that makes the
   arithmetic work. Ask.

## Image or photo of a production record

1. Transcribe the visible values, per cell, including what is illegible.
2. Return the transcription to the user for confirmation **before** analysing.
   A transcription error propagates into every number downstream.
3. Handwritten totals are often already wrong; check the source's own arithmetic
   and report a discrepancy rather than correcting it.
4. Images rarely carry complete reason codes. Expect
   `insufficient_evidence` for causes, and say so upfront instead of at the end.

## API / SQL / MES / ERP

Production connectivity is outside the Community Edition. Its
`shopfloor-data` MCP server reads fictional local records only and exists to
demonstrate a tool contract.

For a separately assessed production integration, use read-only access,
explicit time-zone handling (shift boundaries crossing midnight are the classic
bug), least privilege and audited mappings. Never let a SQL `JOIN` silently
drop stop events — check row counts before and after.

## Free text ("we lost about two hours yesterday")

Extract what is stated; do not complete it. Two hours of downtime with no
planned time, no counts and no cycle time yields no OEE. Return the missing-field
list and the single most useful question to ask next — not an estimate.

## Multi-shift and multi-machine

Analyse one asset and one period per dataset. To compare, run several datasets
and compare the results — never merge machines into one dataset: the ideal cycle
times differ and the resulting OEE is meaningless.
