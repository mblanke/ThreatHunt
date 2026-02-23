"""API routes for dataset upload, listing, and management."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db.models import ProcessingTask
from app.db.repositories.datasets import DatasetRepository
from app.services.csv_parser import parse_csv_bytes, infer_column_types
from app.services.normalizer import (
    normalize_columns,
    normalize_rows,
    detect_ioc_columns,
    detect_time_range,
)
from app.services.artifact_classifier import classify_artifact, get_artifact_category

logger = logging.getLogger(__name__)

from app.services.job_queue import job_queue, JobType
from app.services.host_inventory import inventory_cache
from app.services.scanner import keyword_scan_cache

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt"}


# -- Response models --


class DatasetSummary(BaseModel):
    id: str
    name: str
    filename: str
    source_tool: str | None = None
    row_count: int
    column_schema: dict | None = None
    normalized_columns: dict | None = None
    ioc_columns: dict | None = None
    file_size_bytes: int
    encoding: str | None = None
    delimiter: str | None = None
    time_range_start: str | None = None
    time_range_end: str | None = None
    artifact_type: str | None = None
    processing_status: str | None = None
    hunt_id: str | None = None
    created_at: str


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]
    total: int


class RowsResponse(BaseModel):
    rows: list[dict]
    total: int
    offset: int
    limit: int


class UploadResponse(BaseModel):
    id: str
    name: str
    row_count: int
    columns: list[str]
    column_types: dict
    normalized_columns: dict
    ioc_columns: dict
    artifact_type: str | None = None
    processing_status: str
    jobs_queued: list[str]
    message: str


# -- Routes --


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a CSV dataset",
    description="Upload a CSV/TSV file for analysis. The file is parsed, columns normalized, "
    "IOCs auto-detected, artifact type classified, and all processing jobs queued automatically.",
)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Query(None, description="Display name for the dataset"),
    source_tool: str | None = Query(None, description="Source tool (e.g., velociraptor)"),
    hunt_id: str | None = Query(None, description="Hunt ID to associate with"),
    db: AsyncSession = Depends(get_db),
):
    """Upload and parse a CSV dataset, then trigger full processing pipeline."""
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file bytes
    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # Parse CSV
    try:
        rows, metadata = parse_csv_bytes(raw_bytes)
    except Exception as e:
        logger.error(f"CSV parse error: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse CSV: {str(e)}. Check encoding and format.",
        )

    if not rows:
        raise HTTPException(status_code=422, detail="CSV file contains no data rows")

    columns: list[str] = metadata["columns"]
    column_types: dict = metadata["column_types"]

    # Normalize columns
    column_mapping = normalize_columns(columns)
    normalized = normalize_rows(rows, column_mapping)

    # Detect IOCs
    ioc_columns = detect_ioc_columns(columns, column_types, column_mapping)

    # Detect time range
    time_start, time_end = detect_time_range(rows, column_mapping)

    # Classify artifact type from column headers
    artifact_type = classify_artifact(columns)
    artifact_category = get_artifact_category(artifact_type)
    logger.info(f"Artifact classification: {artifact_type} (category: {artifact_category})")

    # Store in DB with processing_status = "processing"
    repo = DatasetRepository(db)
    dataset = await repo.create_dataset(
        name=name or Path(file.filename).stem,
        filename=file.filename,
        source_tool=source_tool,
        row_count=len(rows),
        column_schema=column_types,
        normalized_columns=column_mapping,
        ioc_columns=ioc_columns,
        file_size_bytes=len(raw_bytes),
        encoding=metadata["encoding"],
        delimiter=metadata["delimiter"],
        time_range_start=time_start,
        time_range_end=time_end,
        hunt_id=hunt_id,
        artifact_type=artifact_type,
        processing_status="processing",
    )

    await repo.bulk_insert_rows(
        dataset_id=dataset.id,
        rows=rows,
        normalized_rows=normalized,
    )

    logger.info(
        f"Uploaded dataset '{dataset.name}': {len(rows)} rows, "
        f"{len(columns)} columns, {len(ioc_columns)} IOC columns, "
        f"artifact={artifact_type}"
    )

    # -- Queue full processing pipeline --
    jobs_queued = []

    task_rows: list[ProcessingTask] = []

    # 1. AI Triage (chains to HOST_PROFILE automatically on completion)
    triage_job = job_queue.submit(JobType.TRIAGE, dataset_id=dataset.id)
    jobs_queued.append("triage")
    task_rows.append(ProcessingTask(
        hunt_id=hunt_id,
        dataset_id=dataset.id,
        job_id=triage_job.id,
        stage="triage",
        status="queued",
        progress=0.0,
        message="Queued",
    ))

    # 2. Anomaly detection (embedding-based outlier detection)
    anomaly_job = job_queue.submit(JobType.ANOMALY, dataset_id=dataset.id)
    jobs_queued.append("anomaly")
    task_rows.append(ProcessingTask(
        hunt_id=hunt_id,
        dataset_id=dataset.id,
        job_id=anomaly_job.id,
        stage="anomaly",
        status="queued",
        progress=0.0,
        message="Queued",
    ))

    # 3. AUP keyword scan
    kw_job = job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=dataset.id)
    jobs_queued.append("keyword_scan")
    task_rows.append(ProcessingTask(
        hunt_id=hunt_id,
        dataset_id=dataset.id,
        job_id=kw_job.id,
        stage="keyword_scan",
        status="queued",
        progress=0.0,
        message="Queued",
    ))

    # 4. IOC extraction
    ioc_job = job_queue.submit(JobType.IOC_EXTRACT, dataset_id=dataset.id)
    jobs_queued.append("ioc_extract")
    task_rows.append(ProcessingTask(
        hunt_id=hunt_id,
        dataset_id=dataset.id,
        job_id=ioc_job.id,
        stage="ioc_extract",
        status="queued",
        progress=0.0,
        message="Queued",
    ))

    # 5. Host inventory (network map) - requires hunt_id
    if hunt_id:
        inventory_cache.invalidate(hunt_id)
        inv_job = job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)
        jobs_queued.append("host_inventory")
        task_rows.append(ProcessingTask(
            hunt_id=hunt_id,
            dataset_id=dataset.id,
            job_id=inv_job.id,
            stage="host_inventory",
            status="queued",
            progress=0.0,
            message="Queued",
        ))

    if task_rows:
        db.add_all(task_rows)
        await db.flush()

    logger.info(f"Queued {len(jobs_queued)} processing jobs for dataset {dataset.id}: {jobs_queued}")

    return UploadResponse(
        id=dataset.id,
        name=dataset.name,
        row_count=len(rows),
        columns=columns,
        column_types=column_types,
        normalized_columns=column_mapping,
        ioc_columns=ioc_columns,
        artifact_type=artifact_type,
        processing_status="processing",
        jobs_queued=jobs_queued,
        message=f"Successfully uploaded {len(rows)} rows. {len(jobs_queued)} processing jobs queued.",
    )


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List datasets",
)
async def list_datasets(
    hunt_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = DatasetRepository(db)
    datasets = await repo.list_datasets(hunt_id=hunt_id, limit=limit, offset=offset)
    total = await repo.count_datasets(hunt_id=hunt_id)

    return DatasetListResponse(
        datasets=[
            DatasetSummary(
                id=ds.id,
                name=ds.name,
                filename=ds.filename,
                source_tool=ds.source_tool,
                row_count=ds.row_count,
                column_schema=ds.column_schema,
                normalized_columns=ds.normalized_columns,
                ioc_columns=ds.ioc_columns,
                file_size_bytes=ds.file_size_bytes,
                encoding=ds.encoding,
                delimiter=ds.delimiter,
                time_range_start=ds.time_range_start.isoformat() if ds.time_range_start else None,
                time_range_end=ds.time_range_end.isoformat() if ds.time_range_end else None,
                artifact_type=ds.artifact_type,
                processing_status=ds.processing_status,
                hunt_id=ds.hunt_id,
                created_at=ds.created_at.isoformat(),
            )
            for ds in datasets
        ],
        total=total,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetSummary,
    summary="Get dataset details",
)
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = DatasetRepository(db)
    ds = await repo.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetSummary(
        id=ds.id,
        name=ds.name,
        filename=ds.filename,
        source_tool=ds.source_tool,
        row_count=ds.row_count,
        column_schema=ds.column_schema,
        normalized_columns=ds.normalized_columns,
        ioc_columns=ds.ioc_columns,
        file_size_bytes=ds.file_size_bytes,
        encoding=ds.encoding,
        delimiter=ds.delimiter,
        time_range_start=ds.time_range_start.isoformat() if ds.time_range_start else None,
        time_range_end=ds.time_range_end.isoformat() if ds.time_range_end else None,
        artifact_type=ds.artifact_type,
        processing_status=ds.processing_status,
        hunt_id=ds.hunt_id,
        created_at=ds.created_at.isoformat(),
    )


@router.get(
    "/{dataset_id}/rows",
    response_model=RowsResponse,
    summary="Get dataset rows",
)
async def get_dataset_rows(
    dataset_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    normalized: bool = Query(False, description="Return normalized column names"),
    db: AsyncSession = Depends(get_db),
):
    repo = DatasetRepository(db)
    ds = await repo.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    rows = await repo.get_rows(dataset_id, limit=limit, offset=offset)
    total = await repo.count_rows(dataset_id)

    return RowsResponse(
        rows=[
            (r.normalized_data if normalized and r.normalized_data else r.data)
            for r in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.delete(
    "/{dataset_id}",
    summary="Delete a dataset",
)
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = DatasetRepository(db)
    deleted = await repo.delete_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    keyword_scan_cache.invalidate_dataset(dataset_id)
    return {"message": "Dataset deleted", "id": dataset_id}
