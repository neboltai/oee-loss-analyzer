"""Shared library for the OEE Loss Analyzer.

Holds the reason-code nomenclature, the default thresholds, the dataset loader,
the metric calculation, the loss classification and the evidence gate.

Three rulesets are implemented so the skill can be benchmarked against itself:

    v0.1  naive baseline  - no validation, no reason-code classification,
                            always asserts a cause, never reports uncertainty
    v0.2  validated       - integrity gates + code-family classification, but no
                            duration escalation, no speed/quality evidence split
                            and a permissive evidence gate
    v0.3  evidence gate   - full loss classification with presence-based corroboration
    v0.4  current         - relational corroboration and strict quality-count contract

Only v0.4 is the shipped behaviour; earlier rulesets exist for measurement.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from datetime import date, datetime, time, timezone
from typing import Any

ENGINE_VERSION = "0.4.0"
SCHEMA_VERSION = "1.0"
DEFAULT_RULESET = "v0.4"
RULESETS = ("v0.1", "v0.2", "v0.3", "v0.4")

# --------------------------------------------------------------------------
# Reason-code nomenclature (see references/downtime-classification.md)
# --------------------------------------------------------------------------

GROUP_A_BREAKDOWN = {
    "MECH_FAIL", "ELEC_FAIL", "HYD_FAIL", "PNEU_FAIL",
    "CONTROL_FAULT", "SOFTWARE_FAULT", "TOOL_BREAK", "SAFETY_TRIP",
}
GROUP_B_SETUP = {
    "SETUP", "CHANGEOVER", "TOOL_CHANGE", "MAT_CHANGEOVER",
    "ADJUST", "WARMUP", "FIRST_ARTICLE",
}
GROUP_C_MINOR = {
    "JAM", "MISFEED", "SENSOR_BLOCK", "PRODUCT_BLOCK",
    "CLEAN", "MINOR_ADJ", "RESET", "LUBRICATE",
}
GROUP_D_EXTERNAL = {
    "MAT_SHORT", "NO_OPERATOR", "UPSTREAM_BLOCK", "DOWNSTREAM_BLOCK",
    "NO_ORDER", "POWER_OUT", "QUALITY_HOLD",
}
GROUP_E_PLANNED = {
    "PLANNED_MAINT", "BREAK", "MEETING", "TRAINING", "NO_SHIFT",
}
UNKNOWN_CODES = {"", "UNKNOWN", "OTHER", "N/A", "NA", "-", None}

BUCKET_OF_GROUP = {
    "A": "breakdowns",
    "B": "setup_and_adjustments",
    "C": "idling_and_minor_stops",
    "D": "external_or_management_losses",
    "E": "planned_inside_ppt",
    "F": "unclassified_downtime",
}

SIX_BIG_LOSS = {
    "breakdowns": 1,
    "setup_and_adjustments": 2,
    "idling_and_minor_stops": 3,
    "reduced_speed": 4,
    "process_defects": 5,
    "startup_rejects": 6,
}

FACTOR_OF_BUCKET = {
    "breakdowns": "availability",
    "setup_and_adjustments": "availability",
    "idling_and_minor_stops": "availability",  # overridden for micro-stop minutes
    "external_or_management_losses": "availability",
    "planned_inside_ppt": "availability",
    "unclassified_downtime": "availability",
    "reduced_speed": "performance",
    "unclassified_performance": "performance",
    "process_defects": "quality",
    "startup_rejects": "quality",
    "unclassified_quality": "quality",
}

DEFAULT_THRESHOLDS = {
    "minor_stop_threshold_min": 5.0,
    "event_sum_tolerance_min": 1.0,
    "cycle_time_tolerance_min": 1.0,
    "unclassified_downtime_ratio": 0.20,
    "significant_bucket_ratio": 0.20,
    "attribution_coverage_min": 0.60,
    "insufficient_evidence_below": 0.30,
    "low_sample_units": 100,
    "alarm_correlation_window_sec": 300.0,
    "maintenance_correlation_window_days": 7.0,
    "order_boundary_window_sec": 900.0,
}

REQUIRED_FIELDS = [
    "planned_production_time_min",
    "downtime_min",
    "ideal_cycle_time_sec",
    "total_count",
    "good_count",
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def issue(code: str, severity: str, field: str, message: str) -> dict:
    return {"code": code, "severity": severity, "field": field, "message": message}


def group_of(code: str | None) -> str:
    c = (code or "").strip().upper()
    if c in GROUP_A_BREAKDOWN:
        return "A"
    if c in GROUP_B_SETUP:
        return "B"
    if c in GROUP_C_MINOR:
        return "C"
    if c in GROUP_D_EXTERNAL:
        return "D"
    if c in GROUP_E_PLANNED:
        return "E"
    return "F"


def normalise_code(raw: Any, code_map: dict | None) -> str:
    if raw is None:
        return "UNKNOWN"
    s = str(raw).strip()
    if code_map:
        if s in code_map:
            s = str(code_map[s])
        elif s.lower() in {k.lower(): v for k, v in code_map.items()}:
            s = str({k.lower(): v for k, v in code_map.items()}[s.lower()])
    up = s.upper()
    if up in UNKNOWN_CODES or not up:
        return "UNKNOWN"
    if group_of(up) == "F":
        return "UNKNOWN"
    return up


def r4(x):
    return None if x is None else round(float(x) + 0.0, 4)


def load_dataset(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # test-case files wrap the dataset under "dataset"
    if "dataset" in data and "production" in data.get("dataset", {}):
        return data["dataset"]
    return data


def thresholds_for(ds: dict, overrides: dict | None = None) -> dict:
    th = dict(DEFAULT_THRESHOLDS)
    th.update((ds.get("config") or {}).get("thresholds") or {})
    th.update(overrides or {})
    return th


def _num(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalised_text(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


FAMILY_TERMS = {
    "hydraulic": ("hydraulic", "hydraulik", "hydraulique", "oil pressure", "oldruck", "pression huile"),
    "pneumatic": ("pneumatic", "pneumatik", "pneumatique", "air pressure", "luftdruck"),
    "electrical": ("electrical", "electric", "elektrik", "elektrisch", "electrique", "voltage", "spannung"),
    "control": ("control", "steuerung", "automate", "plc", "software", "programme", "program"),
    "tooling": ("tool", "werkzeug", "outil", "die", "mold", "mould", "matrice"),
    "feed": ("feed", "feeder", "zufuhr", "alimentation", "misfeed", "jam", "verklemmt", "bourrage"),
    "sensor": ("sensor", "capteur", "lichtschranke"),
    "drive": ("motor", "drive", "antrieb", "moteur", "gearbox", "getriebe", "reducteur"),
    "bearing": ("bearing", "lager", "roulement", "spindle", "spindel", "broche"),
}

REASON_FAMILIES = {
    "HYD_FAIL": {"hydraulic"},
    "PNEU_FAIL": {"pneumatic"},
    "ELEC_FAIL": {"electrical"},
    "CONTROL_FAULT": {"control"},
    "SOFTWARE_FAULT": {"control"},
    "TOOL_BREAK": {"tooling"},
    "TOOL_CHANGE": {"tooling"},
    "JAM": {"feed"},
    "MISFEED": {"feed"},
    "SENSOR_BLOCK": {"sensor"},
}


def _families(record: dict, code_map: dict | None = None) -> set[str]:
    explicit = record.get("family")
    out = {str(explicit).strip().lower()} if explicit else set()
    code = normalise_code(record.get("reason_code") or record.get("code"), code_map)
    out.update(REASON_FAMILIES.get(code, set()))
    text = _normalised_text(" ".join(str(record.get(k, "")) for k in
                                      ("component", "description", "text")))
    for family, terms in FAMILY_TERMS.items():
        if any(_normalised_text(term) in text for term in terms):
            out.add(family)
    return out


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(raw), time.min)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_time(record: dict) -> datetime | None:
    for key in ("ts", "timestamp", "start", "date", "created_at", "completed_at"):
        parsed = _parse_time(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _machine_matches(ds: dict, event: dict, record: dict) -> bool:
    dataset_machine = str((ds.get("meta") or {}).get("machine_id") or "").strip()
    event_machine = str(event.get("machine_id") or dataset_machine).strip()
    record_machine = str(record.get("machine_id") or dataset_machine).strip()
    known = [m for m in (dataset_machine, event_machine, record_machine) if m]
    return bool(known) and len(set(known)) == 1


def _record_id(record: dict, fallback: str) -> str:
    for key in ("id", "code", "wo_id", "order_id"):
        if record.get(key) not in (None, ""):
            return str(record[key])
    return fallback


def _primary_downtime_events(ds: dict, primary_bucket: str, th: dict) -> list[dict]:
    code_map = ds.get("code_map")
    selected = []
    for event in ds.get("downtime_events") or []:
        code = normalise_code(event.get("reason_code"), code_map)
        group = group_of(code)
        bucket = BUCKET_OF_GROUP[group]
        duration = _num(event.get("duration_min")) or 0.0
        if group == "C" and duration >= th["minor_stop_threshold_min"]:
            bucket = "breakdowns"
        if bucket == primary_bucket:
            selected.append(event)
    return selected


def corroboration_matches(ds: dict, primary: dict | None, th: dict) -> list[dict]:
    """Return only records relationally tied to an event in the primary bucket.

    Mere presence in the dataset is never corroboration. A match requires the
    same asset, a compatible time window and a compatible technical family.
    Order boundaries use the same machine/time checks and are limited to setup
    or startup buckets, where the production-order transition is the mechanism.
    """
    if not primary:
        return []
    bucket = primary["bucket"]
    targets = _primary_downtime_events(ds, bucket, th)
    if not targets:
        return []
    code_map = ds.get("code_map")
    matches: list[dict] = []

    def append_match(kind: str, event: dict, record: dict, distance: float,
                     common: set[str], basis: list[str]) -> None:
        event_id = _record_id(event, "DT-?")
        record_id = _record_id(record, f"{kind}-?")
        key = (kind, event_id, record_id)
        if any((m["type"], m["event_id"], m["record_id"]) == key for m in matches):
            return
        matches.append({
            "type": kind,
            "event_id": event_id,
            "record_id": record_id,
            "temporal_distance_sec": round(distance, 1),
            "machine_match": True,
            "family_match": sorted(common),
            "match_basis": basis,
        })

    alarms = [r for r in (ds.get("machine_events") or [])
              if str(r.get("type", "")).lower() == "alarm"]
    for event in targets:
        event_time = _record_time(event)
        event_families = _families(event, code_map)
        if event_time is None or not event_families:
            continue
        for alarm in alarms:
            alarm_time = _record_time(alarm)
            common = event_families & _families(alarm, code_map)
            if alarm_time is None or not common or not _machine_matches(ds, event, alarm):
                continue
            distance = abs((alarm_time - event_time).total_seconds())
            if distance <= th["alarm_correlation_window_sec"]:
                append_match("alarm", event, alarm, distance, common,
                             ["same_machine", "compatible_time_window", "compatible_family"])

    for event in targets:
        event_time = _record_time(event)
        event_families = _families(event, code_map)
        if event_time is None or not event_families:
            continue
        for work_order in ds.get("maintenance_history") or []:
            work_time = _record_time(work_order)
            common = event_families & _families(work_order, code_map)
            if work_time is None or not common or not _machine_matches(ds, event, work_order):
                continue
            distance = abs((work_time - event_time).total_seconds())
            if distance <= th["maintenance_correlation_window_days"] * 86400:
                append_match("maintenance", event, work_order, distance, common,
                             ["same_machine", "compatible_time_window", "compatible_component_family"])

    if bucket in {"setup_and_adjustments", "startup_rejects"}:
        for event in targets:
            event_time = _record_time(event)
            if event_time is None:
                continue
            for order in ds.get("orders") or []:
                if not _machine_matches(ds, event, order):
                    continue
                boundaries = [_parse_time(order.get("start")), _parse_time(order.get("end"))]
                distances = [abs((b - event_time).total_seconds()) for b in boundaries if b]
                if distances and min(distances) <= th["order_boundary_window_sec"]:
                    append_match("order_boundary", event, order, min(distances),
                                 {"production_order_transition"},
                                 ["same_machine", "compatible_time_window", "compatible_loss_mechanism"])
    return matches


def production_values(ds: dict) -> dict:
    """Extract the five required values without inventing anything."""
    p = dict(ds.get("production") or {})
    out = {k: _num(p.get(k)) for k in REQUIRED_FIELDS}
    if out["good_count"] is None:
        rej = _num(p.get("reject_count"))
        if rej is not None and out["total_count"] is not None:
            out["good_count"] = out["total_count"] - rej
            out["_good_derived"] = True
    out["reject_count"] = (
        None
        if out["good_count"] is None or out["total_count"] is None
        else out["total_count"] - out["good_count"]
    )
    out["all_time_min"] = _num(p.get("all_time_min"))
    return out


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate(ds: dict, ruleset: str = DEFAULT_RULESET, th: dict | None = None) -> list[dict]:
    """Return the issue list. v0.1 performs no validation at all."""
    th = th or thresholds_for(ds)
    issues: list[dict] = []
    pv = production_values(ds)

    if ruleset == "v0.1":
        return issues

    # --- integrity gates (severity error) --------------------------------
    production = ds.get("production") or {}
    if (ruleset == "v0.4" and production.get("good_count") is not None
            and production.get("reject_count") is not None):
        issues.append(issue(
            "QUALITY_COUNT_ALTERNATIVES", "error", "production",
            "supply exactly one of good_count or reject_count; both were provided",
        ))
    for f in REQUIRED_FIELDS:
        if pv.get(f) is None:
            if f == "good_count":
                message = "exactly one of 'good_count' or 'reject_count' is required"
            else:
                message = f"required field '{f}' is missing; the metric it feeds is undefined"
            issues.append(issue("MISSING_FIELD", "error", f,
                                message))
    if any(i["severity"] == "error" for i in issues):
        return issues

    ppt = pv["planned_production_time_min"]
    dt = pv["downtime_min"]
    ict = pv["ideal_cycle_time_sec"]
    tc = pv["total_count"]
    gc = pv["good_count"]

    for name, val in (("planned_production_time_min", ppt), ("downtime_min", dt),
                      ("ideal_cycle_time_sec", ict), ("total_count", tc), ("good_count", gc)):
        if val < 0:
            issues.append(issue("NEGATIVE_VALUE", "error", name,
                                f"{name} = {val} is negative and physically impossible"))
    if ppt <= 0:
        issues.append(issue("ZERO_PLANNED_TIME", "error", "planned_production_time_min",
                            "planned production time is zero; OEE is undefined"))
    if ict <= 0:
        issues.append(issue("ZERO_CYCLE_TIME", "error", "ideal_cycle_time_sec",
                            "ideal cycle time is zero; performance is undefined"))
    if dt > ppt:
        issues.append(issue("DOWNTIME_EXCEEDS_PLANNED", "error", "downtime_min",
                            f"downtime {dt} min exceeds planned production time {ppt} min; run time would be negative"))
    if gc > tc:
        issues.append(issue("GOOD_EXCEEDS_TOTAL", "error", "good_count",
                            f"good count {gc:g} exceeds total count {tc:g}; quality would be above 100%"))
    if any(i["severity"] == "error" for i in issues):
        return issues

    run_time = ppt - dt
    net_run = ict * tc / 60.0
    if tc == 0 and run_time > 0:
        issues.append(issue("ZERO_TOTAL_COUNT_WITH_RUNTIME", "error", "total_count",
                            f"total count is 0 while run time is {run_time:g} min; either nothing ran or counting failed"))
    if net_run > run_time + th["cycle_time_tolerance_min"]:
        perf = net_run / run_time if run_time > 0 else float("inf")
        issues.append(issue("IMPOSSIBLE_CYCLE_TIME", "error", "ideal_cycle_time_sec",
                            f"{tc:g} units x {ict:g} s = {net_run:.1f} min exceeds run time {run_time:.1f} min; "
                            f"performance would be {perf * 100:.0f}%"))

    events = ds.get("downtime_events") or []
    sum_ev = sum(_num(e.get("duration_min")) or 0.0 for e in events)
    if events and sum_ev > dt + th["event_sum_tolerance_min"]:
        issues.append(issue("EVENT_DOWNTIME_MISMATCH", "error", "downtime_events",
                            f"stop events sum to {sum_ev:.1f} min but reported downtime is {dt:.1f} min"))

    if any(i["severity"] == "error" for i in issues):
        return issues

    # --- data quality flags (severity warning) ---------------------------
    if dt > 0 and not events:
        issues.append(issue("NO_DOWNTIME_EVENTS", "warning", "downtime_events",
                            f"{dt:.0f} min of downtime with no stop event log; availability causes cannot be attributed"))
    if events and sum_ev < dt - th["event_sum_tolerance_min"]:
        issues.append(issue("EVENT_DOWNTIME_GAP", "warning", "downtime_events",
                            f"stop events cover {sum_ev:.1f} of {dt:.1f} downtime minutes; "
                            f"the {dt - sum_ev:.1f} min gap is carried as unclassified"))
    code_map = ds.get("code_map")
    unknown_min = sum((_num(e.get("duration_min")) or 0.0) for e in events
                      if normalise_code(e.get("reason_code"), code_map) == "UNKNOWN")
    unknown_min += max(0.0, dt - sum_ev)
    if dt > 0 and unknown_min / dt > th["unclassified_downtime_ratio"]:
        issues.append(issue("UNCLASSIFIED_DOWNTIME", "warning", "downtime_events",
                            f"{unknown_min:.0f} of {dt:.0f} downtime minutes carry no reason code "
                            f"({unknown_min / dt * 100:.0f}%); cause statements are capped at hypothesis level"))
    if events:
        unmapped = sum(1 for e in events
                       if normalise_code(e.get("reason_code"), code_map) == "UNKNOWN")
        if unmapped / len(events) > 0.10:
            issues.append(issue("UNMAPPED_REASON_CODES", "warning", "downtime_events",
                                f"{unmapped} of {len(events)} stop events carry an unmapped reason code"))
    for e in events:
        if group_of(normalise_code(e.get("reason_code"), code_map)) == "E":
            issues.append(issue("PLANNED_EVENT_INSIDE_PPT", "warning", "downtime_events",
                                f"event {e.get('id', '?')} uses planned code "
                                f"{normalise_code(e.get('reason_code'), code_map)} inside planned production time; "
                                "the time model should be reviewed, no time was removed"))
            break

    rejects = tc - gc
    if rejects > 0 and not (ds.get("quality_events") or []):
        issues.append(issue("NO_QUALITY_EVENTS", "warning", "quality_events",
                            f"{rejects:g} rejects with no defect log; quality causes cannot be attributed"))
    perf_loss = run_time - net_run
    if perf_loss > 1.0 and not ds.get("micro_stops") and not ds.get("speed_log"):
        issues.append(issue("NO_SPEED_EVIDENCE", "warning", "speed_log",
                            f"{perf_loss:.0f} min of performance loss with no cycle-time or micro-stop evidence; "
                            "minor stops cannot be separated from reduced speed"))
    if tc < th["low_sample_units"]:
        issues.append(issue("LOW_SAMPLE", "warning", "total_count",
                            f"only {tc:g} units produced; conclusions are provisional"))
    if run_time > 0:
        perf = net_run / run_time
        if perf > 0.98 or perf < 0.40:
            issues.append(issue("ICT_SUSPICIOUS", "warning", "ideal_cycle_time_sec",
                                f"performance computes to {perf * 100:.0f}%; the ideal cycle time is likely wrong"))
    return issues


def has_errors(issues: list[dict]) -> bool:
    return any(i["severity"] == "error" for i in issues)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def calculate(ds: dict, ruleset: str = DEFAULT_RULESET) -> dict | None:
    pv = production_values(ds)
    ppt, dt = pv["planned_production_time_min"], pv["downtime_min"]
    ict, tc, gc = pv["ideal_cycle_time_sec"], pv["total_count"], pv["good_count"]
    if None in (ppt, dt, ict, tc, gc) or ppt in (0, None):
        return None

    run_time = ppt - dt
    net_run = ict * tc / 60.0
    fully_productive = ict * gc / 60.0

    availability = run_time / ppt if ppt else None
    performance = (net_run / run_time) if run_time > 0 else None
    quality = (gc / tc) if tc > 0 else None
    oee = None
    if None not in (availability, performance, quality):
        oee = availability * performance * quality

    cross = None
    if oee is not None:
        cross = abs(oee - (fully_productive / ppt)) < 1e-6

    all_time = pv.get("all_time_min")
    utilisation = (ppt / all_time) if all_time else None
    teep = (oee * utilisation) if (oee is not None and utilisation is not None) else None

    return {
        "availability": r4(availability),
        "performance": r4(performance),
        "quality": r4(quality),
        "oee": r4(oee),
        "utilisation": r4(utilisation),
        "teep": r4(teep),
        "planned_production_time_min": round(ppt, 2),
        "run_time_min": round(run_time, 2),
        "net_run_time_min": round(net_run, 2),
        "fully_productive_time_min": round(fully_productive, 2),
        "loss_minutes": {
            "availability": round(dt, 2),
            "performance": round(run_time - net_run, 2),
            "quality": round(ict * (tc - gc) / 60.0, 2),
            "total": round(dt + (run_time - net_run) + ict * (tc - gc) / 60.0, 2),
        },
        "cross_check_ok": cross,
    }


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def classify(ds: dict, metrics: dict, ruleset: str = DEFAULT_RULESET,
             th: dict | None = None) -> dict:
    th = th or thresholds_for(ds)
    code_map = ds.get("code_map")
    events = ds.get("downtime_events") or []
    dt = metrics["loss_minutes"]["availability"]
    perf_loss = max(0.0, metrics["loss_minutes"]["performance"])
    qual_loss = max(0.0, metrics["loss_minutes"]["quality"])

    buckets: dict[str, dict] = {}

    def add(bucket, minutes, factor, n_events=0, note=None, evidence=None, code=None):
        if minutes <= 0 and n_events == 0:
            return
        b = buckets.setdefault(bucket, {
            "bucket": bucket, "loss_minutes": 0.0, "event_count": 0,
            "minutes_by_factor": {}, "notes": [], "evidence": [], "reason_codes": {},
        })
        if code:
            b["reason_codes"][code] = b["reason_codes"].get(code, 0) + 1
        b["loss_minutes"] += minutes
        b["event_count"] += n_events
        b["minutes_by_factor"][factor] = b["minutes_by_factor"].get(factor, 0.0) + max(0.0, minutes)
        if note and note not in b["notes"]:
            b["notes"].append(note)
        if evidence:
            b["evidence"].extend(evidence)

    # ---- availability ---------------------------------------------------
    if ruleset == "v0.1":
        add("breakdowns", dt, "availability", len(events),
            evidence=[_ev_str(e, code_map) for e in events])
    else:
        sum_ev = 0.0
        for e in events:
            dur = _num(e.get("duration_min")) or 0.0
            sum_ev += dur
            code = normalise_code(e.get("reason_code"), code_map)
            grp = group_of(code)
            bucket = BUCKET_OF_GROUP[grp]
            note = None
            if ruleset in {"v0.3", "v0.4"} and grp == "C" and dur >= th["minor_stop_threshold_min"]:
                bucket = "breakdowns"
                note = "escalated_from_minor_stop"
            add(bucket, dur, "availability", 1, note, [_ev_str(e, code_map)], code=code)
        gap = dt - sum_ev
        if gap > th["event_sum_tolerance_min"]:
            add("unclassified_downtime", gap, "availability", 0,
                note="downtime not covered by any stop event")
        elif not events and dt > 0:
            add("unclassified_downtime", dt, "availability", 0, note="no stop event log")

    # ---- performance ----------------------------------------------------
    micro = ds.get("micro_stops") or {}
    micro_min = _num(micro.get("total_min")) or 0.0
    micro_count = int(_num(micro.get("count")) or 0)
    speed_log = ds.get("speed_log") or []
    if ruleset in {"v0.3", "v0.4"}:
        if micro_min > 0:
            m = min(micro_min, perf_loss)
            add("idling_and_minor_stops", m, "performance", micro_count,
                note="micro-stops from cycle log (performance-side)",
                evidence=[f"micro_stops: {micro_count} stops, {m:.1f} min ({micro.get('source', 'cycle_log')})"])
            rest = perf_loss - m
            if rest > 0.01:
                if speed_log:
                    add("reduced_speed", rest, "performance", len(speed_log),
                        evidence=[f"speed_log: {len(speed_log)} samples, "
                                  f"mean actual cycle {_mean_cycle(speed_log):.1f} s"])
                else:
                    add("unclassified_performance", rest, "performance", 0,
                        note="no cycle-time evidence for the remaining performance loss")
        elif speed_log:
            add("reduced_speed", perf_loss, "performance", len(speed_log),
                evidence=[f"speed_log: {len(speed_log)} samples, "
                          f"mean actual cycle {_mean_cycle(speed_log):.1f} s"])
        elif perf_loss > 0:
            add("unclassified_performance", perf_loss, "performance", 0,
                note="no cycle-time or micro-stop evidence")
    else:  # v0.1 / v0.2 push everything to reduced speed
        add("reduced_speed", perf_loss, "performance", len(speed_log))

    # ---- quality --------------------------------------------------------
    qevents = ds.get("quality_events") or []
    pv = production_values(ds)
    ict = pv["ideal_cycle_time_sec"]
    rejects = pv["reject_count"] or 0
    if ruleset in {"v0.3", "v0.4"} and qevents:
        matched = 0
        for q in qevents:
            n = _num(q.get("count")) or 0.0
            phase = str(q.get("phase", "unknown")).lower()
            minutes = ict * n / 60.0
            ev = [f"{q.get('id', 'Q-?')} {q.get('defect_code', 'UNKNOWN')} x{n:g} ({phase})"]
            dcode = str(q.get("defect_code", "UNKNOWN")).upper()
            if phase == "startup":
                add("startup_rejects", minutes, "quality", 1, evidence=ev, code=dcode)
            elif phase == "steady_state":
                add("process_defects", minutes, "quality", 1, evidence=ev, code=dcode)
            else:
                add("unclassified_quality", minutes, "quality", 0,
                    note="reject phase unknown", evidence=ev)
            matched += n
        rest = rejects - matched
        if rest > 0.001:
            add("unclassified_quality", ict * rest / 60.0, "quality", 0,
                note=f"{rest:g} rejects not covered by any defect record")
    elif ruleset in {"v0.3", "v0.4"}:
        if qual_loss > 0:
            add("unclassified_quality", qual_loss, "quality", 0, note="no defect log")
    else:
        add("process_defects", qual_loss, "quality", len(qevents))

    # ---- coverage and shares -------------------------------------------
    total_loss = sum(b["loss_minutes"] for b in buckets.values())
    out = []
    for b in buckets.values():
        bucket = b["bucket"]
        classified = not bucket.startswith("unclassified")
        mbf = {k: round(v, 2) for k, v in b["minutes_by_factor"].items() if v > 0}
        if len(mbf) > 1:
            factor = "mixed"
        elif mbf:
            factor = next(iter(mbf))
        else:
            factor = FACTOR_OF_BUCKET.get(bucket, "availability")
        out.append({
            "bucket": bucket,
            "factor": factor,
            "minutes_by_factor": mbf,
            "six_big_loss": SIX_BIG_LOSS.get(bucket),
            "loss_minutes": round(b["loss_minutes"], 2),
            "share_of_total_loss": r4(b["loss_minutes"] / total_loss) if total_loss else 0.0,
            "event_count": b["event_count"],
            "coverage": 1.0 if classified else 0.0,
            "significant": bool(total_loss and b["loss_minutes"] / total_loss >= th["significant_bucket_ratio"]),
            "reason_codes": b.get("reason_codes", {}),
            "notes": b["notes"],
            "evidence": b["evidence"],
        })
    out.sort(key=lambda x: (-x["loss_minutes"], x["bucket"]))

    primary = None
    if out and total_loss > 0:
        top = out[0]
        ties = [o["bucket"] for o in out[1:] if abs(o["loss_minutes"] - top["loss_minutes"]) < 0.01]
        dominant = top["factor"]
        if dominant == "mixed" and top["minutes_by_factor"]:
            dominant = max(top["minutes_by_factor"].items(), key=lambda kv: kv[1])[0]
        primary = {
            "bucket": top["bucket"],
            "factor": dominant,
            "loss_minutes": top["loss_minutes"],
            "share_of_total_loss": top["share_of_total_loss"],
            "coverage": top["coverage"],
            "event_count": top["event_count"],
            "tie_with": ties,
        }

    return {"losses": out, "primary_loss": primary, "total_loss_minutes": round(total_loss, 2)}


def _ev_str(e: dict, code_map) -> str:
    code = normalise_code(e.get("reason_code"), code_map)
    dur = _num(e.get("duration_min")) or 0.0
    start = e.get("start", "")
    tail = f" at {start}" if start else ""
    return f"{e.get('id', 'DT-?')} {code} {dur:g} min{tail}"


def _mean_cycle(speed_log) -> float:
    vals = [_num(s.get("actual_cycle_time_sec")) for s in speed_log]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else float("nan")


# --------------------------------------------------------------------------
# Evidence gate, confidence, findings
# --------------------------------------------------------------------------

HYPOTHESIS_CATALOGUE = {
    "breakdowns": [
        "A recurring failure mode on the same component (the stop events share a reason code)",
        "Basic conditions not restored - cleaning, lubrication or fastening",
    ],
    "setup_and_adjustments": [
        "Changeover is largely internal setup that SMED could move to external time",
        "First-article approval loop is extending each changeover",
    ],
    "idling_and_minor_stops": [
        "A feed or transport path producing repetitive jams",
        "Sensor sensitivity or contamination causing false stops",
    ],
    "reduced_speed": [
        "Deliberate derating to contain a quality or noise problem",
        "Ideal cycle time no longer matches the qualified condition of the asset",
    ],
    "process_defects": [
        "A process parameter drifting out of its capable window",
        "Incoming material variation",
    ],
    "startup_rejects": [
        "Ramp-up standard not stabilising the process before release",
        "Too many starts - each stop pays the startup scrap again",
    ],
    "external_or_management_losses": [
        "Upstream supply or planning constraint rather than an equipment problem",
    ],
    "unclassified_downtime": [
        "Stop reasons are not being captured at the machine",
    ],
    "unclassified_performance": [
        "Unrecorded micro-stops rather than genuine slow running",
    ],
    "unclassified_quality": [
        "Defects are not being coded at the point of rejection",
    ],
    "planned_inside_ppt": [
        "The time model counts planned activities inside planned production time",
    ],
}

ACTION_CATALOGUE = {
    "breakdowns": [
        "Pull 6 months of work orders for the affected component and rank failure modes",
        "Confirm basic conditions at the machine (clean, lubricate, fasten) before any capital action",
    ],
    "setup_and_adjustments": [
        "Video one full changeover and split internal from external setup (SMED step 1)",
    ],
    "idling_and_minor_stops": [
        "Count and locate minor stops for two shifts before changing anything",
    ],
    "reduced_speed": [
        "Re-qualify the ideal cycle time against the nameplate and the best demonstrated cycle",
    ],
    "process_defects": [
        "Stratify the defect data by product, tool and shift, then run a capability study on the driving parameter",
    ],
    "startup_rejects": [
        "Measure scrap per start and time-to-stable for 10 starts",
    ],
    "external_or_management_losses": [
        "Route the loss to planning or the upstream process owner, not to maintenance",
    ],
    "unclassified_downtime": [
        "Make reason-code entry mandatory at the machine for stops above the minor-stop threshold",
    ],
    "unclassified_performance": [
        "Enable cycle-time logging so micro-stops can be separated from reduced speed",
    ],
    "unclassified_quality": [
        "Introduce defect coding at the point of rejection",
    ],
    "planned_inside_ppt": [
        "Review the time model with the plant: decide whether planned activities sit inside or outside planned production time",
    ],
}

MISSING_EVIDENCE_FOR = {
    "unclassified_downtime": ["reason codes on the uncoded stop events"],
    "unclassified_performance": ["cycle-time log or micro-stop count for the period"],
    "unclassified_quality": ["defect codes and phase (startup / steady state) for the rejects"],
}


def evidence_assessment(ds: dict, cls: dict, issues: list[dict],
                        ruleset: str = DEFAULT_RULESET, th: dict | None = None) -> dict:
    th = th or thresholds_for(ds)
    primary = cls["primary_loss"]
    losses = cls["losses"]

    if primary is None:
        return {"status": "ok", "attribution": 1.0, "root_cause_claimed": False,
                "corroborated": False, "corroboration_matches": [], "reason": None}

    factor = primary["factor"]
    factor_total = sum(l.get("minutes_by_factor", {}).get(factor, 0.0) for l in losses)
    factor_classified = sum(l.get("minutes_by_factor", {}).get(factor, 0.0)
                            for l in losses if l["coverage"] >= 1.0)
    attribution = (factor_classified / factor_total) if factor_total > 0 else 0.0

    # v0.1-v0.3 are retained as historical benchmark rulesets. v0.4 is the
    # shipped behaviour: mere presence of an alarm/work order is not evidence.
    if ruleset == "v0.4":
        relation_matches = corroboration_matches(ds, primary, th)
        corroborated = bool(relation_matches)
    else:
        relation_matches = []
        corroborated = bool(ds.get("maintenance_history")) or bool(
            [e for e in (ds.get("machine_events") or [])
             if str(e.get("type", "")).lower() == "alarm"])

    if ruleset == "v0.1":
        return {"status": "ok", "attribution": attribution, "root_cause_claimed": True,
                "corroborated": corroborated, "corroboration_matches": relation_matches,
                "reason": None}

    if ruleset == "v0.2":
        claimed = primary["event_count"] >= 1
        return {"status": "ok", "attribution": attribution, "root_cause_claimed": claimed,
                "corroborated": corroborated, "corroboration_matches": relation_matches,
                "reason": None}

    # v0.3 / v0.4
    unclassified_primary = primary["bucket"].startswith("unclassified")
    status = "ok"
    reason = None
    if unclassified_primary:
        status = "insufficient_evidence"
        reason = (f"the largest loss ({primary['loss_minutes']:.0f} min, "
                  f"{primary['share_of_total_loss'] * 100:.0f}% of total loss) carries no "
                  f"reason, defect or cycle-time evidence")
    elif attribution < th["insufficient_evidence_below"]:
        status = "insufficient_evidence"
        reason = (f"only {attribution * 100:.0f}% of the {factor} loss is attributable to a "
                  f"coded event; below the {th['insufficient_evidence_below'] * 100:.0f}% floor")

    codes = {i["code"] for i in issues}
    capped = "UNCLASSIFIED_DOWNTIME" in codes
    # a cause on a performance loss is not claimable when the cycle-time basis
    # is itself in doubt - the loss may be an artefact of the ideal cycle time
    if "ICT_SUSPICIOUS" in codes and factor == "performance":
        capped = True
    claimed = (
        status == "ok"
        and attribution >= th["attribution_coverage_min"]
        and (primary["event_count"] >= 2 or corroborated)
        and not capped
    )
    return {"status": status, "attribution": attribution, "root_cause_claimed": claimed,
            "corroborated": corroborated, "corroboration_matches": relation_matches,
            "reason": reason}


def confidence_score(attribution: float, ds: dict, issues: list[dict]) -> float:
    channels = [
        bool(ds.get("downtime_events")),
        bool(ds.get("quality_events")),
        bool(ds.get("micro_stops") or ds.get("speed_log")),
        bool(ds.get("maintenance_history")),
    ]
    channel_ratio = sum(1 for c in channels if c) / 4.0
    n_warn = sum(1 for i in issues if i["severity"] == "warning")
    penalty = min(1.0, 0.15 * n_warn)
    c = 0.30 + 0.40 * attribution + 0.15 * channel_ratio + 0.15 * (1.0 - penalty)
    return round(max(0.05, min(0.95, c)), 2)


def build_findings(ds: dict, cls: dict, assess: dict, issues: list[dict],
                   confidence: float, th: dict) -> list[dict]:
    findings = []
    losses = cls["losses"]
    primary = cls["primary_loss"]
    if primary is None:
        return findings

    machine = (ds.get("meta") or {}).get("machine_id", "the asset")
    ordered = [l for l in losses if l["significant"]] or losses[:1]

    for idx, loss in enumerate(ordered):
        bucket = loss["bucket"]
        is_primary = bucket == primary["bucket"]
        claimed = assess["root_cause_claimed"] and is_primary
        codes = loss.get("reason_codes") or {}
        code_txt = ", ".join(f"{c} x{n}" for c, n in
                             sorted(codes.items(), key=lambda kv: -kv[1])[:3])
        verb = "attributed to" if claimed else "concentrated in"
        problem = (f"{loss['loss_minutes']:.0f} min of {loss['factor']} loss on {machine} "
                   f"{verb} {bucket.replace('_', ' ')}"
                   f"{' (' + code_txt + ')' if code_txt else ''} "
                   f"- {loss['share_of_total_loss'] * 100:.0f}% of total loss")
        hypotheses = list(HYPOTHESIS_CATALOGUE.get(bucket, []))
        if _order_boundary_nearby(ds) and bucket in ("setup_and_adjustments", "startup_rejects"):
            hypotheses.append("Correlated with an order boundary in orders[]; correlation only, not established as cause")
        if ds.get("maintenance_history") and bucket == "breakdowns":
            hypotheses.append("Maintenance work orders exist in the same period; correlation only, not established as cause")

        if assess["status"] == "insufficient_evidence":
            actions = list(MISSING_EVIDENCE_FOR.get(bucket, [])) or ACTION_CATALOGUE.get(bucket, [])
            actions = [f"Collect: {a}" if not a.startswith(("Collect", "Enable", "Make", "Introduce")) else a
                       for a in actions]
        else:
            actions = list(ACTION_CATALOGUE.get(bucket, []))

        findings.append({
            "problem": problem,
            "evidence": loss["evidence"][:8],
            "hypothesis": hypotheses,
            "recommended_action": actions,
            "confidence": confidence if is_primary else round(max(0.05, confidence - 0.10), 2),
            "bucket": bucket,
            "cause_claimed": claimed,
            "corroboration": assess.get("corroboration_matches", []) if is_primary else [],
        })
        if idx >= 2:
            break
    return findings


def _order_boundary_nearby(ds: dict) -> bool:
    return bool(ds.get("orders")) and len(ds.get("orders") or []) > 1


def missing_evidence_list(ds: dict, cls: dict, issues: list[dict]) -> list[str]:
    out: list[str] = []
    for loss in cls["losses"]:
        if loss["coverage"] < 1.0:
            out.extend(MISSING_EVIDENCE_FOR.get(loss["bucket"], []))
    for i in issues:
        if i["code"] == "NO_DOWNTIME_EVENTS":
            out.append("stop event log with reason codes for the period")
        if i["code"] == "NO_QUALITY_EVENTS":
            out.append("defect records with code and phase for the rejects")
        if i["code"] == "NO_SPEED_EVIDENCE":
            out.append("cycle-time log or micro-stop count for the period")
        if i["code"] == "ICT_SUSPICIOUS":
            out.append("confirmation of the ideal cycle time against the machine nameplate")
    if not ds.get("maintenance_history"):
        out.append("maintenance work orders for the asset over the period")
    seen, dedup = set(), []
    for o in out:
        if o not in seen:
            seen.add(o)
            dedup.append(o)
    return dedup


# --------------------------------------------------------------------------
# Top level
# --------------------------------------------------------------------------

def analyse(ds: dict, ruleset: str = DEFAULT_RULESET,
            threshold_overrides: dict | None = None) -> dict:
    th = thresholds_for(ds, threshold_overrides)
    issues = validate(ds, ruleset=ruleset, th=th)
    result = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "ruleset": ruleset,
        "meta": ds.get("meta") or {},
        "status": "ok",
        "issues": issues,
        "metrics": None,
        "losses": [],
        "primary_loss": None,
        "findings": [],
        "missing_evidence": [],
        "thresholds": th,
    }

    if has_errors(issues):
        result["status"] = "data_error"
        result["confidence"] = 0.0
        result["root_cause_claimed"] = False
        result["missing_evidence"] = [
            f"corrected value for '{i['field']}'" for i in issues if i["severity"] == "error"
        ]
        return result

    metrics = calculate(ds, ruleset=ruleset)
    if metrics is None:
        result["status"] = "data_error"
        result["confidence"] = 0.0
        result["root_cause_claimed"] = False
        result["issues"].append(issue("MISSING_FIELD", "error", "production",
                                      "metrics could not be computed from the supplied fields"))
        return result

    result["metrics"] = metrics
    cls = classify(ds, metrics, ruleset=ruleset, th=th)
    result["losses"] = [{k: v for k, v in l.items() if k != "evidence"} for l in cls["losses"]]
    result["primary_loss"] = cls["primary_loss"]
    result["total_loss_minutes"] = cls["total_loss_minutes"]

    assess = evidence_assessment(ds, cls, issues, ruleset=ruleset, th=th)
    conf = confidence_score(assess["attribution"], ds, issues)
    result["status"] = assess["status"]
    result["attribution_coverage"] = round(assess["attribution"], 4)
    result["root_cause_claimed"] = assess["root_cause_claimed"]
    result["corroboration_matches"] = assess.get("corroboration_matches", [])
    result["confidence"] = conf
    if assess["status"] == "insufficient_evidence":
        result["reason"] = assess["reason"]
        result["what_is_still_valid"] = ["availability", "performance", "quality", "oee"]
    result["findings"] = build_findings(ds, cls, assess, issues, conf, th)
    result["missing_evidence"] = missing_evidence_list(ds, cls, issues)
    return result
