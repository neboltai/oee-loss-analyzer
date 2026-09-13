"""Mock backend: reads the JSON files in mcp/mock_data.

Used for demos, for the server smoke test, and as the reference shape every
other adapter must return.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .base import Adapter, filter_rows

FILES = {
    "production": "production.json",
    "downtime": "downtime.json",
    "machine_events": "machine_events.json",
    "orders": "orders.json",
    "maintenance": "maintenance.json",
}


class MockAdapter(Adapter):
    def _dir(self) -> Path:
        d = self.source.get("dir") or self.connection.get("dir") \
            or os.environ.get("OEE_MCP_MOCK_DIR") \
            or str(Path(__file__).resolve().parent.parent / "mock_data")
        return Path(d)

    def fetch(self, kind: str, args: dict) -> list:
        path = self._dir() / FILES[kind]
        if not path.is_file():
            return []
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        rows = filter_rows(rows, args)
        if kind == "production" and args.get("shift"):
            rows = [r for r in rows if str(r.get("shift")) == str(args["shift"])]
        if kind == "machine_events" and args.get("event_type"):
            rows = [r for r in rows if str(r.get("type")) == str(args["event_type"])]
        return rows
