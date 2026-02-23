"""Process tree and storyline graph builder.

Extracts parent→child process relationships from dataset rows and builds
hierarchical trees.  Also builds attack-storyline graphs connecting events
by host → process → network activity → file activity chains.
"""

import logging
from collections import defaultdict
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────

_JUNK = frozenset({"", "N/A", "n/a", "-", "—", "null", "None", "none", "unknown"})


def _clean(val: Any) -> str | None:
    """Return cleaned string or None for junk values."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s in _JUNK else s


# ── Process Tree ──────────────────────────────────────────────────────


class ProcessNode:
    """A single process in the tree."""

    __slots__ = (
        "pid", "ppid", "name", "command_line", "username", "hostname",
        "timestamp", "dataset_name", "row_index", "children", "extra",
    )

    def __init__(self, **kw: Any):
        self.pid: str = kw.get("pid", "")
        self.ppid: str = kw.get("ppid", "")
        self.name: str = kw.get("name", "")
        self.command_line: str = kw.get("command_line", "")
        self.username: str = kw.get("username", "")
        self.hostname: str = kw.get("hostname", "")
        self.timestamp: str = kw.get("timestamp", "")
        self.dataset_name: str = kw.get("dataset_name", "")
        self.row_index: int = kw.get("row_index", -1)
        self.children: list["ProcessNode"] = []
        self.extra: dict = kw.get("extra", {})

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "ppid": self.ppid,
            "name": self.name,
            "command_line": self.command_line,
            "username": self.username,
            "hostname": self.hostname,
            "timestamp": self.timestamp,
            "dataset_name": self.dataset_name,
            "row_index": self.row_index,
            "children": [c.to_dict() for c in self.children],
            "extra": self.extra,
        }


async def build_process_tree(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    hostname_filter: str | None = None,
) -> list[dict]:
    """Build process trees from dataset rows.

    Returns a list of root-level process nodes (forest).
    """
    rows = await _fetch_rows(db, dataset_id=dataset_id, hunt_id=hunt_id)
    if not rows:
        return []

    # Group processes by (hostname, pid) → node
    nodes_by_key: dict[tuple[str, str], ProcessNode] = {}
    nodes_list: list[ProcessNode] = []

    for row_obj in rows:
        data = row_obj.normalized_data or row_obj.data
        pid = _clean(data.get("pid"))
        if not pid:
            continue

        ppid = _clean(data.get("ppid")) or ""
        hostname = _clean(data.get("hostname")) or "unknown"

        if hostname_filter and hostname.lower() != hostname_filter.lower():
            continue

        node = ProcessNode(
            pid=pid,
            ppid=ppid,
            name=_clean(data.get("process_name")) or _clean(data.get("name")) or "",
            command_line=_clean(data.get("command_line")) or "",
            username=_clean(data.get("username")) or "",
            hostname=hostname,
            timestamp=_clean(data.get("timestamp")) or "",
            dataset_name=row_obj.dataset.name if row_obj.dataset else "",
            row_index=row_obj.row_index,
            extra={
                k: str(v)
                for k, v in data.items()
                if k not in {"pid", "ppid", "process_name", "name", "command_line",
                             "username", "hostname", "timestamp"}
                and v is not None and str(v).strip() not in _JUNK
            },
        )

        key = (hostname, pid)
        # Keep the first occurrence (earlier in data) or overwrite if deeper info
        if key not in nodes_by_key:
            nodes_by_key[key] = node
            nodes_list.append(node)

    # Link parent → child
    roots: list[ProcessNode] = []
    for node in nodes_list:
        parent_key = (node.hostname, node.ppid)
        parent = nodes_by_key.get(parent_key)
        if parent and parent is not node:
            parent.children.append(node)
        else:
            roots.append(node)

    return [r.to_dict() for r in roots]


# ── Storyline / Attack Graph ─────────────────────────────────────────


async def build_storyline(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    hostname_filter: str | None = None,
) -> dict:
    """Build a CrowdStrike-style storyline graph.

    Nodes represent events (process start, network connection, file write, etc.)
    Edges represent causal / temporal relationships.

    Returns a Cytoscape-compatible elements dict {nodes: [...], edges: [...]}.
    """
    rows = await _fetch_rows(db, dataset_id=dataset_id, hunt_id=hunt_id)
    if not rows:
        return {"nodes": [], "edges": [], "summary": {}}

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()
    host_events: dict[str, list[dict]] = defaultdict(list)

    for row_obj in rows:
        data = row_obj.normalized_data or row_obj.data
        hostname = _clean(data.get("hostname")) or "unknown"

        if hostname_filter and hostname.lower() != hostname_filter.lower():
            continue

        event_type = _classify_event(data)
        node_id = f"{row_obj.dataset_id}_{row_obj.row_index}"
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)

        label = _build_label(data, event_type)
        severity = _estimate_severity(data, event_type)

        node = {
            "data": {
                "id": node_id,
                "label": label,
                "event_type": event_type,
                "hostname": hostname,
                "timestamp": _clean(data.get("timestamp")) or "",
                "pid": _clean(data.get("pid")) or "",
                "ppid": _clean(data.get("ppid")) or "",
                "process_name": _clean(data.get("process_name")) or "",
                "command_line": _clean(data.get("command_line")) or "",
                "username": _clean(data.get("username")) or "",
                "src_ip": _clean(data.get("src_ip")) or "",
                "dst_ip": _clean(data.get("dst_ip")) or "",
                "dst_port": _clean(data.get("dst_port")) or "",
                "file_path": _clean(data.get("file_path")) or "",
                "severity": severity,
                "dataset_id": row_obj.dataset_id,
                "row_index": row_obj.row_index,
            },
        }
        nodes.append(node)
        host_events[hostname].append(node["data"])

    # Build edges: parent→child (by pid/ppid) and temporal sequence per host
    pid_lookup: dict[tuple[str, str], str] = {}  # (host, pid) → node_id
    for node in nodes:
        d = node["data"]
        if d["pid"]:
            pid_lookup[(d["hostname"], d["pid"])] = d["id"]

    for node in nodes:
        d = node["data"]
        if d["ppid"]:
            parent_id = pid_lookup.get((d["hostname"], d["ppid"]))
            if parent_id and parent_id != d["id"]:
                edges.append({
                    "data": {
                        "id": f"e_{parent_id}_{d['id']}",
                        "source": parent_id,
                        "target": d["id"],
                        "relationship": "spawned",
                    }
                })

    # Temporal edges within each host (sorted by timestamp)
    for hostname, events in host_events.items():
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
        for i in range(len(sorted_events) - 1):
            src = sorted_events[i]
            tgt = sorted_events[i + 1]
            edge_id = f"t_{src['id']}_{tgt['id']}"
            # Avoid duplicate edges
            if not any(e["data"]["id"] == edge_id for e in edges):
                edges.append({
                    "data": {
                        "id": edge_id,
                        "source": src["id"],
                        "target": tgt["id"],
                        "relationship": "temporal",
                    }
                })

    # Summary stats
    type_counts: dict[str, int] = defaultdict(int)
    for n in nodes:
        type_counts[n["data"]["event_type"]] += 1

    summary = {
        "total_events": len(nodes),
        "total_edges": len(edges),
        "hosts": list(host_events.keys()),
        "event_types": dict(type_counts),
    }

    return {"nodes": nodes, "edges": edges, "summary": summary}


# ── Risk scoring for dashboard ────────────────────────────────────────

async def compute_risk_scores(
    db: AsyncSession,
    hunt_id: str | None = None,
) -> dict:
    """Compute per-host risk scores from anomaly signals in datasets.

    Returns {hosts: [{hostname, score, signals, ...}], overall_score, ...}
    """
    rows = await _fetch_rows(db, hunt_id=hunt_id)
    if not rows:
        return {"hosts": [], "overall_score": 0, "total_events": 0,
                "severity_breakdown": {}}

    host_signals: dict[str, dict] = defaultdict(
        lambda: {"hostname": "", "score": 0, "signals": [],
                 "event_count": 0, "process_count": 0,
                 "network_count": 0, "file_count": 0}
    )

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

    for row_obj in rows:
        data = row_obj.normalized_data or row_obj.data
        hostname = _clean(data.get("hostname")) or "unknown"
        entry = host_signals[hostname]
        entry["hostname"] = hostname
        entry["event_count"] += 1

        event_type = _classify_event(data)
        severity = _estimate_severity(data, event_type)
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Count event types
        if event_type == "process":
            entry["process_count"] += 1
        elif event_type == "network":
            entry["network_count"] += 1
        elif event_type == "file":
            entry["file_count"] += 1

        # Risk signals
        cmd = (_clean(data.get("command_line")) or "").lower()
        proc = (_clean(data.get("process_name")) or "").lower()

        # Detect suspicious patterns
        sus_patterns = [
            ("powershell -enc", 8, "Encoded PowerShell"),
            ("invoke-expression", 7, "PowerShell IEX"),
            ("invoke-webrequest", 6, "PowerShell WebRequest"),
            ("certutil -urlcache", 8, "Certutil download"),
            ("bitsadmin /transfer", 7, "BITS transfer"),
            ("regsvr32 /s /n /u", 8, "Regsvr32 squiblydoo"),
            ("mshta ", 7, "MSHTA execution"),
            ("wmic process", 6, "WMIC process enum"),
            ("net user", 5, "User enumeration"),
            ("whoami", 4, "Whoami recon"),
            ("mimikatz", 10, "Mimikatz detected"),
            ("procdump", 7, "Process dumping"),
            ("psexec", 7, "PsExec lateral movement"),
        ]

        for pattern, score_add, signal_name in sus_patterns:
            if pattern in cmd or pattern in proc:
                entry["score"] += score_add
                if signal_name not in entry["signals"]:
                    entry["signals"].append(signal_name)

        # External connections score
        dst_ip = _clean(data.get("dst_ip")) or ""
        if dst_ip and not dst_ip.startswith(("10.", "192.168.", "172.")):
            entry["score"] += 1
            if "External connections" not in entry["signals"]:
                entry["signals"].append("External connections")

    # Normalize scores (0-100)
    max_score = max((h["score"] for h in host_signals.values()), default=1)
    if max_score > 0:
        for entry in host_signals.values():
            entry["score"] = min(round((entry["score"] / max_score) * 100), 100)

    hosts = sorted(host_signals.values(), key=lambda h: h["score"], reverse=True)
    overall = round(sum(h["score"] for h in hosts) / max(len(hosts), 1))

    return {
        "hosts": hosts,
        "overall_score": overall,
        "total_events": sum(h["event_count"] for h in hosts),
        "severity_breakdown": severity_counts,
    }


# ── Internal helpers ──────────────────────────────────────────────────


async def _fetch_rows(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    limit: int = 50_000,
) -> Sequence[DatasetRow]:
    """Fetch dataset rows, optionally filtered by dataset or hunt."""
    stmt = (
        select(DatasetRow)
        .join(Dataset)
        .options(selectinload(DatasetRow.dataset))
    )

    if dataset_id:
        stmt = stmt.where(DatasetRow.dataset_id == dataset_id)
    elif hunt_id:
        stmt = stmt.where(Dataset.hunt_id == hunt_id)
    else:
        # No filter — limit to prevent OOM
        pass

    stmt = stmt.order_by(DatasetRow.row_index).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


def _classify_event(data: dict) -> str:
    """Classify a row as process / network / file / registry / other."""
    if _clean(data.get("pid")) or _clean(data.get("process_name")):
        if _clean(data.get("dst_ip")) or _clean(data.get("dst_port")):
            return "network"
        if _clean(data.get("file_path")):
            return "file"
        return "process"
    if _clean(data.get("dst_ip")) or _clean(data.get("src_ip")):
        return "network"
    if _clean(data.get("file_path")):
        return "file"
    if _clean(data.get("registry_key")):
        return "registry"
    return "other"


def _build_label(data: dict, event_type: str) -> str:
    """Build a concise node label for storyline display."""
    name = _clean(data.get("process_name")) or ""
    pid = _clean(data.get("pid")) or ""
    dst = _clean(data.get("dst_ip")) or ""
    port = _clean(data.get("dst_port")) or ""
    fpath = _clean(data.get("file_path")) or ""

    if event_type == "process":
        return f"{name} (PID {pid})" if pid else name or "process"
    elif event_type == "network":
        target = f"{dst}:{port}" if dst and port else dst or port
        return f"{name} → {target}" if name else target or "network"
    elif event_type == "file":
        fname = fpath.split("\\")[-1].split("/")[-1] if fpath else ""
        return f"{name} → {fname}" if name else fname or "file"
    elif event_type == "registry":
        return _clean(data.get("registry_key")) or "registry"
    return name or "event"


def _estimate_severity(data: dict, event_type: str) -> str:
    """Rough heuristic severity estimate."""
    cmd = (_clean(data.get("command_line")) or "").lower()
    proc = (_clean(data.get("process_name")) or "").lower()

    # Critical indicators
    critical_kw = ["mimikatz", "cobalt", "meterpreter", "empire", "bloodhound"]
    if any(k in cmd or k in proc for k in critical_kw):
        return "critical"

    # High indicators
    high_kw = ["powershell -enc", "certutil -urlcache", "regsvr32", "mshta",
               "bitsadmin", "psexec", "procdump"]
    if any(k in cmd for k in high_kw):
        return "high"

    # Medium indicators
    medium_kw = ["invoke-", "wmic", "net user", "net group", "schtasks",
                 "reg add", "sc create"]
    if any(k in cmd for k in medium_kw):
        return "medium"

    # Low: recon
    low_kw = ["whoami", "ipconfig", "systeminfo", "tasklist", "netstat"]
    if any(k in cmd for k in low_kw):
        return "low"

    return "info"
