from pathlib import Path

p = Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/scanner.py')
text = p.read_text(encoding='utf-8')
new_text = '''"""AUP Keyword Scanner  searches dataset rows, hunts, annotations, and
messages for keyword matches.

Scanning is done in Python (not SQL LIKE on JSON columns) for portability
across SQLite / PostgreSQL and to provide per-cell match context.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KeywordTheme,
    DatasetRow,
    Dataset,
    Hunt,
    Annotation,
    Message,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


@dataclass
class ScanHit:
    theme_name: str
    theme_color: str
    keyword: str
    source_type: str       # dataset_row | hunt | annotation | message
    source_id: str | int
    field: str
    matched_value: str
    row_index: int | None = None
    dataset_name: str | None = None


@dataclass
class ScanResult:
    total_hits: int = 0
    hits: list[ScanHit] = field(default_factory=list)
    themes_scanned: int = 0
    keywords_scanned: int = 0
    rows_scanned: int = 0


@dataclass
class KeywordScanCacheEntry:
    dataset_id: str
    result: dict
    built_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KeywordScanCache:
    """In-memory per-dataset cache for dataset-only keyword scans.

    This enables fast-path reads when users run AUP scans against datasets that
    were already scanned during upload pipeline processing.
    """

    def __init__(self):
        self._entries: dict[str, KeywordScanCacheEntry] = {}

    def put(self, dataset_id: str, result: dict):
        self._entries[dataset_id] = KeywordScanCacheEntry(dataset_id=dataset_id, result=result)

    def get(self, dataset_id: str) -> KeywordScanCacheEntry | None:
        return self._entries.get(dataset_id)

    def invalidate_dataset(self, dataset_id: str):
        self._entries.pop(dataset_id, None)

    def clear(self):
        self._entries.clear()


keyword_scan_cache = KeywordScanCache()


class KeywordScanner:
    """Scans multiple data sources for keyword/regex matches."""

    def __init__(self, db: AsyncSession):
        self.db = db

    #  Public API 

    async def scan(
        self,
        dataset_ids: list[str] | None = None,
        theme_ids: list[str] | None = None,
        scan_hunts: bool = False,
        scan_annotations: bool = False,
        scan_messages: bool = False,
    ) -> dict:
        """Run a full AUP scan and return dict matching ScanResponse."""
        # Load themes + keywords
        themes = await self._load_themes(theme_ids)
        if not themes:
            return ScanResult().__dict__

        # Pre-compile patterns per theme
        patterns = self._compile_patterns(themes)
        result = ScanResult(
            themes_scanned=len(themes),
            keywords_scanned=sum(len(kws) for kws in patterns.values()),
        )

        # Scan dataset rows
        await self._scan_datasets(patterns, result, dataset_ids)

        # Scan hunts
        if scan_hunts:
            await self._scan_hunts(patterns, result)

        # Scan annotations
        if scan_annotations:
            await self._scan_annotations(patterns, result)

        # Scan messages
        if scan_messages:
            await self._scan_messages(patterns, result)

        result.total_hits = len(result.hits)
        return {
            "total_hits": result.total_hits,
            "hits": [h.__dict__ for h in result.hits],
            "themes_scanned": result.themes_scanned,
            "keywords_scanned": result.keywords_scanned,
            "rows_scanned": result.rows_scanned,
        }

    #  Internal 

    async def _load_themes(self, theme_ids: list[str] | None) -> list[KeywordTheme]:
        q = select(KeywordTheme).where(KeywordTheme.enabled == True)  # noqa: E712
        if theme_ids:
            q = q.where(KeywordTheme.id.in_(theme_ids))
        result = await self.db.execute(q)
        return list(result.scalars().all())

    def _compile_patterns(
        self, themes: list[KeywordTheme]
    ) -> dict[tuple[str, str, str], list[tuple[str, re.Pattern]]]:
        """Returns {(theme_id, theme_name, theme_color): [(keyword_value, compiled_pattern), ...]}"""
        patterns: dict[tuple[str, str, str], list[tuple[str, re.Pattern]]] = {}
        for theme in themes:
            key = (theme.id, theme.name, theme.color)
            compiled = []
            for kw in theme.keywords:
                try:
                    if kw.is_regex:
                        pat = re.compile(kw.value, re.IGNORECASE)
                    else:
                        pat = re.compile(re.escape(kw.value), re.IGNORECASE)
                    compiled.append((kw.value, pat))
                except re.error:
                    logger.warning("Invalid regex pattern '%s' in theme '%s', skipping",
                                   kw.value, theme.name)
            patterns[key] = compiled
        return patterns

    def _match_text(
        self,
        text: str,
        patterns: dict,
        source_type: str,
        source_id: str | int,
        field_name: str,
        hits: list[ScanHit],
        row_index: int | None = None,
        dataset_name: str | None = None,
    ) -> None:
        """Check text against all compiled patterns, append hits."""
        if not text:
            return
        for (theme_id, theme_name, theme_color), keyword_patterns in patterns.items():
            for kw_value, pat in keyword_patterns:
                if pat.search(text):
                    matched_preview = text[:200] + ("" if len(text) > 200 else "")
                    hits.append(ScanHit(
                        theme_name=theme_name,
                        theme_color=theme_color,
                        keyword=kw_value,
                        source_type=source_type,
                        source_id=source_id,
                        field=field_name,
                        matched_value=matched_preview,
                        row_index=row_index,
                        dataset_name=dataset_name,
                    ))

    async def _scan_datasets(
        self, patterns: dict, result: ScanResult, dataset_ids: list[str] | None
    ) -> None:
        """Scan dataset rows in batches."""
        ds_q = select(Dataset.id, Dataset.name)
        if dataset_ids:
            ds_q = ds_q.where(Dataset.id.in_(dataset_ids))
        ds_result = await self.db.execute(ds_q)
        ds_map = {r[0]: r[1] for r in ds_result.fetchall()}

        if not ds_map:
            return

        offset = 0
        row_q_base = select(DatasetRow).where(
            DatasetRow.dataset_id.in_(list(ds_map.keys()))
        ).order_by(DatasetRow.id)

        while True:
            rows_result = await self.db.execute(
                row_q_base.offset(offset).limit(BATCH_SIZE)
            )
            rows = rows_result.scalars().all()
            if not rows:
                break

            for row in rows:
                result.rows_scanned += 1
                data = row.data or {}
                for col_name, cell_value in data.items():
                    if cell_value is None:
                        continue
                    text = str(cell_value)
                    self._match_text(
                        text, patterns, "dataset_row", row.id,
                        col_name, result.hits,
                        row_index=row.row_index,
                        dataset_name=ds_map.get(row.dataset_id),
                    )

            offset += BATCH_SIZE
            import asyncio
            await asyncio.sleep(0)
            if len(rows) < BATCH_SIZE:
                break

    async def _scan_hunts(self, patterns: dict, result: ScanResult) -> None:
        """Scan hunt names and descriptions."""
        hunts_result = await self.db.execute(select(Hunt))
        for hunt in hunts_result.scalars().all():
            self._match_text(hunt.name, patterns, "hunt", hunt.id, "name", result.hits)
            if hunt.description:
                self._match_text(hunt.description, patterns, "hunt", hunt.id, "description", result.hits)

    async def _scan_annotations(self, patterns: dict, result: ScanResult) -> None:
        """Scan annotation text."""
        ann_result = await self.db.execute(select(Annotation))
        for ann in ann_result.scalars().all():
            self._match_text(ann.text, patterns, "annotation", ann.id, "text", result.hits)

    async def _scan_messages(self, patterns: dict, result: ScanResult) -> None:
        """Scan conversation messages (user messages only)."""
        msg_result = await self.db.execute(
            select(Message).where(Message.role == "user")
        )
        for msg in msg_result.scalars().all():
            self._match_text(msg.content, patterns, "message", msg.id, "content", result.hits)
'''

p.write_text(new_text, encoding='utf-8')
print('updated scanner.py')
