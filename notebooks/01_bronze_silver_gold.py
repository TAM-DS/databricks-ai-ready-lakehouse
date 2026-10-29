# Databricks notebook source
# MAGIC %md
# MAGIC # AI-Ready Data Platform — 01: Bronze → Silver → Gold
# MAGIC
# MAGIC **Objective:** Build an auditable synthetic energy/supply-chain quality pipeline with PySpark, Spark SQL, Delta Lake, and Unity Catalog.
# MAGIC
# MAGIC **Safety / scope:** Uses synthetic data only. Creates or replaces four demo Delta tables in a dedicated `ai_ready_demo` schema in your current catalog. Does not modify existing non-demo datasets, grant privileges, connect to external services, or invoke a model.
# MAGIC
# MAGIC **Evidence standard:** The final assertions must pass before this can be called a successful Databricks execution. Do not claim Unity Catalog lineage or governance settings until independently checked in Catalog Explorer.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Locate the current Unity Catalog catalog and create an isolated demo schema
# MAGIC
# MAGIC Attach this notebook to **Serverless** compute. You should have permission to create a schema in your workspace catalog.

# COMMAND ----------
import random
from datetime import date, timedelta
from decimal import Decimal
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DecimalType
)

context = spark.sql("SELECT current_catalog() AS catalog, current_schema() AS schema").first()
CATALOG = context["catalog"]
assert CATALOG and CATALOG != "hive_metastore", (
    "Select a Unity Catalog workspace catalog before running this notebook."
)

def quoted(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"

SCHEMA = "ai_ready_demo"
namespace = f"{quoted(CATALOG)}.{quoted(SCHEMA)}"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {namespace}")

def fq_table(name: str) -> str:
    return f"{namespace}.{quoted(name)}"

BRONZE = fq_table("sc_bronze")
SILVER = fq_table("sc_silver")
QUARANTINE = fq_table("sc_quarantine")
GOLD = fq_table("sc_gold")

print("Catalog:", CATALOG)
print("Demo schema:", SCHEMA)
print("Tables:", BRONZE, SILVER, QUARANTINE, GOLD, sep="\n  ")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Generate a reproducible synthetic shipment dataset
# MAGIC
# MAGIC 1,200 valid source shipments, then intentionally introduce 60 faulty/duplicate records for quality-control testing. Fictional IDs and amounts; no sensitive information.

# COMMAND ----------
SEED = 20261029
rng = random.Random(SEED)
regions = ("Gulf Coast", "Midwest", "Southwest", "Northeast")
part_types = ("Transformer", "Inverter", "Turbine Component", "Cooling Module")
statuses = ("IN_TRANSIT", "DELIVERED", "DELAYED")
records = []

def add_record(shipment_id, supplier_id, part_type, region, event_date, quantity, unit_cost, status):
    event_id = f"EV{len(records) + 1:06d}"
    records.append((
        event_id, shipment_id, supplier_id, part_type, region, event_date,
        quantity, unit_cost, status, "SYNTHETIC-20261029"
    ))

for i in range(1, 1201):
    shipment_date = (date(2026, 10, 1) + timedelta(days=(i - 1) % 28)).isoformat()
    add_record(
        shipment_id=f"SHP{i:06d}",
        supplier_id=f"SUP{(i % 24) + 1:03d}",
        part_type=part_types[i % len(part_types)],
        region=regions[(i // 4) % len(regions)],
        event_date=shipment_date,
        quantity=rng.randint(1, 100),
        unit_cost=Decimal(f"{rng.uniform(100, 3500):.2f}"),
        status=statuses[i % len(statuses)],
    )

# 12 missing suppliers
for i in range(12):
    add_record(f"BAD-SUP-{i:03d}", None, "Transformer", "Gulf Coast", "2026-10-12", 10, Decimal("500.00"), "DELIVERED")
# 10 nonpositive quantities
for i in range(10):
    add_record(f"BAD-QTY-{i:03d}", "SUP003", "Inverter", "Southwest", "2026-10-13", 0, Decimal("300.00"), "DELAYED")
# 8 negative unit costs
for i in range(8):
    add_record(f"BAD-COST-{i:03d}", "SUP004", "Cooling Module", "Midwest", "2026-10-14", 6, Decimal("-5.00"), "IN_TRANSIT")
# 6 invalid dates
for i in range(6):
    add_record(f"BAD-DATE-{i:03d}", "SUP005", "Transformer", "Northeast", "not-a-date", 3, Decimal("100.00"), "DELIVERED")
# 9 invalid statuses
for i in range(9):
    add_record(f"BAD-STATUS-{i:03d}", "SUP006", "Inverter", "Gulf Coast", "2026-10-15", 8, Decimal("800.00"), "UNKNOWN")
# 15 distinct extra events referring to shipment IDs already present
for i in range(1, 16):
    original = records[i - 1]
    add_record(original[1], original[2], original[3], original[4], original[5], original[6], original[7], original[8])

assert len(records) == 1260

source_schema = StructType([
    StructField("event_id", StringType(), False),
    StructField("shipment_id", StringType(), False),
    StructField("supplier_id", StringType(), True),
    StructField("part_type", StringType(), False),
    StructField("region", StringType(), False),
    StructField("event_date", StringType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("unit_cost_usd", DecimalType(12, 2), True),
    StructField("status", StringType(), True),
    StructField("source_batch", StringType(), False),
])

bronze_df = spark.createDataFrame(records, schema=source_schema)
bronze_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(BRONZE)
print(f"BRONZE: {spark.table(BRONZE).count()} synthetic source events")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Spark SQL quality checks and deterministic quarantine
# MAGIC
# MAGIC Invalid supplier IDs, quantities, unit costs, dates, statuses, and duplicate shipment events are quarantined, not silently dropped.
# MAGIC
# MAGIC The `try_cast` prevents an invalid date from crashing validation in ANSI mode. The earliest deterministic `event_id` wins for duplicate shipment IDs.

# COMMAND ----------
stage_view = "ai_ready_sc_checked"
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW {stage_view} AS
WITH ranked AS (
    SELECT
        b.*,
        TRY_CAST(b.event_date AS DATE) AS shipment_date,
        ROW_NUMBER() OVER (
            PARTITION BY b.shipment_id ORDER BY b.event_id
        ) AS shipment_occurrence
    FROM {BRONZE} b
)
SELECT ranked.*,
    CONCAT_WS('; ',
        CASE WHEN supplier_id IS NULL OR TRIM(supplier_id) = ''
            THEN 'missing_supplier' END,
        CASE WHEN quantity IS NULL OR quantity <= 0
            THEN 'invalid_quantity' END,
        CASE WHEN unit_cost_usd IS NULL OR unit_cost_usd < 0
            THEN 'invalid_unit_cost' END,
        CASE WHEN shipment_date IS NULL
            THEN 'invalid_date' END,
        CASE WHEN status IS NULL OR status NOT IN ('IN_TRANSIT', 'DELIVERED', 'DELAYED')
            THEN 'invalid_status' END,
        CASE WHEN shipment_occurrence > 1
            THEN 'duplicate_shipment' END
    ) AS quarantine_reason
FROM ranked
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {SILVER} USING DELTA AS
SELECT event_id, shipment_id, supplier_id, part_type, region,
       shipment_date, quantity, unit_cost_usd, status, source_batch
FROM {stage_view}
WHERE quarantine_reason = ''
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {QUARANTINE} USING DELTA AS
SELECT event_id, shipment_id, supplier_id, part_type, region,
       event_date, quantity, unit_cost_usd, status, source_batch,
       quarantine_reason
FROM {stage_view}
WHERE quarantine_reason <> ''
""")

print("SILVER accepted:", spark.table(SILVER).count())
print("QUARANTINE rejected:", spark.table(QUARANTINE).count())

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Gold — AI-ready, aggregated operations data
# MAGIC
# MAGIC This is an operational reporting surface, **not** a claim that an external AI agent is authorized to act on the data. Inventory value is modeled as units × unit cost—not revenue or booked financials.

# COMMAND ----------
spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD} USING DELTA AS
SELECT
    region,
    part_type,
    COUNT(*) AS shipment_count,
    SUM(quantity) AS units_total,
    ROUND(SUM(quantity * unit_cost_usd), 2) AS modeled_inventory_value_usd,
    SUM(CASE WHEN status = 'DELAYED' THEN 1 ELSE 0 END) AS delayed_shipments,
    ROUND(100.0 * SUM(CASE WHEN status = 'DELAYED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS delayed_pct,
    MIN(shipment_date) AS first_shipment_date,
    MAX(shipment_date) AS last_shipment_date
FROM {SILVER}
GROUP BY region, part_type
""")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Verify the pipeline with observable assertions
# MAGIC
# MAGIC Expected synthetic results: **1,260 source rows → 1,200 accepted + 60 quarantined**. This check is executed on the actual Databricks tables—not merely calculated from the in-memory generator.

# COMMAND ----------
from pyspark.sql import functions as F

source_count = spark.table(BRONZE).count()
accepted_count = spark.table(SILVER).count()
rejected_count = spark.table(QUARANTINE).count()
distinct_shipments = spark.table(SILVER).select("shipment_id").distinct().count()
gold_count = spark.table(GOLD).count()

assert source_count == 1260, f"Expected 1260 raw rows, found {source_count}"
assert accepted_count == 1200, f"Expected 1200 validated rows, found {accepted_count}"
assert rejected_count == 60, f"Expected 60 quarantined rows, found {rejected_count}"
assert accepted_count + rejected_count == source_count, "Rows were lost across the validation boundary"
assert distinct_shipments == accepted_count, "Duplicate shipment IDs survived Silver"
assert gold_count > 0, "Gold aggregation is empty"
assert spark.table(SILVER).filter(
    (F.col("quantity") <= 0) |
    (F.col("unit_cost_usd") < 0) |
    F.col("supplier_id").isNull() |
    F.col("shipment_date").isNull()
).count() == 0, "Invalid records survived Silver"

readiness_pct = round(100.0 * accepted_count / source_count, 2)
print("VALIDATED — actual Delta tables")
print("Source rows:", source_count)
print("Accepted rows:", accepted_count)
print("Quarantined rows:", rejected_count)
print("Distinct accepted shipment IDs:", distinct_shipments)
print("Gold segments:", gold_count)
print("Pass rate for these declared quality rules (%):", readiness_pct)
print("NOTE: This is synthetic test coverage, not a comprehensive enterprise data-readiness score.")

print("\nQuarantine reasons:")
display(spark.table(QUARANTINE).groupBy("quarantine_reason").count().orderBy("quarantine_reason"))
print("\nGold data product:")
display(spark.table(GOLD).orderBy("region", "part_type"))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Proof checklist in Databricks
# MAGIC
# MAGIC 1. Save a screenshot showing the **VALIDATED** assertions and the quarantine breakdown.
# MAGIC 2. Open **Catalog Explorer → your workspace catalog → `ai_ready_demo`**, and confirm the four tables exist.
# MAGIC 3. Inspect table-level **Lineage** for Silver and Gold. Lineage visibility/availability must be confirmed in your workspace—do not infer it from successful writes.
# MAGIC 4. Later, wrap this notebook in a Databricks **Lakeflow Job** and preserve a successful run link/screenshot.
# MAGIC 5. After cloud validation, add a bounded read-only export for **Gradio + Docker + MCP**. Those local interfaces will not automatically inherit Unity Catalog access controls.
# MAGIC
# MAGIC **Build it. Secure it. Test it. Prove it.**
