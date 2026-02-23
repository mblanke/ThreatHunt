"""
MITRE ATT&CK mapping service.

Maps dataset events to ATT&CK techniques using pattern-based heuristics.
Uses the enterprise-attack matrix (embedded patterns for offline use).
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)

# ── ATT&CK Technique Patterns ────────────────────────────────────────
# Subset of enterprise-attack techniques with detection patterns.
# Each entry: (technique_id, name, tactic, patterns_list)

TECHNIQUE_PATTERNS: list[tuple[str, str, str, list[str]]] = [
    # Initial Access
    ("T1566", "Phishing", "initial-access", [
        r"phish", r"\.hta\b", r"\.lnk\b", r"mshta\.exe", r"outlook.*attachment",
    ]),
    ("T1190", "Exploit Public-Facing Application", "initial-access", [
        r"exploit", r"CVE-\d{4}", r"vulnerability", r"webshell",
    ]),

    # Execution
    ("T1059.001", "PowerShell", "execution", [
        r"powershell", r"pwsh", r"-enc\b", r"-encodedcommand",
        r"invoke-expression", r"iex\b", r"bypass\b.*execution",
    ]),
    ("T1059.003", "Windows Command Shell", "execution", [
        r"cmd\.exe", r"/c\s+", r"command\.com",
    ]),
    ("T1059.005", "Visual Basic", "execution", [
        r"wscript", r"cscript", r"\.vbs\b", r"\.vbe\b",
    ]),
    ("T1047", "Windows Management Instrumentation", "execution", [
        r"wmic\b", r"winmgmt", r"wmi\b",
    ]),
    ("T1053.005", "Scheduled Task", "execution", [
        r"schtasks", r"at\.exe", r"taskschd",
    ]),
    ("T1204", "User Execution", "execution", [
        r"user.*click", r"open.*attachment", r"macro",
    ]),

    # Persistence
    ("T1547.001", "Registry Run Keys", "persistence", [
        r"CurrentVersion\\Run", r"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        r"reg\s+add.*\\Run",
    ]),
    ("T1543.003", "Windows Service", "persistence", [
        r"sc\s+create", r"new-service", r"service.*install",
    ]),
    ("T1136", "Create Account", "persistence", [
        r"net\s+user\s+/add", r"new-localuser", r"useradd",
    ]),
    ("T1053.005", "Scheduled Task/Job", "persistence", [
        r"schtasks\s+/create", r"crontab",
    ]),

    # Privilege Escalation
    ("T1548.002", "Bypass User Access Control", "privilege-escalation", [
        r"eventvwr", r"fodhelper", r"uac.*bypass", r"computerdefaults",
    ]),
    ("T1134", "Access Token Manipulation", "privilege-escalation", [
        r"token.*impersonat", r"runas", r"adjusttokenprivileges",
    ]),

    # Defense Evasion
    ("T1070.001", "Clear Windows Event Logs", "defense-evasion", [
        r"wevtutil\s+cl", r"clear-eventlog", r"clearlog",
    ]),
    ("T1562.001", "Disable or Modify Tools", "defense-evasion", [
        r"tamper.*protection", r"disable.*defender", r"set-mppreference",
        r"disable.*firewall",
    ]),
    ("T1027", "Obfuscated Files or Information", "defense-evasion", [
        r"base64", r"-enc\b", r"certutil.*-decode", r"frombase64",
    ]),
    ("T1036", "Masquerading", "defense-evasion", [
        r"rename.*\.exe", r"masquerad", r"svchost.*unusual",
    ]),
    ("T1055", "Process Injection", "defense-evasion", [
        r"inject", r"createremotethread", r"ntcreatethreadex",
        r"virtualalloc", r"writeprocessmemory",
    ]),

    # Credential Access
    ("T1003.001", "LSASS Memory", "credential-access", [
        r"mimikatz", r"sekurlsa", r"lsass", r"procdump.*lsass",
    ]),
    ("T1003.003", "NTDS", "credential-access", [
        r"ntds\.dit", r"vssadmin.*shadow", r"ntdsutil",
    ]),
    ("T1110", "Brute Force", "credential-access", [
        r"brute.*force", r"failed.*login.*\d{3,}", r"hydra", r"medusa",
    ]),
    ("T1558.003", "Kerberoasting", "credential-access", [
        r"kerberoast", r"invoke-kerberoast", r"GetUserSPNs",
    ]),

    # Discovery
    ("T1087", "Account Discovery", "discovery", [
        r"net\s+user", r"net\s+localgroup", r"get-aduser",
    ]),
    ("T1082", "System Information Discovery", "discovery", [
        r"systeminfo", r"hostname", r"ver\b",
    ]),
    ("T1083", "File and Directory Discovery", "discovery", [
        r"dir\s+/s", r"tree\s+/f", r"get-childitem.*-recurse",
    ]),
    ("T1057", "Process Discovery", "discovery", [
        r"tasklist", r"get-process", r"ps\s+aux",
    ]),
    ("T1018", "Remote System Discovery", "discovery", [
        r"net\s+view", r"ping\s+-", r"arp\s+-a", r"nslookup",
    ]),
    ("T1016", "System Network Configuration Discovery", "discovery", [
        r"ipconfig", r"ifconfig", r"netstat",
    ]),

    # Lateral Movement
    ("T1021.001", "Remote Desktop Protocol", "lateral-movement", [
        r"rdp\b", r"mstsc", r"3389", r"remote\s+desktop",
    ]),
    ("T1021.002", "SMB/Windows Admin Shares", "lateral-movement", [
        r"\\\\.*\\(c|admin)\$", r"psexec", r"smbclient", r"net\s+use",
    ]),
    ("T1021.006", "Windows Remote Management", "lateral-movement", [
        r"winrm", r"enter-pssession", r"invoke-command.*-computername",
        r"wsman", r"5985|5986",
    ]),
    ("T1570", "Lateral Tool Transfer", "lateral-movement", [
        r"copy.*\\\\", r"xcopy.*\\\\", r"robocopy",
    ]),

    # Collection
    ("T1560", "Archive Collected Data", "collection", [
        r"compress-archive", r"7z\.exe", r"rar\s+a", r"tar\s+-[cz]",
    ]),
    ("T1005", "Data from Local System", "collection", [
        r"type\s+.*password", r"findstr.*password", r"select-string.*credential",
    ]),

    # Command and Control
    ("T1071.001", "Web Protocols", "command-and-control", [
        r"http[s]?://\d+\.\d+\.\d+\.\d+", r"curl\b", r"wget\b",
        r"invoke-webrequest", r"beacon",
    ]),
    ("T1573", "Encrypted Channel", "command-and-control", [
        r"ssl\b", r"tls\b", r"encrypted.*tunnel", r"stunnel",
    ]),
    ("T1105", "Ingress Tool Transfer", "command-and-control", [
        r"certutil.*-urlcache", r"bitsadmin.*transfer",
        r"downloadfile", r"invoke-webrequest.*-outfile",
    ]),
    ("T1219", "Remote Access Software", "command-and-control", [
        r"teamviewer", r"anydesk", r"logmein", r"vnc",
    ]),

    # Exfiltration
    ("T1048", "Exfiltration Over Alternative Protocol", "exfiltration", [
        r"dns.*tunnel", r"exfil", r"icmp.*tunnel",
    ]),
    ("T1041", "Exfiltration Over C2 Channel", "exfiltration", [
        r"upload.*c2", r"exfil.*http",
    ]),
    ("T1567", "Exfiltration Over Web Service", "exfiltration", [
        r"mega\.nz", r"dropbox", r"pastebin", r"transfer\.sh",
    ]),

    # Impact
    ("T1486", "Data Encrypted for Impact", "impact", [
        r"ransomware", r"encrypt.*files", r"\.locked\b", r"ransom",
    ]),
    ("T1489", "Service Stop", "impact", [
        r"sc\s+stop", r"net\s+stop", r"stop-service",
    ]),
    ("T1529", "System Shutdown/Reboot", "impact", [
        r"shutdown\s+/[rs]", r"restart-computer",
    ]),
]

# Tactic display names and kill-chain order
TACTIC_ORDER = [
    "initial-access", "execution", "persistence", "privilege-escalation",
    "defense-evasion", "credential-access", "discovery", "lateral-movement",
    "collection", "command-and-control", "exfiltration", "impact",
]
TACTIC_NAMES = {
    "initial-access": "Initial Access",
    "execution": "Execution",
    "persistence": "Persistence",
    "privilege-escalation": "Privilege Escalation",
    "defense-evasion": "Defense Evasion",
    "credential-access": "Credential Access",
    "discovery": "Discovery",
    "lateral-movement": "Lateral Movement",
    "collection": "Collection",
    "command-and-control": "Command and Control",
    "exfiltration": "Exfiltration",
    "impact": "Impact",
}


# ── Row fetcher ───────────────────────────────────────────────────────

async def _fetch_rows(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    q = select(DatasetRow).join(Dataset)
    if dataset_id:
        q = q.where(DatasetRow.dataset_id == dataset_id)
    elif hunt_id:
        q = q.where(Dataset.hunt_id == hunt_id)
    q = q.limit(limit)
    result = await db.execute(q)
    return [r.data for r in result.scalars().all()]


# ── Main functions ────────────────────────────────────────────────────

async def map_to_attack(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
) -> dict[str, Any]:
    """
    Map dataset rows to MITRE ATT&CK techniques.
    Returns a matrix-style structure + evidence list.
    """
    rows = await _fetch_rows(db, dataset_id, hunt_id)
    if not rows:
        return {"tactics": [], "techniques": [], "evidence": [], "coverage": {}, "total_rows": 0}

    # Flatten all string values per row for matching
    row_texts: list[str] = []
    for row in rows:
        parts = []
        for v in row.values():
            if v is not None:
                parts.append(str(v).lower())
        row_texts.append(" ".join(parts))

    # Match techniques
    technique_hits: dict[str, list[dict]] = defaultdict(list)  # tech_id -> evidence rows
    technique_meta: dict[str, tuple[str, str]] = {}  # tech_id -> (name, tactic)
    row_techniques: list[set[str]] = [set() for _ in rows]

    for tech_id, tech_name, tactic, patterns in TECHNIQUE_PATTERNS:
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        technique_meta[tech_id] = (tech_name, tactic)
        for i, text in enumerate(row_texts):
            for pat in compiled:
                if pat.search(text):
                    row_techniques[i].add(tech_id)
                    if len(technique_hits[tech_id]) < 10:  # limit evidence
                        # find matching field
                        matched_field = ""
                        matched_value = ""
                        for k, v in rows[i].items():
                            if v and pat.search(str(v).lower()):
                                matched_field = k
                                matched_value = str(v)[:200]
                                break
                        technique_hits[tech_id].append({
                            "row_index": i,
                            "field": matched_field,
                            "value": matched_value,
                            "pattern": pat.pattern,
                        })
                    break  # one pattern match per technique per row is enough

    # Build tactic → technique structure
    tactic_techniques: dict[str, list[dict]] = defaultdict(list)
    for tech_id, evidence_list in technique_hits.items():
        name, tactic = technique_meta[tech_id]
        tactic_techniques[tactic].append({
            "id": tech_id,
            "name": name,
            "count": len(evidence_list),
            "evidence": evidence_list[:5],
        })

    # Build ordered tactics list
    tactics = []
    for tactic_key in TACTIC_ORDER:
        techs = tactic_techniques.get(tactic_key, [])
        tactics.append({
            "id": tactic_key,
            "name": TACTIC_NAMES.get(tactic_key, tactic_key),
            "techniques": sorted(techs, key=lambda t: -t["count"]),
            "total_hits": sum(t["count"] for t in techs),
        })

    # Coverage stats
    covered_tactics = sum(1 for t in tactics if t["total_hits"] > 0)
    total_technique_hits = sum(t["total_hits"] for t in tactics)

    return {
        "tactics": tactics,
        "coverage": {
            "tactics_covered": covered_tactics,
            "tactics_total": len(TACTIC_ORDER),
            "techniques_matched": len(technique_hits),
            "total_evidence": total_technique_hits,
        },
        "total_rows": len(rows),
    }


async def build_knowledge_graph(
    db: AsyncSession,
    dataset_id: str | None = None,
    hunt_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a knowledge graph connecting entities (hosts, users, processes, IPs)
    to MITRE techniques and tactics.
    Returns Cytoscape-compatible nodes + edges.
    """
    rows = await _fetch_rows(db, dataset_id, hunt_id)
    if not rows:
        return {"nodes": [], "edges": [], "stats": {}}

    # Extract entities
    entities: dict[str, set[str]] = defaultdict(set)  # type -> set of values
    row_entity_map: list[list[tuple[str, str]]] = []  # per-row list of (type, value)

    # Field name patterns for entity extraction
    HOST_FIELDS = re.compile(r"hostname|computer|host|machine", re.I)
    USER_FIELDS = re.compile(r"user|account|logon.*name|subject.*name", re.I)
    IP_FIELDS = re.compile(r"src.*ip|dst.*ip|ip.*addr|source.*ip|dest.*ip|remote.*addr", re.I)
    PROC_FIELDS = re.compile(r"process.*name|image|parent.*image|executable|command", re.I)

    for row in rows:
        row_ents: list[tuple[str, str]] = []
        for k, v in row.items():
            if not v or str(v).strip() in ('', '-', 'N/A', 'None'):
                continue
            val = str(v).strip()
            if HOST_FIELDS.search(k):
                entities["host"].add(val)
                row_ents.append(("host", val))
            elif USER_FIELDS.search(k):
                entities["user"].add(val)
                row_ents.append(("user", val))
            elif IP_FIELDS.search(k):
                entities["ip"].add(val)
                row_ents.append(("ip", val))
            elif PROC_FIELDS.search(k):
                # Clean process name
                pname = val.split("\\")[-1].split("/")[-1][:60]
                entities["process"].add(pname)
                row_ents.append(("process", pname))
        row_entity_map.append(row_ents)

    # Map rows to techniques
    row_texts = [" ".join(str(v).lower() for v in row.values() if v) for row in rows]
    row_techniques: list[set[str]] = [set() for _ in rows]
    tech_meta: dict[str, tuple[str, str]] = {}

    for tech_id, tech_name, tactic, patterns in TECHNIQUE_PATTERNS:
        compiled = [re.compile(p, re.I) for p in patterns]
        tech_meta[tech_id] = (tech_name, tactic)
        for i, text in enumerate(row_texts):
            for pat in compiled:
                if pat.search(text):
                    row_techniques[i].add(tech_id)
                    break

    # Build graph
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()
    edge_counter: Counter = Counter()

    # Entity nodes
    TYPE_COLORS = {
        "host": "#3b82f6",
        "user": "#10b981",
        "ip": "#8b5cf6",
        "process": "#f59e0b",
        "technique": "#ef4444",
        "tactic": "#6366f1",
    }
    TYPE_SHAPES = {
        "host": "roundrectangle",
        "user": "ellipse",
        "ip": "diamond",
        "process": "hexagon",
        "technique": "tag",
        "tactic": "round-rectangle",
    }

    for ent_type, values in entities.items():
        for val in list(values)[:50]:  # limit nodes
            nid = f"{ent_type}:{val}"
            if nid not in node_ids:
                node_ids.add(nid)
                nodes.append({
                    "data": {
                        "id": nid,
                        "label": val[:40],
                        "type": ent_type,
                        "color": TYPE_COLORS.get(ent_type, "#666"),
                        "shape": TYPE_SHAPES.get(ent_type, "ellipse"),
                    },
                })

    # Technique nodes
    seen_techniques: set[str] = set()
    for tech_set in row_techniques:
        seen_techniques.update(tech_set)

    for tech_id in seen_techniques:
        name, tactic = tech_meta.get(tech_id, (tech_id, "unknown"))
        nid = f"technique:{tech_id}"
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({
                "data": {
                    "id": nid,
                    "label": f"{tech_id}\n{name}",
                    "type": "technique",
                    "color": TYPE_COLORS["technique"],
                    "shape": TYPE_SHAPES["technique"],
                    "tactic": tactic,
                },
            })

    # Edges: entity → technique (based on co-occurrence in rows)
    for i, row_ents in enumerate(row_entity_map):
        for ent_type, ent_val in row_ents:
            for tech_id in row_techniques[i]:
                src = f"{ent_type}:{ent_val}"
                tgt = f"technique:{tech_id}"
                if src in node_ids and tgt in node_ids:
                    edge_key = (src, tgt)
                    edge_counter[edge_key] += 1

    # Edges: entity → entity (based on co-occurrence)
    for row_ents in row_entity_map:
        for j in range(len(row_ents)):
            for k in range(j + 1, len(row_ents)):
                src = f"{row_ents[j][0]}:{row_ents[j][1]}"
                tgt = f"{row_ents[k][0]}:{row_ents[k][1]}"
                if src in node_ids and tgt in node_ids and src != tgt:
                    edge_counter[(src, tgt)] += 1

    # Build edge list (filter low-weight edges)
    for (src, tgt), weight in edge_counter.most_common(500):
        if weight < 1:
            continue
        edges.append({
            "data": {
                "source": src,
                "target": tgt,
                "weight": weight,
                "label": str(weight) if weight > 2 else "",
            },
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_counts": {t: len(v) for t, v in entities.items()},
            "techniques_found": len(seen_techniques),
        },
    }
