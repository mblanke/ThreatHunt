# ThreatHunt — Session Update (February 19–20, 2026)

**Version: 0.4.0**

## Summary

This document covers feature improvements and bug fixes across the ThreatHunt platform.

---

## 1. Network Map — Clickable Type Filters (IP / Host / Domain / URL)

**Request:** "IP, Host, Domain, URL on the network map… can I click on these and they would be filtered in or out"

**Changes (`NetworkMap.tsx`):**
- Legend chips (IP, Host, Domain, URL) are now clickable toggle filters
- Added `visibleTypes` state (`Set<NodeType>`) and `filteredGraph` useMemo that filters nodes + edges by visible types
- Active chips: filled background with type color, fully opaque
- Inactive chips: outlined with type color, dimmed at 50% opacity
- Each chip shows node count for that type, e.g. `IP (42)`
- At least one type must stay visible (can't disable all four)
- Stats chips (nodes/edges) update to reflect the filtered view
- All mouse handlers (pan, hover, click, wheel zoom) updated to use `filteredGraph` instead of raw `graph`

---

## 2. Network Map — Cleaner Nodes (Brighter Colors, 20% Smaller)

**Request:** "Clean up the icons, the colours are dull and the icons are too big in the map… shrink by 20%"

**Changes (`NetworkMap.tsx`):**
- Colors bumped to more saturated variants:
  - IP: `#60a5fa` → `#3b82f6`
  - Host: `#10b981` → `#22c55e`
  - Domain: `#f59e0b` → `#eab308`
  - URL: `#a78bfa` → `#8b5cf6`
- Node radius shrunk ~20%:
  - Max: 22 → 18
  - Base: 5 → 4
  - Multiplier: 2.0 → 1.6

---

## 3. Dataset Viewer — IOC Column Highlighting

**Request:** "I'm looking at one of the datasets and 4 IOCs are showing… but I can't see it… is there a way to highlight that"

**Changes (`DatasetViewer.tsx`):**
- IOC columns in the DataGrid are now visually highlighted
- **Header:** colored background tint + bold colored text + IOC type label (e.g. `src_ip  ◆ IP`)
- **Cells:** subtle colored background + left border stripe
- Color-coded by IOC type matching the Network Map palette:
  - IP — blue (`#3b82f6`)
  - Hostname — green (`#22c55e`)
  - Domain — amber (`#eab308`)
  - URL — purple (`#8b5cf6`)
  - Hashes (MD5/SHA1/SHA256) — rose (`#f43f5e`)
- Added `IOC_COLORS` mapping, `iocTypeFor()` helper, and dynamic `headerClassName`/`cellClassName` on DataGrid columns
- CSS-in-JS styles injected via DataGrid `sx` prop

---

## 4. AUP Scanner — "Social Media (Personal)" → "Social Media" Rename

**Request:** "On the AUP page there is Social Media (Personal) — can we remove personal, it's messing up with the formatting"

**Changes (`keyword_defaults.py`):**
- Default theme key renamed from `"Social Media (Personal)"` to `"Social Media"`
- Added rename migration in `seed_defaults()`: checks for old name in DB, if found renames via SQL UPDATE + commit before normal seeding
- Backend log confirmed: `Renamed AUP theme 'Social Media (Personal)' → 'Social Media'`

---

## 5. AUP Scanner — Hunt Dropdown (previous session, deployed)

- Replaced individual dataset checkboxes with a hunt selector dropdown
- Selecting a hunt auto-loads and selects all its datasets
- Shows dataset/row counts below the dropdown

---

## 6. Network Map — Hunt-Scoped Interactive Map (previous session, deployed)

- Hunt selector dropdown loads only that hunt's datasets
- Enriched nodes with hostname, IP, OS metadata
- Click-to-inspect MUI Popover showing node details
- Zoom (wheel + buttons) and pan (drag) with full viewport transform
- Force-directed layout with co-occurrence edges

---

## 7. Agent Assist — "Failed to Fetch" Diagnosis

**Request:** "AI assist failed: Error: Failed to fetch"

**Diagnosis:**
- Backend agent endpoint works correctly (tested via PowerShell `Invoke-RestMethod` through nginx proxy)
- Health endpoint healthy — both LLM nodes (Wile + Roadrunner) available
- Extra fields sent by frontend (`mode`, `hunt_id`, `conversation_id`) are accepted by Pydantic v2 (ignored, not rejected)
- "Failed to fetch" was a transient browser-level network error, not a backend issue
- Response time ~5s from LLM — within nginx 120s proxy timeout
- **Resolution:** Hard refresh (Ctrl+Shift+R) resolves the issue

---

## 8. Performance Fix — /api/hunts Timeout (previous session)

- Root cause: `Dataset.rows` relationship had `lazy="selectin"` causing SQLAlchemy to cascade-load every DatasetRow when listing hunts
- Fix: Changed `Dataset.rows` and `DatasetRow.annotations` to `lazy="noload"` in `backend/app/db/models.py`
- Result: Hunts endpoint returns instantly

---

## Files Modified This Session

| File | Change |
|------|--------|
| `frontend/src/components/NetworkMap.tsx` | Type filter toggles, brighter colors, smaller nodes |
| `frontend/src/components/DatasetViewer.tsx` | IOC column highlighting in DataGrid |
| `backend/app/services/keyword_defaults.py` | Theme rename + DB migration |

## Deployment

All changes built and deployed via Docker Compose:
```
docker compose build --no-cache frontend
docker compose up -d frontend
docker compose build --no-cache backend
docker compose up -d backend
```

## Git

Committed and pushed to GitHub (`main` branch):
```
92 files changed, 13050 insertions(+), 1097 deletions(-)
d0c9f88..9b98ab9  main -> main
```

---

## 9. Network Picture — Deduplicated Host Inventory (February 20, 2026)

**Request:** "While files are being dropped in, give me a clean clear network picture — like netstat. No 100 iterations of the same computer. Clean pic: hostname, IP, and any users logged into that machine."

### What It Does

New **Net Picture** page that scans all datasets in a hunt and produces a **one-row-per-host** inventory table. If a host appears in 900 netstat rows, it shows once — with all unique IPs, usernames, OS versions, MACs, and ports aggregated via server-side set deduplication. Supports networks with up to 1000 hosts; no artificial caps on unique values per host.

### Backend

**New service** — `backend/app/services/network_inventory.py`:
- `build_network_picture(db, hunt_id)` streams all dataset rows in batches of 1000
- Groups rows by `hostname` (case-insensitive), falls back to `src_ip`/`ip_address` if no hostname column
- Per host, aggregates into Python `set()`s: IPs, users, OS, MAC addresses, protocols, open ports, remote targets, dataset sources
- Tracks `connection_count` (total rows), `first_seen`/`last_seen` from timestamp columns
- Returns sorted by connection count descending

**New API route** — `backend/app/api/routes/network.py`:
- `GET /api/network/picture?hunt_id={id}` → `NetworkPictureResponse`
- Response: `hosts[]` (each with hostname, ips, users, os, mac_addresses, protocols, open_ports, remote_targets, datasets, connection_count, first_seen, last_seen) + `summary` (total_hosts, total_connections, total_unique_ips, datasets_scanned)

**Normalizer additions** — `backend/app/services/normalizer.py`:
- Added `mac_address` canonical mapping: `mac`, `mac_address`, `physical_address`, `mac_addr`, `hw_addr`, `ethernet`
- Added `connection_state` canonical mapping: `state`, `status`, `tcp_state`, `conn_state`

### Frontend

**New component** — `frontend/src/components/NetworkPicture.tsx`:
- Hunt selector dropdown → loads network picture from backend
- MUI Table with sortable columns: Hostname, IPs, Users, OS, MAC, Connections, Ports
- **ChipList** sub-component: shows first 5 values inline as coloured Chips; "+N more" badge expands to show all (no data hidden, just visual overflow control)
- Click any row → expand panel showing: remote targets, all open ports, protocols, MAC addresses, dataset sources, time range
- Search bar filters by hostname, IP, user, OS, or MAC
- Summary stat cards: total hosts, unique IPs, connections, datasets scanned
- Colour palette matches Network Map: IP blue, User green, OS amber, MAC purple, Port rose

**App integration** — `frontend/src/App.tsx`:
- New nav item: **Net Picture** with `DevicesIcon`, route `/netpicture`
- Import and route for `NetworkPicture` component

**API client** — `frontend/src/api/client.ts`:
- Added `HostEntry`, `PictureSummary`, `NetworkPictureResponse` interfaces
- Added `network.picture(huntId)` method

### Files Modified

| File | Change |
|------|--------|
| `backend/app/services/normalizer.py` | Added `mac_address` + `connection_state` mappings |
| `backend/app/services/network_inventory.py` | **New** — host aggregation service |
| `backend/app/api/routes/network.py` | **New** — `/api/network/picture` endpoint |
| `backend/app/main.py` | Registered network router |
| `frontend/src/api/client.ts` | Added network picture types + API method |
| `frontend/src/components/NetworkPicture.tsx` | **New** — host inventory table component |
| `frontend/src/App.tsx` | Added Nav item + route for Net Picture |

---

## 10. Test Data — Velociraptor Mock Network CSVs (February 20, 2026)

**Request:** "Create 10-15 different CSV files you'd expect from Velociraptor for a mock network with 50-100 hosts and random network traffic with a few keywords that would trigger the AUP."

### What Was Created

12 realistic Velociraptor-style CSV files in `backend/tests/test_csvs/`, generated by a Python script (`generate_test_csvs.py`) with deterministic seed for reproducibility.

**Mock Network:**
- **82 hosts**: 75 workstations (IT-WS, HR-WS, FIN-WS, SLS-WS, ENG-WS, LEG-WS, MKT-WS, EXEC-WS) + 7 servers (DC-01, DC-02, FILE-01, EXCH-01, WEB-01, SQL-01, PROXY-01)
- **14 users**: 10 named users (jsmith, agarcia, bwilson, etc.) + 4 service accounts
- **3 subnets**: `10.10.1.x`, `10.10.2.x`, `10.10.3.x`
- **Domain**: `acme.local`
- **Time range**: Feb 10–20, 2026

### Files

| # | File | Rows | Velociraptor Artifact |
|---|------|------|----------------------|
| 1 | `01_netstat_connections.csv` | 2,012 | `Windows.Network.Netstat` |
| 2 | `02_dns_queries.csv` | 2,964 | `Windows.Network.DNS` |
| 3 | `03_process_listing.csv` | 1,896 | `Windows.System.Pslist` |
| 4 | `04_network_interfaces.csv` | 94 | `Windows.Network.Interfaces` |
| 5 | `05_logged_in_users.csv` | 171 | `Windows.Sys.Users` |
| 6 | `06_scheduled_tasks.csv` | 410 | `Windows.System.TaskScheduler` |
| 7 | `07_browser_history.csv` | 1,586 | `Windows.Application.Chrome.History` |
| 8 | `08_sysmon_network.csv` | 2,517 | Sysmon Event ID 3 |
| 9 | `09_autoruns.csv` | 342 | `Windows.Sys.AutoRuns` |
| 10 | `10_logon_events.csv` | 1,604 | Windows Security (4624/4625) |
| 11 | `11_proxy_logs.csv` | 2,605 | Web proxy / filter |
| 12 | `12_file_listing.csv` | 421 | `Windows.Search.FileFinder` |

### AUP Triggers Embedded

| Category | Examples |
|----------|----------|
| Gambling | bet365.com, pokerstars.com, draftkings.com |
| Gaming | steam.exe, discord.exe, steamcommunity.com, epicgameslauncher.exe |
| Streaming | netflix.com, hulu.com, spotify.exe, open.spotify.com |
| Downloads / Piracy | thepiratebay.org, 1337x.to, utorrent.exe, qbittorrent.exe, free_movie_2026.torrent |
| Adult Content | pornhub.com, onlyfans.com, xvideos.com |
| Social Media | facebook.com, tiktok.com, reddit.com |
| Job Search | indeed.com, glassdoor.com, linkedin.com/jobs |
| Shopping | amazon.com, ebay.com, shein.com |

AUP keywords appear in: DNS queries (~12%), browser history (~15%), proxy logs (~10%), process listing (~15% of hosts), autoruns (~20% of workstations), sysmon network (~10%), file listing (crack_photoshop.exe, keygen_v2.exe, free_movie_2026.torrent).

### Files Added

| File | Purpose |
|------|---------|
| `backend/tests/generate_test_csvs.py` | **New** — deterministic CSV generator script |
| `backend/tests/test_csvs/*.csv` (×12) | **New** — mock Velociraptor test data |

---

## 11. Phase 8 — Analyzer Framework & Alerts (February 20, 2026)

### What It Does

Automated alerting engine with 6 built-in analyzers that scan dataset rows for suspicious activity and produce scored, MITRE-tagged alerts. Full alert lifecycle (new → acknowledged → in-progress → resolved / false-positive), bulk operations, and configurable alert rules.

### Backend

**New service** — `backend/app/services/analyzers.py` (~350 lines):
- `BaseAnalyzer` ABC with `name`, `description`, and `async analyze(rows)` method
- 6 built-in analyzers:
  - **EntropyAnalyzer** — Shannon entropy on command_line/url/path fields, threshold 4.5, maps to T1027 (Obfuscated Files or Information)
  - **SuspiciousCommandAnalyzer** — 19 regex patterns (mimikatz, encoded PowerShell, schtasks, psexec, vssadmin, etc.) with per-pattern MITRE mappings
  - **NetworkAnomalyAnalyzer** — Beaconing detection (dst IP frequency), suspicious ports (4444, 5555, etc.), large transfers (>10 MB), maps to T1071/T1048/T1571
  - **FrequencyAnomalyAnalyzer** — Flags values <1% occurrence in process_name/username/event_type fields
  - **AuthAnomalyAnalyzer** — Brute force (>5 failed logins per user), unusual logon types (3=network, 10=RDP), maps to T1110/T1021
  - **PersistenceAnalyzer** — Registry Run keys, services, Winlogon, IFEO patterns, maps to T1547/T1543/T1546
- `run_all_analyzers(rows, analyzers?)` — runs all or selected analyzers, returns sorted `AlertCandidate` list

**New API route** — `backend/app/api/routes/alerts.py` (~300 lines):
- `GET /api/alerts` — list with filters (status, severity, analyzer, hunt_id, dataset_id)
- `GET /api/alerts/stats` — severity/status/analyzer/MITRE breakdowns
- `GET /api/alerts/{id}`, `PUT /api/alerts/{id}`, `DELETE /api/alerts/{id}`
- `POST /api/alerts/bulk-update` — bulk status changes on selected alert IDs
- `GET /api/alerts/analyzers/list` — available analyzer metadata
- `POST /api/alerts/analyze` — run analyzers on a dataset/hunt, auto-creates Alert records
- Alert Rules CRUD: `GET /api/alerts/rules/list`, `POST /api/alerts/rules`, `PUT /api/alerts/rules/{id}`, `DELETE /api/alerts/rules/{id}`

**New ORM models** — `backend/app/db/models.py`:
- `Alert` — 18 fields (id, title, description, severity, status, analyzer, score, evidence JSON, mitre_technique, tags JSON, hunt_id FK, dataset_id FK, case_id FK, assignee, acknowledged_at, resolved_at, timestamps; indexes on severity/status/hunt/dataset)
- `AlertRule` — 10 fields (id, name, description, analyzer, config JSON, severity_override, enabled, hunt_id FK, timestamps; index on analyzer)

**Alembic migration** — `backend/alembic/versions/b4c2d3e5f6a7_add_alerts_and_alert_rules.py`

### Frontend

**New component** — `frontend/src/components/AlertPanel.tsx` (~350 lines):
- **Alerts tab**: MUI DataGrid with severity/status chips, score, MITRE technique; checkbox selection for bulk actions (acknowledge / resolve / false-positive); click → detail dialog with evidence JSON viewer
- **Stats tab**: Cards for total, per-severity counts, status/analyzer breakdowns, top MITRE techniques
- **Rules tab**: Rule cards with enable/disable switch, delete; create rule dialog with analyzer selector
- Selector bar: Hunt + Dataset pickers, "Run Analyzers" button, severity/status filters

**API client** — `frontend/src/api/client.ts`:
- Added `AlertData`, `AlertStats`, `AlertRuleData`, `AnalyzerInfo`, `AnalyzeResult` interfaces
- Added `alerts` namespace with full CRUD + analyze + rules methods

**App integration** — `frontend/src/App.tsx`:
- New nav item: **Alerts** with `NotificationsActiveIcon`, route `/alerts`

### Files

| File | Change |
|------|--------|
| `backend/app/services/analyzers.py` | **New** — 6 analyzers + runner |
| `backend/app/api/routes/alerts.py` | **New** — alerts API (CRUD, stats, bulk, rules) |
| `backend/app/db/models.py` | Added `Alert` + `AlertRule` models |
| `backend/alembic/versions/b4c2d3e5f6a7_...py` | **New** — alerts migration |
| `frontend/src/components/AlertPanel.tsx` | **New** — alerts dashboard |
| `frontend/src/api/client.ts` | Added alert types + `alerts` namespace |
| `frontend/src/App.tsx` | Added Alerts nav + route |

---

## 12. Phase 9 — Investigation Notebooks & Playbooks (February 20, 2026)

### What It Does

Cell-based investigation notebooks (markdown / query / code) for documenting hunts, plus a playbook engine with 4 built-in response templates and step-by-step execution tracking.

### Backend

**New service** — `backend/app/services/playbook.py` (~250 lines):
- `NotebookCell` dataclass + `validate_notebook_cells()` helper
- 4 built-in playbook templates:
  - **Suspicious Process Investigation** (6 steps): identify → process tree → network → analyzers → MITRE → document
  - **Lateral Movement Hunt** (5 steps): remote tools → auth anomaly → network anomaly → knowledge graph → escalate
  - **Data Exfiltration Check** (5 steps): large transfers → DNS → timeline → correlate → MITRE + document
  - **Ransomware Triage** (5 steps): indicators search → all analyzers → persistence → LLM deep → critical case
- Each step: order, title, description, action, action_config, expected_outcome

**New API route** — `backend/app/api/routes/notebooks.py` (~280 lines):
- Notebook CRUD: `GET /api/notebooks`, `GET /api/notebooks/{id}`, `POST /api/notebooks`, `PUT /api/notebooks/{id}`, `DELETE /api/notebooks/{id}`
- Cell operations: `POST /api/notebooks/{id}/cells/upsert`, `DELETE /api/notebooks/{id}/cells/{cell_id}`
- Playbook endpoints: `GET /api/notebooks/playbooks/templates`, `GET /api/notebooks/playbooks/templates/{name}`, `POST /api/notebooks/playbooks/start`, `GET /api/notebooks/playbooks/runs`, `GET /api/notebooks/playbooks/runs/{id}`, `POST /api/notebooks/playbooks/runs/{id}/complete-step`, `POST /api/notebooks/playbooks/runs/{id}/abort`

**New ORM models** — `backend/app/db/models.py`:
- `Notebook` — 10 fields (id, title, description, cells JSON, hunt_id FK, case_id FK, owner_id FK, tags JSON, timestamps; index on hunt_id)
- `PlaybookRun` — 12 fields (id, playbook_name, status, current_step, total_steps, step_results JSON, hunt_id FK, case_id FK, started_by, timestamps, completed_at; indexes on hunt_id/status)

**Alembic migration** — `backend/alembic/versions/c5d3e4f6a7b8_add_notebooks_and_playbook_runs.py`

### Frontend

**New component** — `frontend/src/components/InvestigationNotebook.tsx` (~280 lines):
- List view: Grid of notebook cards with title, description, cell count, tags, open/delete
- Detail view: Cell-based editor with markdown/query/code cell types
- Markdown cells render via ReactMarkdown + remarkGfm; code/query cells as monospace pre blocks
- Edit mode: multiline TextField with Ctrl+S save shortcut
- Cell operations: add (markdown/query/code), edit, save, delete, move up/down

**New component** — `frontend/src/components/PlaybookManager.tsx` (~280 lines):
- **Templates tab**: Grid of template cards with category chips, tags, step count; view detail (MUI Stepper showing all steps) or start new run
- **Runs tab**: List of active/completed runs with progress bars
- Active run view: Vertical MUI Stepper with step completion, notes field, skip/abort, LinearProgress

**API client** — `frontend/src/api/client.ts`:
- Added `NotebookCell`, `NotebookData`, `PlaybookTemplate`, `PlaybookStep`, `PlaybookTemplateDetail`, `PlaybookRunData` interfaces
- Added `notebooks` namespace (CRUD + cell ops) and `playbooks` namespace (templates, runs, step-complete, abort)

**App integration** — `frontend/src/App.tsx`:
- New nav items: **Notebooks** (`MenuBookIcon`, `/notebooks`) and **Playbooks** (`PlaylistPlayIcon`, `/playbooks`)

### Files

| File | Change |
|------|--------|
| `backend/app/services/playbook.py` | **New** — 4 playbook templates + cell validation |
| `backend/app/api/routes/notebooks.py` | **New** — notebooks + playbooks API |
| `backend/app/db/models.py` | Added `Notebook` + `PlaybookRun` models |
| `backend/alembic/versions/c5d3e4f6a7b8_...py` | **New** — notebooks migration |
| `frontend/src/components/InvestigationNotebook.tsx` | **New** — cell-based notebook editor |
| `frontend/src/components/PlaybookManager.tsx` | **New** — playbook template browser + run stepper |
| `frontend/src/api/client.ts` | Added notebook + playbook types + namespaces |
| `frontend/src/App.tsx` | Added Notebooks + Playbooks nav + routes |

---

## 13. Docker Build Fixes (February 20, 2026)

Several issues were resolved to get the full 22-page frontend and updated backend deployed in Docker Compose.

### npm / TypeScript Fixes

| Issue | Fix |
|-------|-----|
| `npm ci` failing: "Missing: yaml@2.8.2 from lock file" | Installed `yaml@2` — `postcss-load-config` (from tailwindcss) required `^2.4.2` but only `1.10.2` was present |
| `GridRowSelectionModel` cast to `string[]` | MUI X DataGrid v8 changed to `{ type, ids: Set }` — fixed with `Array.from(model.ids)` |
| Recharts `formatter` type mismatch | Changed explicit `number`/`string` params to `any` in `Dashboard.tsx` |
| Missing declarations for `cytoscape-dagre` / `cytoscape-cola` | Created `frontend/src/declarations.d.ts` |
| Missing `HuntOut` type export | Added `export type HuntOut = Hunt` alias in `client.ts` |
| `cytoscape.Stylesheet` no longer exists | Renamed to `cytoscape.StylesheetStyle` in ProcessTree, StorylineGraph, KnowledgeGraph |

### Backend Startup Fixes

| Issue | Fix |
|-------|-----|
| `init_db()` crash: "table cases already exists" | Rewrote to inspect existing tables and only create missing ones |
| Alembic migration replay on startup | DB had all tables (from `init_db()`) but Alembic was stamped at `98ab619418bc` — ran `alembic stamp head` to sync to `c5d3e4f6a7b8` |

### Files Modified

| File | Change |
|------|--------|
| `frontend/package.json` / `package-lock.json` | Added `yaml@2` dependency |
| `frontend/src/declarations.d.ts` | **New** — ambient module declarations |
| `frontend/src/api/client.ts` | Added `HuntOut` type alias |
| `frontend/src/components/AlertPanel.tsx` | Fixed `GridRowSelectionModel` handling |
| `frontend/src/components/Dashboard.tsx` | Fixed Recharts formatter types |
| `frontend/src/components/ProcessTree.tsx` | `Stylesheet` → `StylesheetStyle` |
| `frontend/src/components/StorylineGraph.tsx` | `Stylesheet` → `StylesheetStyle` |
| `frontend/src/components/KnowledgeGraph.tsx` | `Stylesheet` → `StylesheetStyle` |
| `backend/app/db/engine.py` | Safe `init_db()` with inspector |

---

## Current Navigation (22 pages)

Dashboard · Hunts · Datasets · Upload · Agent · Analysis · Annotations · Hypotheses · Correlation · Network Map · Net Picture · Proc Tree · Storyline · Timeline · Search · MITRE Map · Knowledge · Cases · **Alerts** · **Notebooks** · **Playbooks** · AUP Scanner

## Deployment

```
docker compose build
docker compose up -d
# Backend: http://localhost:8000 (healthy)
# Frontend: http://localhost:3000 (200 OK)
```

## Alembic Migration Chain

```
9790f482da06  (initial schema)
    ↓
98ab619418bc  (keyword themes + keywords)
    ↓
a3b1c2d4e5f6  (cases + activity logs)
    ↓
b4c2d3e5f6a7  (alerts + alert rules)
    ↓
c5d3e4f6a7b8  (notebooks + playbook runs)  ← HEAD
```

---

## 14. Process Tree — HTTP 500 Fix (February 20, 2026)

**Request:** "process tree: HTTP 500"

**Root Cause:** `MissingGreenlet` error in `_fetch_rows` — async SQLAlchemy lazy-loading the `dataset` relationship on `DatasetRow` outside a greenlet context.

**Fix (`backend/app/services/process_tree.py`):**
- Added `selectinload(DatasetRow.dataset)` to the `_fetch_rows` query so the relationship is eagerly loaded within the async session
- Endpoint now returns data correctly (verified: 3,908 processes for full hunt)

---

## 15. Process Tree — UX Rewrite (February 20, 2026)

**Request:** "proctree view is horrible… there are 3908 processes and I can't see / zoom in to see and when I do click on one the resolution changes to show the data on the right. Ideally I'd like another dropdown to pick a host."

**Complete rewrite of `frontend/src/components/ProcessTree.tsx` (~520 lines):**

- **Host dropdown**: Autocomplete populated by extracting unique hostnames from tree data (82 hosts)
- **Server-side hostname filtering**: API `?hostname=` param reduces returned data per view
- **Grid layout fallback**: When edges < 10% of nodes (e.g. test data with no parent-child relationships), uses grid layout instead of dagre
- **Overlay detail panel**: Absolute-positioned panel on click — no longer reflows the graph
- **ResizeObserver**: Keeps Cytoscape canvas in sync with container size changes
- **Search/highlight**: Filter processes by name or PID
- **Zoom controls**: Fit, zoom-in, zoom-out buttons

---

## 16. Process Tree — White Screen Crash Fix (February 20, 2026)

**Request:** "I picked a different host and the screen went white"

**Root Cause:** Cytoscape's `destroy()` removed `<canvas>` elements that were children of the same DOM node React was managing, causing `NotFoundError: Failed to execute 'removeChild' on 'Node'` when React tried to reconcile.

**Fix (`frontend/src/components/ProcessTree.tsx`):**
- Separated Cytoscape container into a plain `<div>` with zero React children
- Loading spinner and placeholder text are now sibling overlays (not children of the Cytoscape div)
- Added explicit `cyRef.current = null` after `destroy()`
- Cleanup on unmount prevents stale references
- Verified: switching between hosts (DC-01 → EXEC-WS-039 → ENG-WS-052) works with 0 console errors

---

## 17. LLM Analysis — Response Parsing Fix (February 20, 2026)

**Request:** "llm analysis: HTTP 500 — searching for evidence of adult site access"

**Root Cause Chain:**

1. **`AttributeError: 'dict' object has no attribute 'strip'`** — `OllamaProvider.generate()` returns a dict (`{"response": "<llm text>", "model": ..., ...}`), but `_parse_analysis` expected a string.

2. **Wrong dict key extraction** — Initial dict-handling fix looked for `raw.get("analysis")` but Ollama's `/api/generate` endpoint puts the LLM text in the `"response"` key.

3. **JSON parsing failures** — The 70B model sometimes produces slightly malformed JSON (trailing commas, etc.) that `json.loads` rejects.

**Fixes (`backend/app/services/llm_analysis.py`):**

| Change | Detail |
|--------|--------|
| Dict response extraction | `raw.get("response")` instead of `raw.get("analysis")` — correctly extracts LLM text from Ollama API dict |
| Robust JSON parsing | New `_extract_json_candidates()` generator: tries full text, then outermost `{…}` block, then trailing-comma-fixed variant |
| Reduced prompt size | `max_sample` 50 → 20 rows, `max_chars` 8000 → 6000 |
| Reduced row limit | `/llm-analyze` endpoint loads 2000 rows (was 5000) |
| Timeout | `asyncio.wait_for(..., timeout=300)` wraps the LLM call — returns graceful "timed out" message instead of hanging |
| Debug logging | `_parse_analysis` logs extraction source, text length, parse success/failure with error details |

**Results:**
- Quick mode (llama3.1:latest on roadrunner): 18s, confidence 0.85, risk score 65, 3 key findings — all structured fields populated
- Deep mode (llama3.1:70b on wile): 128–185s, full analysis returned — JSON parsing succeeds when model produces valid JSON, falls back to plain text otherwise

---

## 18. Version Bump — 0.3.0 → 0.4.0 (February 20, 2026)

| File | Change |
|------|--------|
| `backend/app/config.py` | `APP_VERSION` 0.3.0 → 0.4.0 |
| `frontend/package.json` | `version` 0.1.0 → 0.4.0 |

---

## Files Modified This Session (Sections 14–18)

| File | Change |
|------|--------|
| `backend/app/services/process_tree.py` | Added `selectinload(DatasetRow.dataset)` to `_fetch_rows` |
| `frontend/src/components/ProcessTree.tsx` | Complete rewrite: host dropdown, grid layout, overlay panel, Cytoscape DOM separation |
| `backend/app/services/llm_analysis.py` | Fixed dict response extraction, robust JSON parsing, reduced prompt, added timeout |
| `backend/app/api/routes/analysis.py` | Row limit 5000 → 2000 |
| `backend/app/config.py` | Version 0.3.0 → 0.4.0 |
| `frontend/package.json` | Version 0.1.0 → 0.4.0 |

## Deployment

```
docker compose up -d --build backend
# Backend: http://localhost:8000 (healthy, v0.4.0)
# Frontend: http://localhost:3000 (200 OK)
```