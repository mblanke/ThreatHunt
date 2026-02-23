from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/job_queue.py')
t=p.read_text(encoding='utf-8')
marker='''def register_all_handlers():
    """Register all job handlers and completion callbacks."""
'''
ins='''\n\nasync def reconcile_stale_processing_tasks() -> int:\n    """Mark queued/running processing tasks from prior runs as failed."""\n    from datetime import datetime, timezone\n    from sqlalchemy import update\n\n    try:\n        from app.db import async_session_factory\n        from app.db.models import ProcessingTask\n\n        now = datetime.now(timezone.utc)\n        async with async_session_factory() as db:\n            result = await db.execute(\n                update(ProcessingTask)\n                .where(ProcessingTask.status.in_([\"queued\", \"running\"]))\n                .values(\n                    status=\"failed\",\n                    error=\"Recovered after service restart before task completion\",\n                    message=\"Recovered stale task after restart\",\n                    completed_at=now,\n                )\n            )\n            await db.commit()\n            updated = int(result.rowcount or 0)\n\n        if updated:\n            logger.warning(\n                \"Reconciled %d stale processing tasks (queued/running -> failed) during startup\",\n                updated,\n            )\n        return updated\n    except Exception as e:\n        logger.warning(f\"Failed to reconcile stale processing tasks: {e}\")\n        return 0\n\n\n'''
if ins.strip() not in t:
    if marker not in t:
        raise SystemExit('register marker not found')
    t=t.replace(marker,ins+marker)
p.write_text(t,encoding='utf-8')
print('added reconcile_stale_processing_tasks to job_queue')
