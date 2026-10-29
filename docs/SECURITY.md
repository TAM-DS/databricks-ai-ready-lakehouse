# Security and operational scope

The pipeline deliberately uses only generated synthetic records, makes no external LLM calls, and writes only to a dedicated demo schema in the current Unity Catalog catalog. Running the notebook **replaces four demo tables** and is therefore not appropriate for a shared, production dataset.

The local application is **not** a live Databricks integration. Do not copy private or regulated data into `data/`. Git ignores local CSV exports. No secrets, user data, or Databricks tokens are needed to run the Gradio/Docker/MCP layer.

The local Docker Compose configuration binds the host port to `127.0.0.1`, runs as a non-root service user, mounts the source data read-only, uses a read-only root filesystem with a temporary filesystem for `/tmp`, and sets `no-new-privileges`. These are hardening choices, not a comprehensive security review. Docker's internal app bind to `0.0.0.0` is only inside the container; the Compose host mapping is loopback-only.

The MCP server uses stdio and exactly three named read-only tools. There is no arbitrary SQL interface, shell tool, mutation capability, or cloud-account access. The code reads only two expected filenames from a configured local data folder; it is **not** designed as a hostile-multiuser sandbox.

Unity Catalog lineage was observed, but **table-level lineage is not proof of fine-grained authorization, retention guarantees, column masking, or audit-log completeness**. A CSV export is no longer governed by its source table's Unity Catalog permissions. The dashboard does not authorize production releases.

Run repeated data-quality tests, dependency checks, and security reviews before any non-demo deployment. Reproducing with live data is outside the project's scope.
