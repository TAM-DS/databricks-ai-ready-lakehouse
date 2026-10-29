# Publish this repository to GitHub

GitHub destination: **`TAM-DS/databricks-ai-ready-lakehouse`**

**Suggested public description:** Databricks Spark + Delta Lake Bronze/Silver/Gold with verified Unity Catalog lineage, Dockerized Gradio, and read-only MCP evidence.

## Before publishing

1. Review the [validation evidence](docs/VALIDATION.md) and [security scope](docs/SECURITY.md).
2. Do **not** copy `gold.csv`, `quarantine_reasons.csv`, `.env`, personal tokens, or proprietary data into the project before publication. The intended local `data/*.csv` paths are ignored by Git, and the helper additionally refuses any tracked CSV files.
3. In GitHub, click **New repository**, owner `TAM-DS`, name `databricks-ai-ready-lakehouse`, visibility **Public**. Leave **Add a README**, **Add .gitignore**, and **Choose a license** all unchecked because this package already contains those files.
4. On your Mac, unzip the release package and open Terminal in the extracted `databricks-ai-ready-lakehouse` folder. Execute:

```bash
bash scripts/publish_to_github.sh
```

The helper initializes the local Git repository, shows which source files will be committed, and pushes to the new public GitHub repository. **No force-push is used**. It requires an existing Git authentication setup and an empty new destination repository; if authentication fails, it will stop without retrying destructively.

## After publishing

- Open `https://github.com/TAM-DS/databricks-ai-ready-lakehouse` and verify the five evidence screenshots, architecture diagram, code, and notebook display.
- In **Settings / General**, optionally set the repository description above; add the topics: `databricks`, `pyspark`, `delta-lake`, `unity-catalog`, `python`, `sql`, `docker`, `gradio`, `mcp`, `data-quality`.
- Check the **Actions** tab for the offline test workflow. CI success is not evidence that Databricks, Docker, or MCP executed in GitHub Actions; those validations were performed on October 29, 2026 and documented separately.
- Preserve the original `TAM-DS/ai-ready-data-platform` repository unchanged.
