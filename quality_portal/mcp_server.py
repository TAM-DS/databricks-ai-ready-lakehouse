"""Three fixed read-only MCP operations over the exact two exported CSVs."""
from __future__ import annotations

import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .core import read_snapshot, SnapshotError

DATA_DIR = Path(os.environ.get("QUALITY_DATA_DIR", "data"))
mcp = FastMCP("ai-ready-quality-evidence")


def _snapshot():
    try:
        return read_snapshot(DATA_DIR)
    except SnapshotError as exc:
        return {"error": str(exc), "available": False}


@mcp.tool()
def get_quality_summary() -> dict:
    """Read synthetic Databricks quality totals from downloaded CSVs; no live data access."""
    result = _snapshot()
    return result if isinstance(result, dict) else result.totals


@mcp.tool()
def list_quarantine_reasons() -> dict:
    """Read the bounded rejection-reason counts, without modifying any data."""
    result = _snapshot()
    return result if isinstance(result, dict) else {"reasons": result.quarantine_reasons}


@mcp.tool()
def list_gold_segments(region: str = "", limit: int = 16) -> dict:
    """Read up to 100 Gold summary segments, optionally filtered by exact region."""
    if not (1 <= limit <= 100):
        return {"error": "limit must be between 1 and 100"}
    result = _snapshot()
    if isinstance(result, dict):
        return result
    matches = [r for r in result.gold if not region or r["region"] == region]
    return {"segments": matches[:limit], "returned": min(limit, len(matches)), "total_matching": len(matches)}


if __name__ == "__main__":
    # Local stdio only: no HTTP listener, web access, arbitrary SQL, or deployment tools.
    mcp.run(transport="stdio")
