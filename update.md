# ThreatHunt  Update Log

## 2026-02-20: Host-Centric Network Map & Analysis Platform

### Network Map Overhaul
- **Problem**: Network Map showed 409 misclassified "domain" nodes (mostly process names like svchost.exe) and 0 hosts. No deduplication  same host counted once per dataset.
- **Root Cause**: IOC column detection misclassified `Fqdn` as "domain" instead of "hostname"; `Name` column (process names) wrongly tagged as "domain" IOC; `ClientId` was in `normalized_columns` as "hostname" but not in `ioc_columns`.
- **Solution**: Created a new host-centric inventory system that scans all datasets, groups by `Fqdn`/`ClientId`, and extracts IPs, users, OS, and network connections.

#### New Backend Files
- `backend/app/services/host_inventory.py`  Deduplicated host inventory builder. Scans all datasets in a hunt, identifies unique hosts via regex-based column detection (`ClientId`, `Fqdn`, `User`/`Username`, `Laddr.IP`/`Raddr.IP`), groups rows, extracts metadata. Filters system accounts (DWM-*, UMFD-*, LOCAL SERVICE, NETWORK SERVICE). Infers OS from hostname patterns (W10-*  Windows 10). Builds network connection graph from netstat remote IPs.
- `backend/app/api/routes/network.py`  `GET /api/network/host-inventory?hunt_id=X` endpoint returning `{hosts, connections, stats}`.
- `backend/app/services/ioc_extractor.py`  IOC extraction service (IP, domain, hash, email, URL patterns).
- `backend/app/services/anomaly_detector.py`  Statistical anomaly detection across datasets.
- `backend/app/services/data_query.py`  Natural language to structured query translation.
- `backend/app/services/load_balancer.py`  Round-robin load balancer for Ollama LLM nodes.
- `backend/app/services/job_queue.py`  Async job queue for long-running analysis tasks.
- `backend/app/api/routes/analysis.py`  16 analysis endpoints (IOC extraction, anomaly detection, host profiling, triage, reports, job management).

#### Modified Backend Files
- `backend/app/main.py`  Added `network_router` and `analysis_router` includes.
- `backend/app/db/models.py`  Added 4 AI/analysis ORM models (`ProcessingJob`, `AnalysisResult`, `HostProfile`, `IOCEntry`).
- `backend/app/db/engine.py`  Connection pool tuning for SQLite async.

#### Frontend Changes
- `frontend/src/components/NetworkMap.tsx`  Complete rewrite: host-centric force-directed graph using Canvas 2D. Two node types (Host / External IP). Shows hostname, IP, OS in labels. Click popover shows FQDN, IPs, OS, logged-in users, datasets, connections. Search across hostname/IP/user/OS. Stats cards showing host counts.
- `frontend/src/components/AnalysisDashboard.tsx`  New 6-tab analysis dashboard (IOC Extraction, Anomaly Detection, Host Profiling, Query, Triage, Reports).
- `frontend/src/api/client.ts`  Added `network.hostInventory()` method + `InventoryHost`, `InventoryConnection`, `InventoryStats` types. Added analysis API namespace with 16 endpoint methods.
- `frontend/src/App.tsx`  Added Analysis Dashboard route and navigation.

### Results (Radio Hunt  20 Velociraptor datasets, 394K rows)

| Metric | Before | After |
|--------|--------|-------|
| Nodes shown | 409 misclassified "domains" | **163 unique hosts** |
| Hosts identified | 0 | **163** |
| With IP addresses | N/A | **48** (172.17.x.x LAN) |
| With logged-in users | N/A | **43** (real names only) |
| OS detected | None | **Windows 10** (inferred from hostnames) |
| Deduplication | None (same host  20 datasets) | **Full** (by FQDN/ClientId) |
| System account filtering | None | **DWM-*, UMFD-*, LOCAL/NETWORK SERVICE removed** |
## 2026-02-23: Agent Execution Controls, Learning Mode, and Dev Startup Hardening

### Agent Assist: Explicit Execution + Learning Controls
- **Problem**: Agent behavior was partly implicit (intent-triggered execution only), with no analyst override to force/disable execution and no explicit "learning mode" explainability toggle.
- **Solution**:
  - Added `execution_preference` to assist requests (`auto | force | off`).
  - Added `learning_mode` flag for analyst-friendly explanations and rationale.
  - Preserved deterministic execution path for policy-domain scans while allowing explicit override.

#### Backend Updates
- `backend/app/api/routes/agent_v2.py`
  - Extended `AssistRequest` with `execution_preference` and `learning_mode`.
  - Added `_should_execute_policy_scan(request)` helper:
    - `off`: advisory-only (never execute scan)
    - `force`: execute scan regardless of query phrasing
    - `auto`: existing intent-based policy execution behavior
  - Wired `learning_mode` into agent context calls.
- `backend/app/agents/core_v2.py`
  - Extended `AgentContext` with `learning_mode: bool`.
  - Prompt construction now adds analyst-teaching/explainability guidance when enabled.

#### Frontend Updates
- `frontend/src/api/client.ts`
  - Extended `AssistRequest` with `execution_preference` and `learning_mode`.
  - Extended `AssistResponse` with optional `execution` payload.
- `frontend/src/components/AgentPanel.tsx`
  - Added Execution selector (`Auto`, `Force execute`, `Advisory only`).
  - Added `Learning mode` switch.
  - Added execution results accordion (scope, datasets, top domains, hit count, elapsed).
  - Cleaned stream update logic to avoid loop-closure lint warnings.

#### Tests and Validation
- `backend/tests/test_agent_policy_execution.py`
  - Added regression tests for:
    - `execution_preference=off` (stays advisory)
    - `execution_preference=force` (executes scanner)
- Validation:
  - Backend tests: `test_agent_policy_execution.py` passed.
  - Frontend build: clean compile after warning cleanup.

### Frontend Warning Cleanup
- `frontend/src/components/AnalysisDashboard.tsx`
  - Removed unused `DeleteIcon` import.
- `frontend/src/components/MitreMatrix.tsx`
  - Fixed `useCallback` dependency warning by including `huntList`.

### Dev Reliability: Docker Compose Startup on PowerShell
- **Problem**: Intermittent `docker compose up -d 2>&1` exit code `1` despite healthy/running containers.
- **Root Cause**: PowerShell `2>&1` handling can surface `NativeCommandError` for compose stderr/progress output (false failure signal).
- **Solution**:
  - Added `scripts/dev-up.ps1` startup helper to:
    - run compose with stable output handling,
    - show container status,
    - verify backend/frontend readiness,
    - return actionable exit codes.
  - Updated backend liveness probe to `http://localhost:8000/openapi.json` (current app does not expose `/health`).
