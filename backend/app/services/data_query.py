"""Natural-language data query service with SSE streaming.

Lets analysts ask questions about dataset rows in plain English.
Routes to fast model (Roadrunner) for quick queries, heavy model (Wile)
for deep analysis.  Supports streaming via OllamaProvider.generate_stream().
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_factory
from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)

# Maximum rows to include in context window
MAX_CONTEXT_ROWS = 60
MAX_ROW_TEXT_CHARS = 300


def _rows_to_text(rows: list[dict], columns: list[str]) -> str:
    """Convert dataset rows to a compact text table for the LLM context."""
    if not rows:
        return "(no rows)"
    # Header
    header = " | ".join(columns[:20])  # cap columns to avoid overflow
    lines = [header, "-" * min(len(header), 120)]
    for row in rows[:MAX_CONTEXT_ROWS]:
        vals = []
        for c in columns[:20]:
            v = str(row.get(c, ""))
            if len(v) > 80:
                v = v[:77] + "..."
            vals.append(v)
        line = " | ".join(vals)
        if len(line) > MAX_ROW_TEXT_CHARS:
            line = line[:MAX_ROW_TEXT_CHARS] + "..."
        lines.append(line)
    return "\n".join(lines)


QUERY_SYSTEM_PROMPT = """You are a cybersecurity data analyst assistant for ThreatHunt.
You have been given a sample of rows from a forensic artifact dataset (Velociraptor, etc.).

Your job:
- Answer the analyst's question about this data accurately and concisely
- Point out suspicious patterns, anomalies, or indicators of compromise
- Reference MITRE ATT&CK techniques when relevant
- Suggest follow-up queries or pivots
- If you cannot answer from the data provided, say so clearly

Rules:
- Be factual - only reference data you can see
- Use forensic terminology appropriate for SOC/DFIR analysts
- Format your answer with clear sections using markdown
- If the data seems benign, say so - do not fabricate threats"""


async def _load_dataset_context(
    dataset_id: str,
    db: AsyncSession,
    sample_size: int = MAX_CONTEXT_ROWS,
) -> tuple[dict, str, int]:
    """Load dataset metadata + sample rows for context.

    Returns (metadata_dict, rows_text, total_row_count).
    """
    ds = await db.get(Dataset, dataset_id)
    if not ds:
        raise ValueError(f"Dataset {dataset_id} not found")

    # Get total count
    count_q = await db.execute(
        select(func.count()).where(DatasetRow.dataset_id == dataset_id)
    )
    total = count_q.scalar() or 0

    # Sample rows - get first batch + some from the middle
    half = sample_size // 2
    result = await db.execute(
        select(DatasetRow)
        .where(DatasetRow.dataset_id == dataset_id)
        .order_by(DatasetRow.row_index)
        .limit(half)
    )
    first_rows = result.scalars().all()

    # If dataset is large, also sample from the middle
    middle_rows = []
    if total > sample_size:
        mid_offset = total // 2
        result2 = await db.execute(
            select(DatasetRow)
            .where(DatasetRow.dataset_id == dataset_id)
            .order_by(DatasetRow.row_index)
            .offset(mid_offset)
            .limit(sample_size - half)
        )
        middle_rows = result2.scalars().all()
    else:
        result2 = await db.execute(
            select(DatasetRow)
            .where(DatasetRow.dataset_id == dataset_id)
            .order_by(DatasetRow.row_index)
            .offset(half)
            .limit(sample_size - half)
        )
        middle_rows = result2.scalars().all()

    all_rows = first_rows + middle_rows
    row_dicts = [r.data if isinstance(r.data, dict) else {} for r in all_rows]

    columns = list(ds.column_schema.keys()) if ds.column_schema else []
    if not columns and row_dicts:
        columns = list(row_dicts[0].keys())

    rows_text = _rows_to_text(row_dicts, columns)

    metadata = {
        "name": ds.name,
        "filename": ds.filename,
        "source_tool": ds.source_tool,
        "artifact_type": getattr(ds, "artifact_type", None),
        "row_count": total,
        "columns": columns[:30],
        "sample_rows_shown": len(all_rows),
    }
    return metadata, rows_text, total


async def query_dataset(
    dataset_id: str,
    question: str,
    mode: str = "quick",
) -> str:
    """Non-streaming query: returns full answer text."""
    from app.agents.providers_v2 import OllamaProvider, Node

    async with async_session_factory() as db:
        meta, rows_text, total = await _load_dataset_context(dataset_id, db)

    prompt = _build_prompt(question, meta, rows_text, total)

    if mode == "deep":
        provider = OllamaProvider(settings.DEFAULT_HEAVY_MODEL, Node.WILE)
        max_tokens = 4096
    else:
        provider = OllamaProvider(settings.DEFAULT_FAST_MODEL, Node.ROADRUNNER)
        max_tokens = 2048

    result = await provider.generate(
        prompt,
        system=QUERY_SYSTEM_PROMPT,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return result.get("response", "No response generated.")


async def query_dataset_stream(
    dataset_id: str,
    question: str,
    mode: str = "quick",
) -> AsyncIterator[str]:
    """Streaming query: yields SSE-formatted events."""
    from app.agents.providers_v2 import OllamaProvider, Node

    start = time.monotonic()

    # Send initial metadata event
    yield f"data: {json.dumps({'type': 'status', 'message': 'Loading dataset...'})}\n\n"

    async with async_session_factory() as db:
        meta, rows_text, total = await _load_dataset_context(dataset_id, db)

    yield f"data: {json.dumps({'type': 'metadata', 'dataset': meta})}\n\n"
    yield f"data: {json.dumps({'type': 'status', 'message': f'Querying LLM ({mode} mode)...'})}\n\n"

    prompt = _build_prompt(question, meta, rows_text, total)

    if mode == "deep":
        provider = OllamaProvider(settings.DEFAULT_HEAVY_MODEL, Node.WILE)
        max_tokens = 4096
        model_name = settings.DEFAULT_HEAVY_MODEL
        node_name = "wile"
    else:
        provider = OllamaProvider(settings.DEFAULT_FAST_MODEL, Node.ROADRUNNER)
        max_tokens = 2048
        model_name = settings.DEFAULT_FAST_MODEL
        node_name = "roadrunner"

    # Stream tokens
    token_count = 0
    try:
        async for token in provider.generate_stream(
            prompt,
            system=QUERY_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=0.3,
        ):
            token_count += 1
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    elapsed_ms = int((time.monotonic() - start) * 1000)
    yield f"data: {json.dumps({'type': 'done', 'tokens': token_count, 'elapsed_ms': elapsed_ms, 'model': model_name, 'node': node_name})}\n\n"


def _build_prompt(question: str, meta: dict, rows_text: str, total: int) -> str:
    """Construct the full prompt with data context."""
    parts = [
        f"## Dataset: {meta['name']}",
        f"- Source: {meta.get('source_tool', 'unknown')}",
        f"- Artifact type: {meta.get('artifact_type', 'unknown')}",
        f"- Total rows: {total}",
        f"- Columns: {', '.join(meta.get('columns', []))}",
        f"- Showing {meta['sample_rows_shown']} sample rows below",
        "",
        "## Sample Data",
        "```",
        rows_text,
        "```",
        "",
        f"## Analyst Question",
        question,
    ]
    return "\n".join(parts)