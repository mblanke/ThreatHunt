from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/main.py')
t=p.read_text(encoding='utf-8')
old='''    # Start job queue
    from app.services.job_queue import job_queue, register_all_handlers, JobType
    register_all_handlers()
    await job_queue.start()
    logger.info("Job queue started (%d workers)", job_queue._max_workers)
'''
new='''    # Start job queue
    from app.services.job_queue import (
        job_queue,
        register_all_handlers,
        reconcile_stale_processing_tasks,
        JobType,
    )

    if settings.STARTUP_RECONCILE_STALE_TASKS:
        reconciled = await reconcile_stale_processing_tasks()
        if reconciled:
            logger.info("Startup reconciliation marked %d stale tasks", reconciled)

    register_all_handlers()
    await job_queue.start()
    logger.info("Job queue started (%d workers)", job_queue._max_workers)
'''
if old not in t:
    raise SystemExit('startup queue block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('wired startup reconciliation in main lifespan')
