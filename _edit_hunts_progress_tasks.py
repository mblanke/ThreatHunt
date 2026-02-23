from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/hunts.py')
t=p.read_text(encoding='utf-8')
if 'ProcessingTask' not in t:
    t=t.replace('from app.db.models import Hunt, Dataset','from app.db.models import Hunt, Dataset, ProcessingTask')

old='''    jobs = job_queue.list_jobs(limit=5000)
    relevant_jobs = [
        j for j in jobs
        if j.get("params", {}).get("hunt_id") == hunt_id
        or j.get("params", {}).get("dataset_id") in dataset_ids
    ]
    active_jobs = sum(1 for j in relevant_jobs if j.get("status") == "running")
    queued_jobs = sum(1 for j in relevant_jobs if j.get("status") == "queued")

    if inventory_cache.get(hunt_id) is not None:
'''
new='''    jobs = job_queue.list_jobs(limit=5000)
    relevant_jobs = [
        j for j in jobs
        if j.get("params", {}).get("hunt_id") == hunt_id
        or j.get("params", {}).get("dataset_id") in dataset_ids
    ]
    active_jobs_mem = sum(1 for j in relevant_jobs if j.get("status") == "running")
    queued_jobs_mem = sum(1 for j in relevant_jobs if j.get("status") == "queued")

    task_rows = await db.execute(
        select(ProcessingTask.stage, ProcessingTask.status, ProcessingTask.progress)
        .where(ProcessingTask.hunt_id == hunt_id)
    )
    tasks = task_rows.all()

    task_total = len(tasks)
    task_done = sum(1 for _, st, _ in tasks if st in ("completed", "failed", "cancelled"))
    task_running = sum(1 for _, st, _ in tasks if st == "running")
    task_queued = sum(1 for _, st, _ in tasks if st == "queued")
    task_ratio = (task_done / task_total) if task_total > 0 else None

    active_jobs = max(active_jobs_mem, task_running)
    queued_jobs = max(queued_jobs_mem, task_queued)

    stage_rollup: dict[str, dict] = {}
    for stage, status, progress in tasks:
        bucket = stage_rollup.setdefault(stage, {"total": 0, "done": 0, "running": 0, "queued": 0, "progress_sum": 0.0})
        bucket["total"] += 1
        if status in ("completed", "failed", "cancelled"):
            bucket["done"] += 1
        elif status == "running":
            bucket["running"] += 1
        elif status == "queued":
            bucket["queued"] += 1
        bucket["progress_sum"] += float(progress or 0.0)

    for stage_name, bucket in stage_rollup.items():
        total = max(1, bucket["total"])
        bucket["percent"] = round(bucket["progress_sum"] / total, 1)

    if inventory_cache.get(hunt_id) is not None:
'''
if old not in t:
    raise SystemExit('job block not found')
t=t.replace(old,new)

old2='''    dataset_ratio = ((dataset_completed + dataset_errors) / dataset_total) if dataset_total > 0 else 1.0
    overall_ratio = min(1.0, (dataset_ratio * 0.85) + (network_ratio * 0.15))
    progress_percent = round(overall_ratio * 100.0, 1)
'''
new2='''    dataset_ratio = ((dataset_completed + dataset_errors) / dataset_total) if dataset_total > 0 else 1.0
    if task_ratio is None:
        overall_ratio = min(1.0, (dataset_ratio * 0.85) + (network_ratio * 0.15))
    else:
        overall_ratio = min(1.0, (dataset_ratio * 0.50) + (task_ratio * 0.35) + (network_ratio * 0.15))
    progress_percent = round(overall_ratio * 100.0, 1)
'''
if old2 not in t:
    raise SystemExit('ratio block not found')
t=t.replace(old2,new2)

old3='''        "jobs": {
            "active": active_jobs,
            "queued": queued_jobs,
            "total_seen": len(relevant_jobs),
        },
    }
'''
new3='''        "jobs": {
            "active": active_jobs,
            "queued": queued_jobs,
            "total_seen": len(relevant_jobs),
            "task_total": task_total,
            "task_done": task_done,
            "task_percent": round((task_ratio or 0.0) * 100.0, 1) if task_total else None,
        },
        "task_stages": stage_rollup,
    }
'''
if old3 not in t:
    raise SystemExit('stages jobs block not found')
t=t.replace(old3,new3)

p.write_text(t,encoding='utf-8')
print('updated hunt progress to merge persistent processing tasks')
