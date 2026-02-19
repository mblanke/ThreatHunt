"""Cross-hunt correlation engine — find IOC overlaps, timeline patterns, and shared TTPs.

Identifies connections between hunts by analyzing:
1. Shared IOC values across datasets
2. Overlapping time ranges and temporal proximity
3. Common MITRE ATT&CK techniques across hypotheses
4. Host-to-host lateral movement patterns
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow, Hunt, Hypothesis, EnrichmentResult

logger = logging.getLogger(__name__)


@dataclass
class IOCOverlap:
    """Shared IOC between two or more hunts/datasets."""
    ioc_value: str
    ioc_type: str
    datasets: list[dict] = field(default_factory=list)  # [{dataset_id, hunt_id, name}]
    hunt_ids: list[str] = field(default_factory=list)
    count: int = 0
    enrichment_verdict: str = ""


@dataclass
class TimeOverlap:
    """Overlapping time window between datasets."""
    dataset_a: dict = field(default_factory=dict)
    dataset_b: dict = field(default_factory=dict)
    overlap_start: str = ""
    overlap_end: str = ""
    overlap_hours: float = 0.0


@dataclass
class TechniqueOverlap:
    """Shared MITRE ATT&CK technique across hunts."""
    technique_id: str
    technique_name: str = ""
    hypotheses: list[dict] = field(default_factory=list)
    hunt_ids: list[str] = field(default_factory=list)


@dataclass
class CorrelationResult:
    """Complete correlation analysis result."""
    hunt_ids: list[str]
    ioc_overlaps: list[IOCOverlap] = field(default_factory=list)
    time_overlaps: list[TimeOverlap] = field(default_factory=list)
    technique_overlaps: list[TechniqueOverlap] = field(default_factory=list)
    host_overlaps: list[dict] = field(default_factory=list)
    summary: str = ""
    total_correlations: int = 0


class CorrelationEngine:
    """Engine for finding correlations across hunts and datasets."""

    async def correlate_hunts(
        self,
        hunt_ids: list[str],
        db: AsyncSession,
    ) -> CorrelationResult:
        """Run full correlation analysis across specified hunts."""
        result = CorrelationResult(hunt_ids=hunt_ids)

        # Run all correlation types
        result.ioc_overlaps = await self._find_ioc_overlaps(hunt_ids, db)
        result.time_overlaps = await self._find_time_overlaps(hunt_ids, db)
        result.technique_overlaps = await self._find_technique_overlaps(hunt_ids, db)
        result.host_overlaps = await self._find_host_overlaps(hunt_ids, db)

        result.total_correlations = (
            len(result.ioc_overlaps)
            + len(result.time_overlaps)
            + len(result.technique_overlaps)
            + len(result.host_overlaps)
        )

        result.summary = self._build_summary(result)
        return result

    async def correlate_all(self, db: AsyncSession) -> CorrelationResult:
        """Correlate across ALL hunts in the system."""
        stmt = select(Hunt.id)
        result = await db.execute(stmt)
        hunt_ids = [row[0] for row in result.fetchall()]

        if len(hunt_ids) < 2:
            return CorrelationResult(
                hunt_ids=hunt_ids,
                summary="Need at least 2 hunts for correlation analysis.",
            )

        return await self.correlate_hunts(hunt_ids, db)

    async def find_ioc_across_hunts(
        self,
        ioc_value: str,
        db: AsyncSession,
    ) -> list[dict]:
        """Find all occurrences of a specific IOC across all datasets/hunts."""
        # Search in dataset rows using JSON contains
        stmt = select(DatasetRow, Dataset).join(
            Dataset, DatasetRow.dataset_id == Dataset.id
        )
        result = await db.execute(stmt.limit(5000))
        rows = result.all()

        occurrences = []
        for row, dataset in rows:
            data = row.data or {}
            normalized = row.normalized_data or {}

            # Search both raw and normalized data
            for col, val in {**data, **normalized}.items():
                if str(val) == ioc_value:
                    occurrences.append({
                        "dataset_id": dataset.id,
                        "dataset_name": dataset.name,
                        "hunt_id": dataset.hunt_id,
                        "row_index": row.row_index,
                        "column": col,
                    })
                    break

        return occurrences

    # ── IOC overlap detection ─────────────────────────────────────────

    async def _find_ioc_overlaps(
        self,
        hunt_ids: list[str],
        db: AsyncSession,
    ) -> list[IOCOverlap]:
        """Find IOC values that appear in datasets from different hunts."""
        # Get all datasets for the specified hunts
        stmt = select(Dataset).where(Dataset.hunt_id.in_(hunt_ids))
        result = await db.execute(stmt)
        datasets = result.scalars().all()

        if len(datasets) < 2:
            return []

        # Build IOC → dataset mapping
        ioc_map: dict[str, list[dict]] = defaultdict(list)

        for dataset in datasets:
            if not dataset.ioc_columns:
                continue

            ioc_cols = list(dataset.ioc_columns.keys())
            rows_stmt = select(DatasetRow).where(
                DatasetRow.dataset_id == dataset.id
            ).limit(2000)
            rows_result = await db.execute(rows_stmt)
            rows = rows_result.scalars().all()

            for row in rows:
                data = row.data or {}
                for col in ioc_cols:
                    val = data.get(col, "")
                    if val and str(val).strip():
                        ioc_map[str(val).strip()].append({
                            "dataset_id": dataset.id,
                            "dataset_name": dataset.name,
                            "hunt_id": dataset.hunt_id,
                            "column": col,
                            "ioc_type": dataset.ioc_columns.get(col, "unknown"),
                        })

        # Filter to IOCs appearing in multiple hunts
        overlaps = []
        for ioc_value, appearances in ioc_map.items():
            hunt_set = set(a["hunt_id"] for a in appearances if a["hunt_id"])
            if len(hunt_set) >= 2:
                # Check for enrichment data
                enrich_stmt = select(EnrichmentResult).where(
                    EnrichmentResult.ioc_value == ioc_value
                ).limit(1)
                enrich_result = await db.execute(enrich_stmt)
                enrichment = enrich_result.scalar_one_or_none()

                overlaps.append(IOCOverlap(
                    ioc_value=ioc_value,
                    ioc_type=appearances[0].get("ioc_type", "unknown"),
                    datasets=appearances,
                    hunt_ids=sorted(hunt_set),
                    count=len(appearances),
                    enrichment_verdict=enrichment.verdict if enrichment else "",
                ))

        # Sort by count descending
        overlaps.sort(key=lambda x: x.count, reverse=True)
        return overlaps[:100]  # Limit results

    # ── Time window overlap ───────────────────────────────────────────

    async def _find_time_overlaps(
        self,
        hunt_ids: list[str],
        db: AsyncSession,
    ) -> list[TimeOverlap]:
        """Find datasets across hunts with overlapping time ranges."""
        stmt = select(Dataset).where(
            Dataset.hunt_id.in_(hunt_ids),
            Dataset.time_range_start.isnot(None),
            Dataset.time_range_end.isnot(None),
        )
        result = await db.execute(stmt)
        datasets = result.scalars().all()

        overlaps = []
        for i, ds_a in enumerate(datasets):
            for ds_b in datasets[i + 1:]:
                if ds_a.hunt_id == ds_b.hunt_id:
                    continue  # Same hunt, skip

                try:
                    a_start = datetime.fromisoformat(ds_a.time_range_start)
                    a_end = datetime.fromisoformat(ds_a.time_range_end)
                    b_start = datetime.fromisoformat(ds_b.time_range_start)
                    b_end = datetime.fromisoformat(ds_b.time_range_end)
                except (ValueError, TypeError):
                    continue

                # Check overlap
                overlap_start = max(a_start, b_start)
                overlap_end = min(a_end, b_end)

                if overlap_start < overlap_end:
                    hours = (overlap_end - overlap_start).total_seconds() / 3600
                    overlaps.append(TimeOverlap(
                        dataset_a={
                            "id": ds_a.id,
                            "name": ds_a.name,
                            "hunt_id": ds_a.hunt_id,
                            "start": ds_a.time_range_start,
                            "end": ds_a.time_range_end,
                        },
                        dataset_b={
                            "id": ds_b.id,
                            "name": ds_b.name,
                            "hunt_id": ds_b.hunt_id,
                            "start": ds_b.time_range_start,
                            "end": ds_b.time_range_end,
                        },
                        overlap_start=overlap_start.isoformat(),
                        overlap_end=overlap_end.isoformat(),
                        overlap_hours=round(hours, 2),
                    ))

        overlaps.sort(key=lambda x: x.overlap_hours, reverse=True)
        return overlaps[:50]

    # ── MITRE technique overlap ───────────────────────────────────────

    async def _find_technique_overlaps(
        self,
        hunt_ids: list[str],
        db: AsyncSession,
    ) -> list[TechniqueOverlap]:
        """Find MITRE ATT&CK techniques shared across hunts."""
        stmt = select(Hypothesis).where(
            Hypothesis.hunt_id.in_(hunt_ids),
            Hypothesis.mitre_technique.isnot(None),
        )
        result = await db.execute(stmt)
        hypotheses = result.scalars().all()

        technique_map: dict[str, list[dict]] = defaultdict(list)
        for hyp in hypotheses:
            technique = hyp.mitre_technique.strip()
            if technique:
                technique_map[technique].append({
                    "hypothesis_id": hyp.id,
                    "hypothesis_title": hyp.title,
                    "hunt_id": hyp.hunt_id,
                    "status": hyp.status,
                })

        overlaps = []
        for technique, hyps in technique_map.items():
            hunt_set = set(h["hunt_id"] for h in hyps if h["hunt_id"])
            if len(hunt_set) >= 2:
                overlaps.append(TechniqueOverlap(
                    technique_id=technique,
                    hypotheses=hyps,
                    hunt_ids=sorted(hunt_set),
                ))

        return overlaps

    # ── Host overlap ──────────────────────────────────────────────────

    async def _find_host_overlaps(
        self,
        hunt_ids: list[str],
        db: AsyncSession,
    ) -> list[dict]:
        """Find hostnames that appear in datasets from different hunts.

        Useful for detecting lateral movement patterns.
        """
        stmt = select(Dataset).where(Dataset.hunt_id.in_(hunt_ids))
        result = await db.execute(stmt)
        datasets = result.scalars().all()

        host_map: dict[str, list[dict]] = defaultdict(list)

        for dataset in datasets:
            norm_cols = dataset.normalized_columns or {}
            # Look for hostname columns
            hostname_cols = [
                orig for orig, canon in norm_cols.items()
                if canon in ("hostname", "host", "computer_name", "src_host", "dst_host")
            ]
            if not hostname_cols:
                continue

            rows_stmt = select(DatasetRow).where(
                DatasetRow.dataset_id == dataset.id
            ).limit(2000)
            rows_result = await db.execute(rows_stmt)
            rows = rows_result.scalars().all()

            for row in rows:
                data = row.data or {}
                for col in hostname_cols:
                    val = data.get(col, "")
                    if val and str(val).strip():
                        host_name = str(val).strip().upper()
                        host_map[host_name].append({
                            "dataset_id": dataset.id,
                            "dataset_name": dataset.name,
                            "hunt_id": dataset.hunt_id,
                        })

        # Filter to hosts appearing in multiple hunts
        overlaps = []
        for host, appearances in host_map.items():
            hunt_set = set(a["hunt_id"] for a in appearances if a["hunt_id"])
            if len(hunt_set) >= 2:
                overlaps.append({
                    "hostname": host,
                    "hunt_ids": sorted(hunt_set),
                    "dataset_count": len(appearances),
                    "datasets": appearances[:10],
                })

        overlaps.sort(key=lambda x: x["dataset_count"], reverse=True)
        return overlaps[:50]

    # ── Summary builder ───────────────────────────────────────────────

    def _build_summary(self, result: CorrelationResult) -> str:
        """Build a human-readable summary of correlations."""
        parts = [f"Correlation analysis across {len(result.hunt_ids)} hunts:"]

        if result.ioc_overlaps:
            malicious = [o for o in result.ioc_overlaps if o.enrichment_verdict == "malicious"]
            parts.append(
                f"  - {len(result.ioc_overlaps)} shared IOCs "
                f"({len(malicious)} flagged malicious)"
            )
        else:
            parts.append("  - No shared IOCs found")

        if result.time_overlaps:
            parts.append(f"  - {len(result.time_overlaps)} overlapping time windows")

        if result.technique_overlaps:
            parts.append(
                f"  - {len(result.technique_overlaps)} shared MITRE techniques"
            )

        if result.host_overlaps:
            parts.append(
                f"  - {len(result.host_overlaps)} hosts appearing in multiple hunts "
                "(potential lateral movement)"
            )

        if result.total_correlations == 0:
            parts.append("  No significant correlations detected.")

        return "\n".join(parts)


# Singleton
correlation_engine = CorrelationEngine()
