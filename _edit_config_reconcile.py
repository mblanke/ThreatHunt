from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/config.py')
t=p.read_text(encoding='utf-8')
anchor='''    STARTUP_REPROCESS_MAX_DATASETS: int = Field(
        default=25, description="Max unprocessed datasets to enqueue at startup"
    )
'''
insert='''    STARTUP_REPROCESS_MAX_DATASETS: int = Field(
        default=25, description="Max unprocessed datasets to enqueue at startup"
    )
    STARTUP_RECONCILE_STALE_TASKS: bool = Field(
        default=True,
        description="Mark stale queued/running processing tasks as failed on startup",
    )
'''
if anchor not in t:
    raise SystemExit('startup anchor not found')
t=t.replace(anchor,insert)
p.write_text(t,encoding='utf-8')
print('updated config with STARTUP_RECONCILE_STALE_TASKS')
