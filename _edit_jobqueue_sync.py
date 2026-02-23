from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/job_queue.py')
t=p.read_text(encoding='utf-8')
ins='''\n\nasync def _sync_processing_task(job: Job):\n    """Persist latest job state into processing_tasks (if linked by job_id)."""\n    from datetime import datetime, timezone\n    from sqlalchemy import update\n\n    try:\n        from app.db import async_session_factory\n        from app.db.models import ProcessingTask\n\n        values = {\n            "status": job.status.value,\n            "progress": float(job.progress),\n            "message": job.message,\n            "error": job.error,\n        }\n        if job.started_at:\n            values["started_at"] = datetime.fromtimestamp(job.started_at, tz=timezone.utc)\n        if job.completed_at:\n            values["completed_at"] = datetime.fromtimestamp(job.completed_at, tz=timezone.utc)\n\n        async with async_session_factory() as db:\n            await db.execute(\n                update(ProcessingTask)\n                .where(ProcessingTask.job_id == job.id)\n                .values(**values)\n            )\n            await db.commit()\n    except Exception as e:\n        logger.warning(f"Failed to sync processing task for job {job.id}: {e}")\n'''
marker='\n\n# -- Singleton + job handlers --\n'
if ins.strip() not in t:
    t=t.replace(marker, ins+marker)

old='''            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            job.message = "Running..."
            logger.info(f"Worker {worker_id}: executing {job.id} ({job.job_type.value})")

            try:
'''
new='''            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            if job.progress <= 0:
                job.progress = 5.0
            job.message = "Running..."
            await _sync_processing_task(job)
            logger.info(f"Worker {worker_id}: executing {job.id} ({job.job_type.value})")

            try:
'''
if old not in t:
    raise SystemExit('worker running block not found')
t=t.replace(old,new)

old2='''                    job.completed_at = time.time()
                    logger.info(f"Worker {worker_id}: completed {job.id} in {job.elapsed_ms}ms")
            except Exception as e:
                if not job.is_cancelled:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.message = f"Failed: {e}"
                    job.completed_at = time.time()
                    logger.error(f"Worker {worker_id}: failed {job.id}: {e}", exc_info=True)

            # Fire completion callbacks
'''
new2='''                    job.completed_at = time.time()
                    logger.info(f"Worker {worker_id}: completed {job.id} in {job.elapsed_ms}ms")
            except Exception as e:
                if not job.is_cancelled:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.message = f"Failed: {e}"
                    job.completed_at = time.time()
                    logger.error(f"Worker {worker_id}: failed {job.id}: {e}", exc_info=True)

            if job.is_cancelled and not job.completed_at:
                job.completed_at = time.time()

            await _sync_processing_task(job)

            # Fire completion callbacks
'''
if old2 not in t:
    raise SystemExit('worker completion block not found')
t=t.replace(old2,new2)

p.write_text(t, encoding='utf-8')
print('updated job_queue persistent task syncing')
