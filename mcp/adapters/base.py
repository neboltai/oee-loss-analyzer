"""Adapter interface and shared filtering helpers."""
from __future__ import annotations

import re


class Adapter:
    """Read-only access to one source system family."""

    kinds = ("production", "downtime", "machine_events", "orders", "maintenance")

    def __init__(self, source: dict | None = None, connection: dict | None = None):
        self.source = source or {}
        self.connection = connection or {}

    def fetch(self, kind: str, args: dict) -> list:  # pragma: no cover - interface
        raise NotImplementedError


def day(value) -> str:
    """Reduce an ISO date or datetime to its date part; '' when unusable."""
    if value is None:
        return ""
    s = str(value)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def in_range(row: dict, args: dict, fields=("date", "start", "ts")) -> bool:
    lo, hi = day(args.get("date_from")), day(args.get("date_to"))
    if not lo and not hi:
        return True
    stamp = ""
    for f in fields:
        if row.get(f):
            stamp = day(row[f])
            break
    if not stamp:
        return True  # undated rows are returned, never silently dropped
    if lo and stamp < lo:
        return False
    if hi and stamp > hi:
        return False
    return True


def machine_matches(row: dict, args: dict) -> bool:
    want = args.get("machine_id")
    if not want:
        return True
    got = row.get("machine_id") or row.get("machine") or row.get("asset")
    return got is None or str(got) == str(want)


def filter_rows(rows: list, args: dict) -> list:
    return [r for r in rows if machine_matches(r, args) and in_range(r, args)]
