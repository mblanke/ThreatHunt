from pathlib import Path

root = Path(r"d:\Projects\Dev\ThreatHunt")

# 1) config.py additions
cfg = root / "backend/app/config.py"
text = cfg.read_text(encoding="utf-8")
needle = "    # -- Scanner settings -----------------------------------------------\n    SCANNER_BATCH_SIZE: int = Field(default=500, description=\"Rows per scanner batch\")\n"
insert = "    # -- Scanner settings -----------------------------------------------\n    SCANNER_BATCH_SIZE: int = Field(default=500, description=\"Rows per scanner batch\")\n\n    # -- Job queue settings ----------------------------------------------\n    JOB_QUEUE_MAX_BACKLOG: int = Field(\n        default=2000, description=\"Soft cap for queued background jobs\"\n    )\n    JOB_QUEUE_RETAIN_COMPLETED: int = Field(\n        default=3000, description=\"Maximum completed/failed jobs to retain in memory\"\n    )\n    JOB_QUEUE_CLEANUP_INTERVAL_SECONDS: int = Field(\n        default=60, description=\"How often to run in-memory job cleanup\"\n    )\n    JOB_QUEUE_CLEANUP_MAX_AGE_SECONDS: int = Field(\n        default=3600, description=\"Age threshold for in-memory completed job cleanup\"\n    )\n"
if needle in text:
    text = text.replace(needle, insert)
cfg.write_text(text, encoding="utf-8")

# 2) scanner.py default scope = dataset-only
scanner = root / "backend/app/services/scanner.py"
text = scanner.read_text(encoding="utf-8")
text = text.replace("        scan_hunts: bool = True,", "        scan_hunts: bool = False,")
text = text.replace("        scan_annotations: bool = True,", "        scan_annotations: bool = False,")
text = text.replace("        scan_messages: bool = True,", "        scan_messages: bool = False,")
scanner.write_text(text, encoding="utf-8")

# 3) keywords.py defaults = dataset-only
kw = root / "backend/app/api/routes/keywords.py"
text = kw.read_text(encoding="utf-8")
text = text.replace("    scan_hunts: bool = True", "    scan_hunts: bool = False")
text = text.replace("    scan_annotations: bool = True", "    scan_annotations: bool = False")
text = text.replace("    scan_messages: bool = True", "    scan_messages: bool = False")
kw.write_text(text, encoding="utf-8")

# 4) job_queue.py dedupe + periodic cleanup
jq = root / "backend/app/services/job_queue.py"
text = jq.read_text(encoding="utf-8")

text = text.replace(
"from typing import Any, Callable, Coroutine, Optional\n",
"from typing import Any, Callable, Coroutine, Optional\n\nfrom app.config import settings\n"
)

text = text.replace(
"        self._completion_callbacks: list[Callable[[Job], Coroutine]] = []\n",
"        self._completion_callbacks: list[Callable[[Job], Coroutine]] = []\n        self._cleanup_task: asyncio.Task | None = None\n"
)

start_old = '''    async def start(self):
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        logger.info(f"Job queue started with {self._max_workers} workers")
'''
start_new = '''    async def start(self):
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Job queue started with {self._max_workers} workers")
'''
text = text.replace(start_old, start_new)

stop_old = '''    async def stop(self):
        self._started = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Job queue stopped")
'''
stop_new = '''    async def stop(self):
        self._started = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        logger.info("Job queue stopped")
'''
text = text.replace(stop_old, stop_new)

submit_old = '''    def submit(self, job_type: JobType, **params) -> Job:
        job = Job(id=str(uuid.uuid4()), job_type=job_type, params=params)
        self._jobs[job.id] = job
        self._queue.put_nowait(job.id)
        logger.info(f"Job submitted: {job.id} ({job_type.value}) params={params}")
        return job
'''
submit_new = '''    def submit(self, job_type: JobType, **params) -> Job:
        # Soft backpressure: prefer dedupe over queue amplification
        dedupe_job = self._find_active_duplicate(job_type, params)
        if dedupe_job is not None:
            logger.info(
                f"Job deduped: reusing {dedupe_job.id} ({job_type.value}) params={params}"
            )
            return dedupe_job

        if self._queue.qsize() >= settings.JOB_QUEUE_MAX_BACKLOG:
            logger.warning(
                "Job queue backlog high (%d >= %d). Accepting job but system may be degraded.",
                self._queue.qsize(), settings.JOB_QUEUE_MAX_BACKLOG,
            )

        job = Job(id=str(uuid.uuid4()), job_type=job_type, params=params)
        self._jobs[job.id] = job
        self._queue.put_nowait(job.id)
        logger.info(f"Job submitted: {job.id} ({job_type.value}) params={params}")
        return job
'''
text = text.replace(submit_old, submit_new)

insert_methods_after = "    def get_job(self, job_id: str) -> Job | None:\n        return self._jobs.get(job_id)\n"
new_methods = '''    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _find_active_duplicate(self, job_type: JobType, params: dict) -> Job | None:
        """Return queued/running job with same key workload to prevent duplicate storms."""
        key_fields = ["dataset_id", "hunt_id", "hostname", "question", "mode"]
        sig = tuple((k, params.get(k)) for k in key_fields if params.get(k) is not None)
        if not sig:
            return None
        for j in self._jobs.values():
            if j.job_type != job_type:
                continue
            if j.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                continue
            other_sig = tuple((k, j.params.get(k)) for k in key_fields if j.params.get(k) is not None)
            if sig == other_sig:
                return j
        return None
'''
text = text.replace(insert_methods_after, new_methods)

cleanup_old = '''    def cleanup(self, max_age_seconds: float = 3600):
        now = time.time()
        to_remove = [
            jid for jid, j in self._jobs.items()
            if j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
            and (now - j.created_at) > max_age_seconds
        ]
        for jid in to_remove:
            del self._jobs[jid]
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")
'''
cleanup_new = '''    def cleanup(self, max_age_seconds: float = 3600):
        now = time.time()
        terminal_states = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
        to_remove = [
            jid for jid, j in self._jobs.items()
            if j.status in terminal_states and (now - j.created_at) > max_age_seconds
        ]

        # Also cap retained terminal jobs to avoid unbounded memory growth
        terminal_jobs = sorted(
            [j for j in self._jobs.values() if j.status in terminal_states],
            key=lambda j: j.created_at,
            reverse=True,
        )
        overflow = terminal_jobs[settings.JOB_QUEUE_RETAIN_COMPLETED :]
        to_remove.extend([j.id for j in overflow])

        removed = 0
        for jid in set(to_remove):
            if jid in self._jobs:
                del self._jobs[jid]
                removed += 1
        if removed:
            logger.info(f"Cleaned up {removed} old jobs")

    async def _cleanup_loop(self):
        interval = max(10, settings.JOB_QUEUE_CLEANUP_INTERVAL_SECONDS)
        while self._started:
            try:
                self.cleanup(max_age_seconds=settings.JOB_QUEUE_CLEANUP_MAX_AGE_SECONDS)
            except Exception as e:
                logger.warning(f"Job queue cleanup loop error: {e}")
            await asyncio.sleep(interval)
'''
text = text.replace(cleanup_old, cleanup_new)

jq.write_text(text, encoding="utf-8")

# 5) NetworkMap polling backoff/jitter max wait
nm = root / "frontend/src/components/NetworkMap.tsx"
text = nm.read_text(encoding="utf-8")

text = text.replace(
"        // Poll until ready, then re-fetch\n        for (;;) {\n          await new Promise(r => setTimeout(r, 2000));\n          const st = await network.inventoryStatus(huntId);\n          if (st.status === 'ready') break;\n        }\n",
"        // Poll until ready (exponential backoff), then re-fetch\n        let delayMs = 1500;\n        const startedAt = Date.now();\n        for (;;) {\n          const jitter = Math.floor(Math.random() * 250);\n          await new Promise(r => setTimeout(r, delayMs + jitter));\n          const st = await network.inventoryStatus(huntId);\n          if (st.status === 'ready') break;\n          if (Date.now() - startedAt > 5 * 60 * 1000) {\n            throw new Error('Host inventory build timed out after 5 minutes');\n          }\n          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));\n        }\n"
)

text = text.replace(
"    const waitUntilReady = async (): Promise<boolean> => {\n      // Poll inventory-status every 2s until 'ready' (or cancelled)\n      setProgress('Host inventory is being prepared in the background');\n      setLoading(true);\n      for (;;) {\n        await new Promise(r => setTimeout(r, 2000));\n        if (cancelled) return false;\n        try {\n          const st = await network.inventoryStatus(selectedHuntId);\n          if (cancelled) return false;\n          if (st.status === 'ready') return true;\n          // still building or none (job may not have started yet) - keep polling\n        } catch { if (cancelled) return false; }\n      }\n    };\n",
"    const waitUntilReady = async (): Promise<boolean> => {\n      // Poll inventory-status with exponential backoff until 'ready' (or cancelled)\n      setProgress('Host inventory is being prepared in the background');\n      setLoading(true);\n      let delayMs = 1500;\n      const startedAt = Date.now();\n      for (;;) {\n        const jitter = Math.floor(Math.random() * 250);\n        await new Promise(r => setTimeout(r, delayMs + jitter));\n        if (cancelled) return false;\n        try {\n          const st = await network.inventoryStatus(selectedHuntId);\n          if (cancelled) return false;\n          if (st.status === 'ready') return true;\n          if (Date.now() - startedAt > 5 * 60 * 1000) {\n            setError('Host inventory build timed out. Please retry.');\n            return false;\n          }\n          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));\n          // still building or none (job may not have started yet) - keep polling\n        } catch {\n          if (cancelled) return false;\n          delayMs = Math.min(10000, Math.floor(delayMs * 1.5));\n        }\n      }\n    };\n"
)

nm.write_text(text, encoding="utf-8")

print("Patched: config.py, scanner.py, keywords.py, job_queue.py, NetworkMap.tsx")