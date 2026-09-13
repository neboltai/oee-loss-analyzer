#!/usr/bin/env python3
"""Drive the MCP server over stdio and check the handshake and every tool.

    python3 mcp/smoke_test.py

Exits non-zero on the first failure. Uses the mock backend, so it needs no
credentials and touches no real system.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARGS = {"machine_id": "L1-PRESS-02", "date_from": "2026-09-08", "date_to": "2026-09-08"}
TOOLS = ["get_production_data", "get_downtime", "get_machine_events",
         "get_orders", "get_maintenance_history", "build_oee_dataset"]


def main() -> int:
    env = dict(os.environ)
    env["OEE_MCP_BACKEND"] = "mock"
    env["OEE_MCP_MOCK_DIR"] = str(HERE / "mock_data")
    env.pop("OEE_MCP_CONFIG", None)

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "smoke-test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    for i, tool in enumerate(TOOLS, start=3):
        requests.append({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                         "params": {"name": tool, "arguments": ARGS}})

    payload = "\n".join(json.dumps(r) for r in requests) + "\n"
    proc = subprocess.run([sys.executable, str(HERE / "server.py")], input=payload,
                          capture_output=True, text=True, env=env, timeout=60)
    if proc.stderr.strip():
        print("server stderr:\n" + proc.stderr, file=sys.stderr)

    responses = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        responses[msg.get("id")] = msg

    ok = True

    init = responses.get(1, {}).get("result", {})
    assert_ok = init.get("serverInfo", {}).get("name") == "shopfloor-data"
    print(f"[{'PASS' if assert_ok else 'FAIL'}] initialize -> {init.get('serverInfo')}")
    ok &= assert_ok

    listed = [t["name"] for t in responses.get(2, {}).get("result", {}).get("tools", [])]
    tools_ok = set(TOOLS) == set(listed)
    print(f"[{'PASS' if tools_ok else 'FAIL'}] tools/list -> {len(listed)} tools")
    ok &= tools_ok

    for i, tool in enumerate(TOOLS, start=3):
        res = responses.get(i, {}).get("result", {})
        text = (res.get("content") or [{}])[0].get("text", "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        if tool == "build_oee_dataset":
            prod = data.get("production", {})
            good = (prod.get("planned_production_time_min") == 960
                    and prod.get("downtime_min") == 157
                    and prod.get("total_count") == 1460
                    and len(data.get("downtime_events", [])) == 7
                    and "micro_stops" in data and "speed_log" in data
                    and len(data.get("quality_events", [])) == 2)
            detail = f"ppt={prod.get('planned_production_time_min')} dt={prod.get('downtime_min')} " \
                     f"events={len(data.get('downtime_events', []))} missing={data.get('_missing_sources')}"
        else:
            good = not res.get("isError") and data.get("count", 0) > 0
            detail = f"{data.get('count')} rows"
        print(f"[{'PASS' if good else 'FAIL'}] {tool:26} {detail}")
        ok &= good

    print("\nSMOKE TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
