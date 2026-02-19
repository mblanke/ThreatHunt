"""Report generation — JSON, HTML, and CSV export for hunt investigations.

Generates comprehensive investigation reports including:
- Hunt metadata and status
- Dataset summaries with IOC counts
- Hypotheses and their evidence
- Annotations timeline
- Enrichment verdicts
- Agent conversation history
- Cross-hunt correlations
"""

import csv
import io
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Hunt, Dataset, DatasetRow, Hypothesis,
    Annotation, Conversation, Message, EnrichmentResult,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates exportable investigation reports."""

    async def generate_hunt_report(
        self,
        hunt_id: str,
        db: AsyncSession,
        format: str = "json",
        include_rows: bool = False,
        max_rows: int = 500,
    ) -> dict | str:
        """Generate a comprehensive report for a hunt investigation."""

        # Gather all hunt data
        report_data = await self._gather_hunt_data(
            hunt_id, db, include_rows=include_rows, max_rows=max_rows,
        )

        if not report_data:
            return {"error": "Hunt not found"}

        if format == "json":
            return report_data
        elif format == "html":
            return self._render_html(report_data)
        elif format == "csv":
            return self._render_csv(report_data)
        else:
            return report_data

    async def _gather_hunt_data(
        self,
        hunt_id: str,
        db: AsyncSession,
        include_rows: bool = False,
        max_rows: int = 500,
    ) -> dict | None:
        """Gather all data for a hunt report."""

        # Hunt metadata
        result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
        hunt = result.scalar_one_or_none()
        if not hunt:
            return None

        # Datasets
        ds_result = await db.execute(
            select(Dataset).where(Dataset.hunt_id == hunt_id)
        )
        datasets = ds_result.scalars().all()

        dataset_summaries = []
        all_iocs = {}
        for ds in datasets:
            summary = {
                "id": ds.id,
                "name": ds.name,
                "filename": ds.filename,
                "source_tool": ds.source_tool,
                "row_count": ds.row_count,
                "columns": list((ds.column_schema or {}).keys()),
                "ioc_columns": ds.ioc_columns or {},
                "time_range": {
                    "start": ds.time_range_start,
                    "end": ds.time_range_end,
                },
                "created_at": ds.created_at.isoformat(),
            }

            if include_rows:
                rows_result = await db.execute(
                    select(DatasetRow)
                    .where(DatasetRow.dataset_id == ds.id)
                    .order_by(DatasetRow.row_index)
                    .limit(max_rows)
                )
                rows = rows_result.scalars().all()
                summary["rows"] = [r.data for r in rows]

            dataset_summaries.append(summary)

            # Collect IOCs for enrichment lookup
            if ds.ioc_columns:
                all_iocs.update(ds.ioc_columns)

        # Hypotheses
        hyp_result = await db.execute(
            select(Hypothesis).where(Hypothesis.hunt_id == hunt_id)
        )
        hypotheses = hyp_result.scalars().all()

        hypotheses_data = [
            {
                "id": h.id,
                "title": h.title,
                "description": h.description,
                "mitre_technique": h.mitre_technique,
                "status": h.status,
                "evidence_row_ids": h.evidence_row_ids,
                "evidence_notes": h.evidence_notes,
                "created_at": h.created_at.isoformat(),
                "updated_at": h.updated_at.isoformat(),
            }
            for h in hypotheses
        ]

        # Annotations (across all datasets in this hunt)
        dataset_ids = [ds.id for ds in datasets]
        annotations_data = []
        if dataset_ids:
            ann_result = await db.execute(
                select(Annotation)
                .where(Annotation.dataset_id.in_(dataset_ids))
                .order_by(Annotation.created_at)
            )
            annotations = ann_result.scalars().all()
            annotations_data = [
                {
                    "id": a.id,
                    "dataset_id": a.dataset_id,
                    "row_id": a.row_id,
                    "text": a.text,
                    "severity": a.severity,
                    "tag": a.tag,
                    "created_at": a.created_at.isoformat(),
                }
                for a in annotations
            ]

        # Conversations
        conv_result = await db.execute(
            select(Conversation).where(Conversation.hunt_id == hunt_id)
        )
        conversations = conv_result.scalars().all()

        conversations_data = []
        for conv in conversations:
            msg_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
            )
            messages = msg_result.scalars().all()
            conversations_data.append({
                "id": conv.id,
                "title": conv.title,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "model_used": m.model_used,
                        "node_used": m.node_used,
                        "latency_ms": m.latency_ms,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages
                ],
            })

        # Enrichment results
        enrichment_data = []
        for ds in datasets:
            if not ds.ioc_columns:
                continue
            # Get unique enriched IOCs for this dataset
            for col_name in ds.ioc_columns.keys():
                enrich_result = await db.execute(
                    select(EnrichmentResult)
                    .where(EnrichmentResult.source.isnot(None))
                    .limit(100)
                )
                enrichments = enrich_result.scalars().all()
                for e in enrichments:
                    enrichment_data.append({
                        "ioc_value": e.ioc_value,
                        "ioc_type": e.ioc_type,
                        "source": e.source,
                        "verdict": e.verdict,
                        "score": e.score,
                        "tags": e.tags,
                        "country": e.country,
                    })
                break  # Only query once

        # Build report
        now = datetime.now(timezone.utc)
        return {
            "report_metadata": {
                "generated_at": now.isoformat(),
                "format_version": "1.0",
                "generator": "ThreatHunt Report Engine",
            },
            "hunt": {
                "id": hunt.id,
                "name": hunt.name,
                "description": hunt.description,
                "status": hunt.status,
                "created_at": hunt.created_at.isoformat(),
                "updated_at": hunt.updated_at.isoformat(),
            },
            "summary": {
                "dataset_count": len(datasets),
                "total_rows": sum(ds.row_count for ds in datasets),
                "hypothesis_count": len(hypotheses),
                "confirmed_hypotheses": len([h for h in hypotheses if h.status == "confirmed"]),
                "annotation_count": len(annotations_data),
                "critical_annotations": len([a for a in annotations_data if a["severity"] == "critical"]),
                "conversation_count": len(conversations_data),
                "enrichment_count": len(enrichment_data),
                "malicious_iocs": len([e for e in enrichment_data if e["verdict"] == "malicious"]),
            },
            "datasets": dataset_summaries,
            "hypotheses": hypotheses_data,
            "annotations": annotations_data,
            "conversations": conversations_data,
            "enrichments": enrichment_data[:100],
        }

    def _render_html(self, data: dict) -> str:
        """Render report as self-contained HTML."""
        hunt = data.get("hunt", {})
        summary = data.get("summary", {})
        hypotheses = data.get("hypotheses", [])
        annotations = data.get("annotations", [])
        datasets = data.get("datasets", [])
        enrichments = data.get("enrichments", [])
        meta = data.get("report_metadata", {})

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ThreatHunt Report: {hunt.get('name', 'Unknown')}</title>
<style>
  :root {{ --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #c9d1d9; --accent: #58a6ff; --red: #f85149; --orange: #d29922; --green: #3fb950; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: var(--accent); border-bottom: 2px solid var(--border); padding-bottom: 0.5rem; margin-bottom: 1rem; }}
  h2 {{ color: var(--accent); margin: 1.5rem 0 0.75rem; }}
  h3 {{ color: var(--text); margin: 1rem 0 0.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 0.75rem 0; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; }}
  .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; text-align: center; }}
  .stat .value {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .stat .label {{ font-size: 0.85rem; color: #8b949e; }}
  table {{ width: 100%; border-collapse: collapse; margin: 0.5rem 0; }}
  th, td {{ padding: 0.5rem 0.75rem; border: 1px solid var(--border); text-align: left; }}
  th {{ background: var(--surface); color: var(--accent); }}
  .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }}
  .badge-malicious {{ background: var(--red); color: white; }}
  .badge-suspicious {{ background: var(--orange); color: #000; }}
  .badge-clean {{ background: var(--green); color: #000; }}
  .badge-critical {{ background: var(--red); color: white; }}
  .badge-high {{ background: #da3633; color: white; }}
  .badge-medium {{ background: var(--orange); color: #000; }}
  .badge-confirmed {{ background: var(--green); color: #000; }}
  .badge-active {{ background: var(--accent); color: #000; }}
  .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); color: #8b949e; font-size: 0.85rem; }}
</style>
</head>
<body>
<div class="container">
<h1>🔍 ThreatHunt Report: {hunt.get('name', 'Untitled')}</h1>
<p><strong>Hunt ID:</strong> {hunt.get('id', '')}<br>
<strong>Status:</strong> {hunt.get('status', 'unknown')}<br>
<strong>Description:</strong> {hunt.get('description', 'N/A')}<br>
<strong>Created:</strong> {hunt.get('created_at', '')}</p>

<h2>Summary</h2>
<div class="stat-grid">
  <div class="stat"><div class="value">{summary.get('dataset_count', 0)}</div><div class="label">Datasets</div></div>
  <div class="stat"><div class="value">{summary.get('total_rows', 0):,}</div><div class="label">Total Rows</div></div>
  <div class="stat"><div class="value">{summary.get('hypothesis_count', 0)}</div><div class="label">Hypotheses</div></div>
  <div class="stat"><div class="value">{summary.get('confirmed_hypotheses', 0)}</div><div class="label">Confirmed</div></div>
  <div class="stat"><div class="value">{summary.get('annotation_count', 0)}</div><div class="label">Annotations</div></div>
  <div class="stat"><div class="value">{summary.get('malicious_iocs', 0)}</div><div class="label">Malicious IOCs</div></div>
</div>
"""

        # Hypotheses section
        if hypotheses:
            html += "<h2>Hypotheses</h2>\n"
            html += "<table><tr><th>Title</th><th>MITRE</th><th>Status</th><th>Description</th></tr>\n"
            for h in hypotheses:
                status_class = f"badge-{h['status']}" if h['status'] in ('confirmed', 'active') else ""
                html += (
                    f"<tr><td>{h['title']}</td>"
                    f"<td>{h.get('mitre_technique', 'N/A')}</td>"
                    f"<td><span class='badge {status_class}'>{h['status']}</span></td>"
                    f"<td>{h.get('description', '') or ''}</td></tr>\n"
                )
            html += "</table>\n"

        # Datasets section
        if datasets:
            html += "<h2>Datasets</h2>\n"
            for ds in datasets:
                html += f"""<div class="card">
<h3>{ds['name']} ({ds.get('filename', '')})</h3>
<p><strong>Source:</strong> {ds.get('source_tool', 'N/A')} |
<strong>Rows:</strong> {ds['row_count']:,} |
<strong>IOC Columns:</strong> {len(ds.get('ioc_columns', {}))} |
<strong>Time Range:</strong> {ds.get('time_range', {}).get('start', 'N/A')} to {ds.get('time_range', {}).get('end', 'N/A')}</p>
</div>\n"""

        # Annotations
        if annotations:
            critical = [a for a in annotations if a['severity'] in ('critical', 'high')]
            html += f"<h2>Annotations ({len(annotations)} total, {len(critical)} critical/high)</h2>\n"
            html += "<table><tr><th>Severity</th><th>Tag</th><th>Text</th><th>Created</th></tr>\n"
            for a in annotations[:50]:
                sev_class = f"badge-{a['severity']}" if a['severity'] in ('critical', 'high', 'medium') else ""
                html += (
                    f"<tr><td><span class='badge {sev_class}'>{a['severity']}</span></td>"
                    f"<td>{a.get('tag', 'N/A')}</td>"
                    f"<td>{a['text'][:200]}</td>"
                    f"<td>{a['created_at'][:19]}</td></tr>\n"
                )
            html += "</table>\n"

        # Enrichments
        if enrichments:
            malicious = [e for e in enrichments if e['verdict'] == 'malicious']
            html += f"<h2>IOC Enrichment ({len(enrichments)} results, {len(malicious)} malicious)</h2>\n"
            html += "<table><tr><th>IOC</th><th>Type</th><th>Source</th><th>Verdict</th><th>Score</th></tr>\n"
            for e in enrichments[:50]:
                verdict_class = f"badge-{e['verdict']}"
                html += (
                    f"<tr><td><code>{e['ioc_value']}</code></td>"
                    f"<td>{e['ioc_type']}</td>"
                    f"<td>{e['source']}</td>"
                    f"<td><span class='badge {verdict_class}'>{e['verdict']}</span></td>"
                    f"<td>{e.get('score', 0)}</td></tr>\n"
                )
            html += "</table>\n"

        html += f"""
<div class="footer">
  <p>Generated by ThreatHunt Report Engine | {meta.get('generated_at', '')[:19]}</p>
</div>
</div>
</body>
</html>"""

        return html

    def _render_csv(self, data: dict) -> str:
        """Render key report data as CSV."""
        output = io.StringIO()

        # Hypotheses sheet
        output.write("=== HYPOTHESES ===\n")
        writer = csv.writer(output)
        writer.writerow(["Title", "MITRE Technique", "Status", "Description", "Evidence Notes"])
        for h in data.get("hypotheses", []):
            writer.writerow([
                h.get("title", ""),
                h.get("mitre_technique", ""),
                h.get("status", ""),
                h.get("description", ""),
                h.get("evidence_notes", ""),
            ])

        output.write("\n=== ANNOTATIONS ===\n")
        writer.writerow(["Severity", "Tag", "Text", "Dataset ID", "Row ID", "Created"])
        for a in data.get("annotations", []):
            writer.writerow([
                a.get("severity", ""),
                a.get("tag", ""),
                a.get("text", ""),
                a.get("dataset_id", ""),
                a.get("row_id", ""),
                a.get("created_at", ""),
            ])

        output.write("\n=== ENRICHMENTS ===\n")
        writer.writerow(["IOC Value", "IOC Type", "Source", "Verdict", "Score", "Country"])
        for e in data.get("enrichments", []):
            writer.writerow([
                e.get("ioc_value", ""),
                e.get("ioc_type", ""),
                e.get("source", ""),
                e.get("verdict", ""),
                e.get("score", ""),
                e.get("country", ""),
            ])

        return output.getvalue()


# Singleton
report_generator = ReportGenerator()
