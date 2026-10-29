"""Bounded, read-only loader for two Databricks-exported synthetic CSV reports.

This module does not contain Databricks credentials, SQL clients, model calls,
or mutation interfaces. It never reads outside the configured data directory.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_BYTES = 2_000_000
MAX_ROWS = 1_000
GOLD_COLUMNS = (
    "region", "part_type", "shipment_count", "units_total",
    "modeled_inventory_value_usd", "delayed_shipments", "delayed_pct",
    "first_shipment_date", "last_shipment_date",
)
REASONS_COLUMNS = ("quarantine_reason", "count")


class SnapshotError(ValueError):
    """Export is absent, invalid, or inconsistent."""


@dataclass(frozen=True)
class Snapshot:
    gold: list[dict[str, Any]]
    quarantine_reasons: list[dict[str, Any]]
    totals: dict[str, Any]


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise SnapshotError(f"Missing {path.name}. Export it from the completed Databricks notebook.")
    if path.stat().st_size > MAX_BYTES:
        raise SnapshotError(f"{path.name} exceeds the 2 MB size limit")
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SnapshotError(f"{path.name} has no header row")
        if set(reader.fieldnames) != set(columns) or len(reader.fieldnames) != len(columns):
            raise SnapshotError(
                f"{path.name} requires exactly these columns: {', '.join(columns)}"
            )
        rows = []
        for item in reader:
            if len(rows) >= MAX_ROWS:
                raise SnapshotError(f"{path.name} exceeds the {MAX_ROWS} row limit")
            if None in item or any(v is None for v in item.values()):
                raise SnapshotError(f"{path.name} contains a malformed row")
            if any(len(v) > 160 for v in item.values()):
                raise SnapshotError(f"{path.name} has an overlong cell")
            rows.append(item)
    if not rows:
        raise SnapshotError(f"{path.name} must contain at least one data row")
    return rows


def _int(value: str, field: str) -> int:
    try:
        n = int(value.strip())
    except (ValueError, AttributeError):
        raise SnapshotError(f"Invalid whole number in {field}") from None
    if n < 0:
        raise SnapshotError(f"Negative whole number in {field}")
    return n


def _decimal(value: str, field: str) -> Decimal:
    try:
        d = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise SnapshotError(f"Invalid number in {field}") from None
    if not d.is_finite() or d < 0:
        raise SnapshotError(f"Invalid nonnegative number in {field}")
    return d


def read_snapshot(data_dir: str | Path) -> Snapshot:
    """Read exact fixed filenames; derive all KPIs from exported records."""
    directory = Path(data_dir)
    rows = _read_csv(directory / "gold.csv", GOLD_COLUMNS)
    reason_rows = _read_csv(directory / "quarantine_reasons.csv", REASONS_COLUMNS)
    gold: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        region = row["region"].strip()
        part_type = row["part_type"].strip()
        if not region or not part_type:
            raise SnapshotError("Gold region and part type cannot be empty")
        key = (region, part_type)
        if key in seen:
            raise SnapshotError("Gold contains duplicate region/part_type segments")
        seen.add(key)
        shipments = _int(row["shipment_count"], "shipment_count")
        delayed = _int(row["delayed_shipments"], "delayed_shipments")
        percent = _decimal(row["delayed_pct"], "delayed_pct")
        inventory = _decimal(row["modeled_inventory_value_usd"], "modeled_inventory_value_usd")
        if shipments == 0 or delayed > shipments or percent > 100:
            raise SnapshotError("Inconsistent Gold shipment/delay counts")
        if abs(percent - Decimal(100 * delayed) / Decimal(shipments)) > Decimal("0.02"):
            raise SnapshotError("Gold delayed_pct differs from underlying counts")
        gold.append({
            "region": region, "part_type": part_type,
            "shipment_count": shipments,
            "units_total": _int(row["units_total"], "units_total"),
            "modeled_inventory_value_usd": float(inventory),
            "delayed_shipments": delayed, "delayed_pct": float(percent),
            "first_shipment_date": row["first_shipment_date"],
            "last_shipment_date": row["last_shipment_date"],
        })
    reasons: list[dict[str, Any]] = []
    reason_seen: set[str] = set()
    for row in reason_rows:
        name = row["quarantine_reason"].strip()
        if not name or name in reason_seen:
            raise SnapshotError("Quarantine reason is empty or duplicated")
        reason_seen.add(name)
        reasons.append({"quarantine_reason": name, "count": _int(row["count"], "count")})
    accepted = sum(r["shipment_count"] for r in gold)
    quarantined = sum(r["count"] for r in reasons)
    source = accepted + quarantined
    if source <= 0:
        raise SnapshotError("No records in exported snapshot")
    totals = {
        "source_rows": source,
        "accepted_rows": accepted,
        "quarantined_rows": quarantined,
        "gold_segments": len(gold),
        "declared_rule_pass_pct": round(100 * accepted / source, 2),
        "delayed_shipments": sum(r["delayed_shipments"] for r in gold),
        "modeled_inventory_value_usd": round(sum(r["modeled_inventory_value_usd"] for r in gold), 2),
        "data_source": "User-downloaded CSV results from Databricks notebook",
        "scope_note": "Synthetic records; checks cover only declared quality rules. Not an enterprise readiness certification.",
    }
    return Snapshot(gold=gold, quarantine_reasons=reasons, totals=totals)
