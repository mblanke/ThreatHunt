"""API routes for IOC enrichment."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.enrichment import (
    enrichment_engine,
    IOCType,
    Verdict,
    EnrichmentResultData,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


# ── Models ────────────────────────────────────────────────────────────


class EnrichIOCRequest(BaseModel):
    ioc_value: str = Field(..., max_length=2048, description="IOC value to enrich")
    ioc_type: str = Field(..., description="IOC type: ip, domain, hash_md5, hash_sha1, hash_sha256, url")
    skip_cache: bool = False


class EnrichBatchRequest(BaseModel):
    iocs: list[dict] = Field(
        ...,
        description="List of {value, type} pairs",
        max_length=50,
    )


class EnrichmentResultResponse(BaseModel):
    ioc_value: str
    ioc_type: str
    source: str
    verdict: str
    score: float
    tags: list[str] = []
    country: str = ""
    asn: str = ""
    org: str = ""
    last_seen: str = ""
    raw_data: dict = {}
    error: str = ""
    latency_ms: int = 0


class EnrichIOCResponse(BaseModel):
    ioc_value: str
    ioc_type: str
    results: list[EnrichmentResultResponse]
    overall_verdict: str
    overall_score: float


class EnrichBatchResponse(BaseModel):
    results: dict[str, list[EnrichmentResultResponse]]
    total_enriched: int


def _to_response(r: EnrichmentResultData) -> EnrichmentResultResponse:
    return EnrichmentResultResponse(
        ioc_value=r.ioc_value,
        ioc_type=r.ioc_type.value,
        source=r.source,
        verdict=r.verdict.value,
        score=r.score,
        tags=r.tags,
        country=r.country,
        asn=r.asn,
        org=r.org,
        last_seen=r.last_seen,
        raw_data=r.raw_data,
        error=r.error,
        latency_ms=r.latency_ms,
    )


def _compute_overall(results: list[EnrichmentResultData]) -> tuple[str, float]:
    """Compute overall verdict from multiple provider results."""
    if not results:
        return Verdict.UNKNOWN.value, 0.0

    verdicts = [r.verdict for r in results if r.verdict != Verdict.ERROR]
    if not verdicts:
        return Verdict.ERROR.value, 0.0

    if Verdict.MALICIOUS in verdicts:
        return Verdict.MALICIOUS.value, max(r.score for r in results)
    elif Verdict.SUSPICIOUS in verdicts:
        return Verdict.SUSPICIOUS.value, max(r.score for r in results)
    elif Verdict.CLEAN in verdicts:
        return Verdict.CLEAN.value, 0.0
    return Verdict.UNKNOWN.value, 0.0


# ── Routes ────────────────────────────────────────────────────────────


@router.post(
    "/ioc",
    response_model=EnrichIOCResponse,
    summary="Enrich a single IOC",
    description="Query all configured providers for an IOC (IP, hash, domain, URL).",
)
async def enrich_ioc(
    body: EnrichIOCRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        ioc_type = IOCType(body.ioc_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IOC type: {body.ioc_type}. Valid: {[t.value for t in IOCType]}",
        )

    results = await enrichment_engine.enrich_ioc(
        body.ioc_value, ioc_type, db=db, skip_cache=body.skip_cache,
    )

    overall_verdict, overall_score = _compute_overall(results)

    return EnrichIOCResponse(
        ioc_value=body.ioc_value,
        ioc_type=body.ioc_type,
        results=[_to_response(r) for r in results],
        overall_verdict=overall_verdict,
        overall_score=overall_score,
    )


@router.post(
    "/batch",
    response_model=EnrichBatchResponse,
    summary="Enrich a batch of IOCs",
    description="Enrich up to 50 IOCs at once across all providers.",
)
async def enrich_batch(
    body: EnrichBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    iocs = []
    for item in body.iocs:
        try:
            ioc_type = IOCType(item["type"])
            iocs.append((item["value"], ioc_type))
        except (KeyError, ValueError):
            continue

    if not iocs:
        raise HTTPException(status_code=400, detail="No valid IOCs provided")

    all_results = await enrichment_engine.enrich_batch(iocs, db=db)

    return EnrichBatchResponse(
        results={
            k: [_to_response(r) for r in v]
            for k, v in all_results.items()
        },
        total_enriched=len(all_results),
    )


@router.post(
    "/dataset/{dataset_id}",
    summary="Auto-enrich IOCs in a dataset",
    description="Automatically extract and enrich IOCs from a dataset's IOC columns.",
)
async def enrich_dataset(
    dataset_id: str,
    max_iocs: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    from app.db.repositories.datasets import DatasetRepository

    repo = DatasetRepository(db)
    dataset = await repo.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.ioc_columns:
        return {"message": "No IOC columns detected in this dataset", "results": {}}

    rows = await repo.get_rows(dataset_id, limit=1000)
    row_data = [r.data for r in rows]

    all_results = await enrichment_engine.enrich_dataset_iocs(
        rows=row_data,
        ioc_columns=dataset.ioc_columns,
        db=db,
        max_iocs=max_iocs,
    )

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        "ioc_columns": dataset.ioc_columns,
        "results": {
            k: [_to_response(r) for r in v]
            for k, v in all_results.items()
        },
        "total_enriched": len(all_results),
    }


@router.get(
    "/status",
    summary="Enrichment engine status",
    description="Check which providers are configured and available.",
)
async def enrichment_status():
    return enrichment_engine.status()
