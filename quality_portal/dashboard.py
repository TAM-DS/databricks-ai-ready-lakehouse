"""Local read-only Gradio quality evidence dashboard."""
from __future__ import annotations

import os
from pathlib import Path
from .core import read_snapshot, SnapshotError, GOLD_COLUMNS, REASONS_COLUMNS

DATA_DIR = Path(os.environ.get("QUALITY_DATA_DIR", "data"))


def render():
    try:
        snapshot = read_snapshot(DATA_DIR)
    except SnapshotError as exc:
        return (
            f"### No verified export loaded yet\n\n{exc}\n\n"
            "Download **both** final notebook tables as CSV, rename them `gold.csv` "
            "and `quarantine_reasons.csv`, and place them in the `data/` folder. "
            "Then click **Reload exported evidence**.",
            [], [],
        )
    t = snapshot.totals
    summary = (
        "### Exported data-quality evidence\n\n"
        f"**Source:** {t['source_rows']:,}  |  **Accepted:** {t['accepted_rows']:,}  |  "
        f"**Quarantined:** {t['quarantined_rows']:,}  |  **Gold segments:** {t['gold_segments']:,}\n\n"
        f"**Pass rate for declared rules:** {t['declared_rule_pass_pct']:.2f}%  |  "
        f"**Delayed shipments:** {t['delayed_shipments']:,}  |  "
        f"**Modeled inventory value:** ${t['modeled_inventory_value_usd']:,.2f}\n\n"
        "*These figures are calculated from downloaded synthetic Databricks results; "
        "they are not a live connection, production KPI, or enterprise data-readiness certification.*"
    )
    gold_table = [[row[k] for k in GOLD_COLUMNS] for row in snapshot.gold]
    reason_table = [[row[k] for k in REASONS_COLUMNS] for row in snapshot.quarantine_reasons]
    return summary, gold_table, reason_table


def create_app():
    import gradio as gr
    with gr.Blocks(title="AI-Ready Data Platform | Quality Evidence") as demo:
        gr.Markdown("# AI-Ready Data Platform  ·  Data Quality Control Tower")
        gr.Markdown(
            "**Read-only local audit view** · Databricks → Delta Lake → Unity Catalog → "
            "CSV export → Gradio.  "
            "**No direct cloud connection. No AI inference. No write access.**"
        )
        summary = gr.Markdown()
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Gold: accepted synthetic operational segments")
                gold = gr.Dataframe(headers=list(GOLD_COLUMNS), interactive=False, wrap=True)
            with gr.Column(scale=1):
                gr.Markdown("### Quarantined: declared rejection reasons")
                reasons = gr.Dataframe(headers=list(REASONS_COLUMNS), interactive=False)
        reload_button = gr.Button("Reload exported evidence")
        demo.load(render, outputs=[summary, gold, reasons])
        reload_button.click(render, outputs=[summary, gold, reasons])
        gr.Markdown(
            "*Governance boundary:* The CSV snapshot is an offline export. "
            "Unity Catalog permissions and lineage **do not transfer** to this local copy. "
            "Distribution of exported data must be separately controlled."
        )
    return demo


def main():
    app = create_app()
    app.launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        share=False,
        show_error=False,
    )


if __name__ == "__main__":
    main()
