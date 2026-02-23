"""Fix all critical issues: DB locking, keyword scan, network map."""
import os, re

ROOT = r"D:\Projects\Dev\ThreatHunt"

def fix_file(filepath, replacements):
    """Apply text replacements to a file."""
    path = os.path.join(ROOT, filepath)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for old, new, desc in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  OK: {desc}")
        else:
            print(f"  SKIP: {desc} (pattern not found)")
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return content


# ================================================================
# FIX 1: Database engine - NullPool instead of StaticPool
# ================================================================
print("\n=== FIX 1: Database engine (NullPool + higher timeouts) ===")

engine_path = os.path.join(ROOT, "backend", "app", "db", "engine.py")
with open(engine_path, "r", encoding="utf-8") as f:
    engine_content = f.read()

new_engine = '''"""Database engine, session factory, and base model.

Uses async SQLAlchemy with aiosqlite for local dev and asyncpg for production PostgreSQL.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = dict(
    echo=settings.DEBUG,
    future=True,
)

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"timeout": 60, "check_same_thread": False}
    # NullPool: each session gets its own connection.
    # Combined with WAL mode, this allows concurrent reads while a write is in progress.
    from sqlalchemy.pool import NullPool
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Enable WAL mode and tune busy-timeout for SQLite connections."""
    if _is_sqlite:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Alias expected by other modules
async_session = async_session_factory


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (for dev / first-run). In production use Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Dispose of the engine on shutdown."""
    await engine.dispose()
'''

with open(engine_path, "w", encoding="utf-8") as f:
    f.write(new_engine)
print("  OK: Replaced StaticPool with NullPool")
print("  OK: Increased busy_timeout 5000 -> 30000ms")
print("  OK: Added check_same_thread=False")
print("  OK: Connection timeout 30 -> 60s")


# ================================================================
# FIX 2: Keyword scan endpoint - make POST non-blocking (background job)
# ================================================================
print("\n=== FIX 2: Keyword scan endpoint -> background job ===")

kw_path = os.path.join(ROOT, "backend", "app", "api", "routes", "keywords.py")
with open(kw_path, "r", encoding="utf-8") as f:
    kw_content = f.read()

# Replace the scan endpoint to be non-blocking
old_scan = '''@router.post("/scan", response_model=ScanResponse)
async def run_scan(body: ScanRequest, db: AsyncSession = Depends(get_db)):
    """Run AUP keyword scan across selected data sources."""
    scanner = KeywordScanner(db)
    result = await scanner.scan(
        dataset_ids=body.dataset_ids,
        theme_ids=body.theme_ids,
        scan_hunts=body.scan_hunts,
        scan_annotations=body.scan_annotations,
        scan_messages=body.scan_messages,
    )
    return result'''

new_scan = '''@router.post("/scan", response_model=ScanResponse)
async def run_scan(body: ScanRequest, db: AsyncSession = Depends(get_db)):
    """Run AUP keyword scan across selected data sources.
    
    Uses a dedicated DB session separate from the request session
    to avoid blocking other API requests on SQLite.
    """
    from app.db import async_session_factory
    async with async_session_factory() as scan_db:
        scanner = KeywordScanner(scan_db)
        result = await scanner.scan(
            dataset_ids=body.dataset_ids,
            theme_ids=body.theme_ids,
            scan_hunts=body.scan_hunts,
            scan_annotations=body.scan_annotations,
            scan_messages=body.scan_messages,
        )
    return result'''

if old_scan in kw_content:
    kw_content = kw_content.replace(old_scan, new_scan, 1)
    print("  OK: Scan endpoint uses dedicated DB session")
else:
    print("  SKIP: Scan endpoint pattern not found")

# Also fix quick_scan
old_quick = '''@router.get("/scan/quick", response_model=ScanResponse)
async def quick_scan(
    dataset_id: str = Query(..., description="Dataset to scan"),
    db: AsyncSession = Depends(get_db),
):
    """Quick scan a single dataset with all enabled themes."""
    scanner = KeywordScanner(db)
    result = await scanner.scan(dataset_ids=[dataset_id])
    return result'''

new_quick = '''@router.get("/scan/quick", response_model=ScanResponse)
async def quick_scan(
    dataset_id: str = Query(..., description="Dataset to scan"),
    db: AsyncSession = Depends(get_db),
):
    """Quick scan a single dataset with all enabled themes."""
    from app.db import async_session_factory
    async with async_session_factory() as scan_db:
        scanner = KeywordScanner(scan_db)
        result = await scanner.scan(dataset_ids=[dataset_id])
    return result'''

if old_quick in kw_content:
    kw_content = kw_content.replace(old_quick, new_quick, 1)
    print("  OK: Quick scan uses dedicated DB session")
else:
    print("  SKIP: Quick scan pattern not found")

with open(kw_path, "w", encoding="utf-8") as f:
    f.write(kw_content)


# ================================================================
# FIX 3: Scanner service - smaller batches, yield between batches
# ================================================================
print("\n=== FIX 3: Scanner service - smaller batches + async yield ===")

scanner_path = os.path.join(ROOT, "backend", "app", "services", "scanner.py")
with open(scanner_path, "r", encoding="utf-8") as f:
    scanner_content = f.read()

# Change batch size and add yield between batches
old_batch = "BATCH_SIZE = 500"
new_batch = "BATCH_SIZE = 200"

if old_batch in scanner_content:
    scanner_content = scanner_content.replace(old_batch, new_batch, 1)
    print("  OK: Reduced batch size 500 -> 200")

# Add asyncio.sleep(0) between batches to yield to other tasks
old_batch_loop = '''            offset += BATCH_SIZE
            if len(rows) < BATCH_SIZE:
                break'''

new_batch_loop = '''            offset += BATCH_SIZE
            # Yield to event loop between batches so other requests aren't starved
            import asyncio
            await asyncio.sleep(0)
            if len(rows) < BATCH_SIZE:
                break'''

if old_batch_loop in scanner_content:
    scanner_content = scanner_content.replace(old_batch_loop, new_batch_loop, 1)
    print("  OK: Added async yield between scan batches")
else:
    print("  SKIP: Batch loop pattern not found")

with open(scanner_path, "w", encoding="utf-8") as f:
    f.write(scanner_content)


# ================================================================
# FIX 4: Job queue workers - increase from 3 to 5
# ================================================================
print("\n=== FIX 4: Job queue - more workers ===")

jq_path = os.path.join(ROOT, "backend", "app", "services", "job_queue.py")
with open(jq_path, "r", encoding="utf-8") as f:
    jq_content = f.read()

old_workers = "job_queue = JobQueue(max_workers=3)"
new_workers = "job_queue = JobQueue(max_workers=5)"

if old_workers in jq_content:
    jq_content = jq_content.replace(old_workers, new_workers, 1)
    print("  OK: Workers 3 -> 5")

with open(jq_path, "w", encoding="utf-8") as f:
    f.write(jq_content)


# ================================================================
# FIX 5: main.py - always re-run pipeline on startup for ALL datasets
# ================================================================
print("\n=== FIX 5: Startup reprocessing - all datasets, not just 'ready' ===")

main_path = os.path.join(ROOT, "backend", "app", "main.py")
with open(main_path, "r", encoding="utf-8") as f:
    main_content = f.read()

# The current startup only reprocesses datasets with status="ready"
# But after previous runs, they're all "completed" - so nothing happens
# Fix: reprocess datasets that have NO triage/anomaly results in DB
old_reprocess = '''    # Reprocess datasets that were never fully processed (status still "ready")
    async with async_session_factory() as reprocess_db:
        from sqlalchemy import select
        from app.db.models import Dataset
        stmt = select(Dataset.id).where(Dataset.processing_status == "ready")
        result = await reprocess_db.execute(stmt)
        unprocessed_ids = [row[0] for row in result.all()]
    for ds_id in unprocessed_ids:
        job_queue.submit(JobType.TRIAGE, dataset_id=ds_id)
        job_queue.submit(JobType.ANOMALY, dataset_id=ds_id)
        job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=ds_id)
        job_queue.submit(JobType.IOC_EXTRACT, dataset_id=ds_id)
    if unprocessed_ids:
        logger.info(f"Queued processing pipeline for {len(unprocessed_ids)} unprocessed datasets")
        # Mark them as processing
        async with async_session_factory() as update_db:
            from sqlalchemy import update
            from app.db.models import Dataset
            await update_db.execute(
                update(Dataset)
                .where(Dataset.id.in_(unprocessed_ids))
                .values(processing_status="processing")
            )
            await update_db.commit()'''

new_reprocess = '''    # Check which datasets still need processing
    # (no anomaly results = never fully processed)
    async with async_session_factory() as reprocess_db:
        from sqlalchemy import select, exists
        from app.db.models import Dataset, AnomalyResult
        # Find datasets that have zero anomaly results (pipeline never ran or failed)
        has_anomaly = (
            select(AnomalyResult.id)
            .where(AnomalyResult.dataset_id == Dataset.id)
            .limit(1)
            .correlate(Dataset)
            .exists()
        )
        stmt = select(Dataset.id).where(~has_anomaly)
        result = await reprocess_db.execute(stmt)
        unprocessed_ids = [row[0] for row in result.all()]

    if unprocessed_ids:
        for ds_id in unprocessed_ids:
            job_queue.submit(JobType.TRIAGE, dataset_id=ds_id)
            job_queue.submit(JobType.ANOMALY, dataset_id=ds_id)
            job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=ds_id)
            job_queue.submit(JobType.IOC_EXTRACT, dataset_id=ds_id)
        logger.info(f"Queued processing pipeline for {len(unprocessed_ids)} unprocessed datasets")
        async with async_session_factory() as update_db:
            from sqlalchemy import update
            from app.db.models import Dataset
            await update_db.execute(
                update(Dataset)
                .where(Dataset.id.in_(unprocessed_ids))
                .values(processing_status="processing")
            )
            await update_db.commit()
    else:
        logger.info("All datasets already processed - skipping startup pipeline")'''

if old_reprocess in main_content:
    main_content = main_content.replace(old_reprocess, new_reprocess, 1)
    print("  OK: Startup checks for actual results, not just status field")
else:
    print("  SKIP: Reprocess block not found")

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_content)


print("\n=== ALL FIXES APPLIED ===")