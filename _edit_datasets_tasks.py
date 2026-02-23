from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/datasets.py')
t=p.read_text(encoding='utf-8')
if 'ProcessingTask' not in t:
    t=t.replace('from app.db.models import', 'from app.db.models import ProcessingTask\n# from app.db.models import')
    t=t.replace('from app.services.scanner import keyword_scan_cache','from app.services.scanner import keyword_scan_cache')
# clean import replacement to proper single line
if '# from app.db.models import' in t:
    t=t.replace('from app.db.models import ProcessingTask\n# from app.db.models import', 'from app.db.models import ProcessingTask')

old='''    # 1. AI Triage (chains to HOST_PROFILE automatically on completion)
    job_queue.submit(JobType.TRIAGE, dataset_id=dataset.id)
    jobs_queued.append("triage")

    # 2. Anomaly detection (embedding-based outlier detection)
    job_queue.submit(JobType.ANOMALY, dataset_id=dataset.id)
    jobs_queued.append("anomaly")

    # 3. AUP keyword scan
    job_queue.submit(JobType.KEYWORD_SCAN, dataset_id=dataset.id)
    jobs_queued.append("keyword_scan")

    # 4. IOC extraction
    job_queue.submit(JobType.IOC_EXTRACT, dataset_id=dataset.id)
    jobs_queued.append("ioc_extract")

    # 5. Host inventory (network map) - requires hunt_id
    if hunt_id:
        inventory_cache.invalidate(hunt_id)
        job_queue.submit(JobType.HOST_INVENTORY, hunt_id=hunt_id)
        jobs_queued.append("host_inventory")
'''
new='''    task_rows: list[ProcessingTask] = []

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
'''
if old not in t:
    raise SystemExit('queue block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated datasets upload queue + processing tasks')
