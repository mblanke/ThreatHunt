from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/job_queue.py')
t=p.read_text(encoding='utf-8')
old='''        if hunt_id:
            job_queue.submit(JobType.HOST_PROFILE, hunt_id=hunt_id)
            logger.info(f"Triage done for {dataset_id} - chained HOST_PROFILE for hunt {hunt_id}")
    except Exception as e:
'''
new='''        if hunt_id:
            hp_job = job_queue.submit(JobType.HOST_PROFILE, hunt_id=hunt_id)
            try:
                from sqlalchemy import select
                from app.db.models import ProcessingTask
                async with async_session_factory() as db:
                    existing = await db.execute(
                        select(ProcessingTask.id).where(ProcessingTask.job_id == hp_job.id)
                    )
                    if existing.first() is None:
                        db.add(ProcessingTask(
                            hunt_id=hunt_id,
                            dataset_id=dataset_id,
                            job_id=hp_job.id,
                            stage="host_profile",
                            status="queued",
                            progress=0.0,
                            message="Queued",
                        ))
                        await db.commit()
            except Exception as persist_err:
                logger.warning(f"Failed to persist chained HOST_PROFILE task: {persist_err}")

            logger.info(f"Triage done for {dataset_id} - chained HOST_PROFILE for hunt {hunt_id}")
    except Exception as e:
'''
if old not in t:
    raise SystemExit('triage chain block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated triage chain to persist host_profile task row')
