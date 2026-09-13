"""Demo backend for the Community Edition MCP server.

The public package intentionally ships only the local mock adapter. Production
connectors, credentials, tenant routing and customer-specific mappings belong
to a separately operated integration layer.
"""
from __future__ import annotations

from .base import Adapter  # noqa: F401
from .mock import MockAdapter

BACKENDS = {
    "mock": MockAdapter,
}


def load_config() -> dict:
    return {"default": "mock", "sources": {}, "connections": {}}


def get_adapter(kind: str, cfg: dict) -> Adapter:
    source = cfg["sources"].get(kind, {})
    name = source.get("backend", cfg.get("default", "mock"))
    cls = BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"unknown backend '{name}' for source '{kind}'; "
                         f"known backends: {', '.join(sorted(BACKENDS))}")
    conn = cfg["connections"].get(source.get("ref", ""), {})
    return cls(source=source, connection=conn)
