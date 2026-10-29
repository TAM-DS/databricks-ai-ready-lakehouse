# October 29, 2026 — observed test evidence

| Component | Observation | Evidence source |
|---|---|---|
| Databricks PySpark and Spark SQL | Notebook printed `VALIDATED` after assertions on persisted Delta tables | User-shared notebook output |
| Synthetic quality sample | 1,260 source rows; 1,200 accepted; 60 quarantined; 1,200 distinct accepted shipment IDs; 16 Gold groups | Notebook output and local Gradio dashboard |
| Quarantine classification | Six reason categories, counts 15, 6, 10, 9, 8, and 12; total 60 | Local Gradio + MCP results |
| Unity Catalog persistence | `sc_bronze`, `sc_silver`, `sc_quarantine`, `sc_gold` in `workspace.ai_ready_demo` | Catalog Explorer screenshot, provided by the project owner |
| Unity Catalog lineage | Bronze → Silver → Gold, table-level lineage shown in Catalog Explorer | [`evidence/01-lineage.png`](evidence/01-lineage.png) |
| Databricks managed workflow | One manual serverless Job run finished **Succeeded** in **1m 12s** | [`evidence/02-managed-job.png`](evidence/02-managed-job.png) |
| Local Gradio | UI displayed all 16 Gold groups and six quarantine reasons from manually exported CSVs | [`evidence/03-gradio.png`](evidence/03-gradio.png) |
| Python parser tests | **6 passed** in **0.003 seconds** on the Mac | User-shared Terminal observation, 2026-10-29 |
| Docker | `docker compose up --build` built the image and launched the Gradio server; local UI again showed exported data | [`evidence/04-docker.png`](evidence/04-docker.png), [`evidence/03-gradio.png`](evidence/03-gradio.png) |
| MCP protocol | MCP client discovered three tools and successfully invoked each; printed `MCP VALIDATION COMPLETE` | [`evidence/05-mcp.png`](evidence/05-mcp.png) |

**Interpretation:** These are controlled synthetic-data observations, not fleet-scale, enterprise security, performance, data-freshness, or production availability validations. The serverless Job has not been configured with a recurring schedule. Fine-grained Unity Catalog permissions were not tested. Some screenshots are cropped or have account identifiers obscured for safe public sharing; the measured results remain unchanged.

**Reproduction notes:** `notebooks/01_bronze_silver_gold.py` is the source export; the `.ipynb` is suitable for notebook import. Local Gradio/Docker/MCP require manually exported CSV files, which are excluded from this repository. See the main [README](../README.md).
