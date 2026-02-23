from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/job_queue.py')
t=p.read_text(encoding='utf-8')
old='''async def _handle_keyword_scan(job: Job):
    """AUP keyword scan handler."""
    from app.db import async_session_factory
    from app.services.scanner import KeywordScanner

    dataset_id = job.params.get("dataset_id")
    job.message = f"Running AUP keyword scan on dataset {dataset_id}"

    async with async_session_factory() as db:
        scanner = KeywordScanner(db)
        result = await scanner.scan(dataset_ids=[dataset_id])

    hits = result.get("total_hits", 0)
    job.message = f"Keyword scan complete: {hits} hits"
    logger.info(f"Keyword scan for {dataset_id}: {hits} hits across {result.get('rows_scanned', 0)} rows")
    return {"dataset_id": dataset_id, "total_hits": hits, "rows_scanned": result.get("rows_scanned", 0)}
'''
new='''async def _handle_keyword_scan(job: Job):
    """AUP keyword scan handler."""
    from app.db import async_session_factory
    from app.services.scanner import KeywordScanner, keyword_scan_cache

    dataset_id = job.params.get("dataset_id")
    job.message = f"Running AUP keyword scan on dataset {dataset_id}"

    async with async_session_factory() as db:
        scanner = KeywordScanner(db)
        result = await scanner.scan(dataset_ids=[dataset_id])

    # Cache dataset-only result for fast API reuse
    if dataset_id:
        keyword_scan_cache.put(dataset_id, result)

    hits = result.get("total_hits", 0)
    job.message = f"Keyword scan complete: {hits} hits"
    logger.info(f"Keyword scan for {dataset_id}: {hits} hits across {result.get('rows_scanned', 0)} rows")
    return {"dataset_id": dataset_id, "total_hits": hits, "rows_scanned": result.get("rows_scanned", 0)}
'''
if old not in t:
    raise SystemExit('target block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated job_queue keyword scan handler')
