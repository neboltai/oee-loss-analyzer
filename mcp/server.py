#!/usr/bin/env python3
"""shopfloor-data — local demo MCP server for the Community Edition.

The server exposes representative production, downtime, machine-event, order
and maintenance tools over a fictional dataset. It never reaches an external
system. Production connectors are intentionally not included.

Exposes five read-only tools plus one composite:

    get_production_data(machine_id, date_from, date_to, shift?)
    get_downtime(machine_id, date_from, date_to)
    get_machine_events(machine_id, date_from, date_to, event_type?)
    get_orders(machine_id, date_from, date_to)
    get_maintenance_history(machine_id, date_from, date_to)
    build_oee_dataset(machine_id, date_from, date_to, shift?)   # merged, canonical

Transport: stdio JSON-RPC 2.0, standard library only — no pip install needed.

Configuration
-------------
OEE_MCP_MOCK_DIR  directory holding the mock JSON files
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from adapters import get_adapter, load_config  # noqa: E402

SERVER_NAME = "shopfloor-data"
SERVER_VERSION = "0.4.0"
PROTOCOL_VERSION = "2025-06-18"

_RANGE = {
    "machine_id": {"type": "string", "description": "Asset identifier as it appears in the source system"},
    "date_from": {"type": "string", "description": "ISO date or datetime, inclusive"},
    "date_to": {"type": "string", "description": "ISO date or datetime, inclusive"},
}


def _schema(extra: dict | None = None, required=("machine_id", "date_from", "date_to")) -> dict:
    props = dict(_RANGE)
    props.update(extra or {})
    return {"type": "object", "properties": props, "required": list(required)}


TOOLS = [
    {
        "name": "get_production_data",
        "description": ("Planned production time, downtime total, ideal cycle time, total and good "
                        "counts for an asset over a period. This is the minimum dataset an OEE "
                        "calculation needs. Returns one record per shift."),
        "inputSchema": _schema({"shift": {"type": "string", "description": "Optional shift filter, e.g. S1"}}),
    },
    {
        "name": "get_downtime",
        "description": ("Stop events with start, duration and reason code. Needed to attribute "
                        "availability losses; without it, downtime causes cannot be established."),
        "inputSchema": _schema(),
    },
    {
        "name": "get_machine_events",
        "description": ("Machine telemetry: alarms, state changes, cycle times and micro-stop counts. "
                        "Use it to separate minor stops from reduced speed and to corroborate failures."),
        "inputSchema": _schema({"event_type": {"type": "string",
                                               "description": "Optional filter: alarm, state_change, speed, counter"}}),
    },
    {
        "name": "get_orders",
        "description": ("Production orders with product, quantity and time window. Use it to locate "
                        "changeover boundaries and to normalise ideal cycle time per product."),
        "inputSchema": _schema(),
    },
    {
        "name": "get_maintenance_history",
        "description": ("Work orders from the CMMS: preventive, corrective, inspections, part "
                        "replacements. Use it to corroborate a breakdown finding - never as proof "
                        "of cause on its own."),
        "inputSchema": _schema(),
    },
    {
        "name": "build_oee_dataset",
        "description": ("Convenience: calls the five sources and returns one canonical dataset ready "
                        "for the oee-loss-analyzer skill (assets/dataset.schema.json). Sources that "
                        "return nothing are reported as missing rather than filled in."),
        "inputSchema": _schema({"shift": {"type": "string"}}),
    },
]

KIND_OF_TOOL = {
    "get_production_data": "production",
    "get_downtime": "downtime",
    "get_machine_events": "machine_events",
    "get_orders": "orders",
    "get_maintenance_history": "maintenance",
}


# --------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------

def fetch(kind: str, args: dict) -> list:
    cfg = load_config()
    adapter = get_adapter(kind, cfg)
    return adapter.fetch(kind, args)


def build_dataset(args: dict) -> dict:
    machine = args.get("machine_id")
    prod = fetch("production", args)
    missing = []

    if not prod:
        return {"error": "no production data for this asset and period",
                "machine_id": machine,
                "note": "no metrics can be computed; do not estimate the missing values"}

    shift = args.get("shift")
    rows = [r for r in prod if not shift or str(r.get("shift")) == str(shift)]
    if not rows:
        rows = prod

    agg = {
        "planned_production_time_min": sum(float(r.get("planned_production_time_min", 0)) for r in rows),
        "downtime_min": sum(float(r.get("downtime_min", 0)) for r in rows),
        "total_count": sum(float(r.get("total_count", 0)) for r in rows),
        "good_count": sum(float(r.get("good_count", 0)) for r in rows),
    }
    icts = {float(r["ideal_cycle_time_sec"]) for r in rows if r.get("ideal_cycle_time_sec")}
    if len(icts) == 1:
        agg["ideal_cycle_time_sec"] = icts.pop()
    elif len(icts) > 1:
        missing.append(f"a single ideal cycle time: the period mixes {sorted(icts)} s - "
                       "analyse one product at a time")
    else:
        missing.append("ideal_cycle_time_sec")

    downtime = fetch("downtime", args)
    events = fetch("machine_events", args)
    orders = fetch("orders", args)
    maint = fetch("maintenance", args)

    if not downtime:
        missing.append("downtime events with reason codes")
    if not events:
        missing.append("machine events / cycle-time log")
    if not maint:
        missing.append("maintenance work orders")

    micro = None
    speed = [e for e in events if str(e.get("type")) == "speed"]
    counters = [e for e in events if str(e.get("type")) == "counter" and e.get("micro_stop_count")]
    if counters:
        micro = {
            "count": sum(int(c.get("micro_stop_count", 0)) for c in counters),
            "total_min": sum(float(c.get("micro_stop_min", 0)) for c in counters),
            "source": "machine_events.counter",
        }

    ds = {
        "meta": {"machine_id": machine, "shift": shift, "date": args.get("date_from"),
                 "period": {"from": args.get("date_from"), "to": args.get("date_to")},
                 "source": "MCP:shopfloor-data"},
        "production": agg,
        "downtime_events": downtime,
        "machine_events": [e for e in events if str(e.get("type")) != "speed"],
        "orders": orders,
        "maintenance_history": maint,
    }
    if speed:
        ds["speed_log"] = [{"ts": s.get("ts"), "actual_cycle_time_sec": s.get("actual_cycle_time_sec")}
                           for s in speed]
    if micro:
        ds["micro_stops"] = micro
    quality = [e for e in events if str(e.get("type")) == "defect"]
    if quality:
        ds["quality_events"] = [{"id": q.get("code"), "defect_code": q.get("defect_code"),
                                 "count": q.get("count"), "phase": q.get("phase", "unknown")}
                                for q in quality]
    else:
        missing.append("defect records with code and phase")

    ds["_missing_sources"] = missing
    ds["_note"] = ("Fields absent from the source systems are listed in _missing_sources and are NOT "
                   "filled in. Run validate.py before calculating.")
    return ds


def call_tool(name: str, args: dict):
    if name == "build_oee_dataset":
        return build_dataset(args)
    kind = KIND_OF_TOOL.get(name)
    if not kind:
        raise ValueError(f"unknown tool: {name}")
    rows = fetch(kind, args)
    return {"machine_id": args.get("machine_id"), "count": len(rows), "rows": rows}


# --------------------------------------------------------------------------
# JSON-RPC / MCP plumbing
# --------------------------------------------------------------------------

def respond(msg_id, result=None, error=None) -> None:
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def handle(msg: dict) -> None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        respond(msg_id, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": ("Read-only access to production, downtime, machine event, order and "
                             "maintenance data. Call build_oee_dataset for a ready-to-analyse "
                             "dataset, or the individual tools when a specific evidence channel is "
                             "needed. Never fill a gap these tools report as missing."),
        })
    elif method in ("notifications/initialized", "notifications/cancelled"):
        return
    elif method == "ping":
        respond(msg_id, {})
    elif method == "tools/list":
        respond(msg_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            data = call_tool(name, args)
            respond(msg_id, {"content": [{"type": "text",
                                          "text": json.dumps(data, indent=2, ensure_ascii=False)}],
                             "isError": False})
        except Exception as exc:  # surfaced to the model, not swallowed
            respond(msg_id, {"content": [{"type": "text",
                                          "text": f"{type(exc).__name__}: {exc}"}],
                             "isError": True})
    elif msg_id is not None:
        respond(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            handle(msg)
        except Exception:
            traceback.print_exc(file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
