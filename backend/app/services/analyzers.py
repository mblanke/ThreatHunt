"""Pluggable Analyzer Framework for ThreatHunt.

Each analyzer implements a simple protocol:
  - name / description properties
  - async analyze(rows, config) -> list[AlertCandidate]

The AnalyzerRegistry discovers and runs all enabled analyzers against
a dataset, producing alert candidates that the alert system can persist.
"""

from __future__ import annotations

import logging
import math
import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


# ── Alert Candidate DTO ──────────────────────────────────────────────


@dataclass
class AlertCandidate:
    """A single finding from an analyzer, before it becomes a persisted Alert."""
    analyzer: str
    title: str
    severity: str  # critical | high | medium | low | info
    description: str
    evidence: list[dict] = field(default_factory=list)  # [{row_index, field, value, ...}]
    mitre_technique: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    score: float = 0.0  # 0-100


# ── Base Analyzer ────────────────────────────────────────────────────


class BaseAnalyzer(ABC):
    """Interface every analyzer must implement."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    async def analyze(
        self, rows: list[dict[str, Any]], config: dict[str, Any] | None = None
    ) -> list[AlertCandidate]: ...


# ── Built-in Analyzers ──────────────────────────────────────────────


class EntropyAnalyzer(BaseAnalyzer):
    """Detects high-entropy strings (encoded payloads, obfuscated commands)."""

    name = "entropy"
    description = "Flags fields with high Shannon entropy (possible encoding/obfuscation)"

    ENTROPY_FIELDS = [
        "command_line", "commandline", "process_command_line", "cmdline",
        "powershell_command", "script_block", "url", "uri", "path",
        "file_path", "target_filename", "query", "dns_query",
    ]
    DEFAULT_THRESHOLD = 4.5

    @staticmethod
    def _shannon(s: str) -> float:
        if not s or len(s) < 8:
            return 0.0
        freq = Counter(s)
        length = len(s)
        return -sum((c / length) * math.log2(c / length) for c in freq.values())

    async def analyze(self, rows, config=None):
        config = config or {}
        threshold = config.get("entropy_threshold", self.DEFAULT_THRESHOLD)
        min_length = config.get("min_length", 20)
        alerts: list[AlertCandidate] = []

        for idx, row in enumerate(rows):
            for field_name in self.ENTROPY_FIELDS:
                val = str(row.get(field_name, ""))
                if len(val) < min_length:
                    continue
                ent = self._shannon(val)
                if ent >= threshold:
                    sev = "critical" if ent > 5.5 else "high" if ent > 5.0 else "medium"
                    alerts.append(AlertCandidate(
                        analyzer=self.name,
                        title=f"High-entropy string in {field_name}",
                        severity=sev,
                        description=f"Shannon entropy {ent:.2f} (threshold {threshold}) in row {idx}, field '{field_name}'",
                        evidence=[{"row_index": idx, "field": field_name, "value": val[:200], "entropy": round(ent, 3)}],
                        mitre_technique="T1027",  # Obfuscated Files or Information
                        tags=["obfuscation", "entropy"],
                        score=min(100, ent * 18),
                    ))
        return alerts


class SuspiciousCommandAnalyzer(BaseAnalyzer):
    """Detects known-bad command patterns (credential dumping, lateral movement, persistence)."""

    name = "suspicious_commands"
    description = "Flags processes executing known-suspicious command patterns"

    PATTERNS: list[tuple[str, str, str, str]] = [
        # (regex, title, severity, mitre_technique)
        (r"mimikatz|sekurlsa|lsadump|kerberos::list", "Mimikatz / Credential Dumping", "critical", "T1003"),
        (r"(?i)-enc\s+[A-Za-z0-9+/=]{40,}", "Encoded PowerShell command", "high", "T1059.001"),
        (r"(?i)invoke-(mimikatz|expression|webrequest|shellcode)", "Suspicious PowerShell Invoke", "high", "T1059.001"),
        (r"(?i)net\s+(user|localgroup|group)\s+/add", "Local account creation", "high", "T1136.001"),
        (r"(?i)schtasks\s+/create", "Scheduled task creation", "medium", "T1053.005"),
        (r"(?i)reg\s+add\s+.*\\run", "Registry Run key persistence", "high", "T1547.001"),
        (r"(?i)wmic\s+.*(process\s+call|shadowcopy\s+delete)", "WMI abuse / shadow copy deletion", "critical", "T1047"),
        (r"(?i)psexec|winrm|wmic\s+/node:", "Lateral movement tool", "high", "T1021"),
        (r"(?i)certutil\s+-urlcache", "Certutil download (LOLBin)", "high", "T1105"),
        (r"(?i)bitsadmin\s+/transfer", "BITSAdmin download", "medium", "T1197"),
        (r"(?i)vssadmin\s+delete\s+shadows", "VSS shadow deletion (ransomware)", "critical", "T1490"),
        (r"(?i)bcdedit.*recoveryenabled.*no", "Boot config tamper (ransomware)", "critical", "T1490"),
        (r"(?i)attrib\s+\+h\s+\+s", "Hidden file attribute set", "low", "T1564.001"),
        (r"(?i)netsh\s+advfirewall\s+.*disable", "Firewall disabled", "high", "T1562.004"),
        (r"(?i)whoami\s*/priv", "Privilege enumeration", "medium", "T1033"),
        (r"(?i)nltest\s+/dclist", "Domain controller enumeration", "medium", "T1018"),
        (r"(?i)dsquery|ldapsearch|adfind", "Active Directory enumeration", "medium", "T1087.002"),
        (r"(?i)procdump.*-ma\s+lsass", "LSASS memory dump", "critical", "T1003.001"),
        (r"(?i)rundll32.*comsvcs.*MiniDump", "LSASS dump via comsvcs", "critical", "T1003.001"),
    ]

    CMD_FIELDS = [
        "command_line", "commandline", "process_command_line", "cmdline",
        "parent_command_line", "powershell_command",
    ]

    async def analyze(self, rows, config=None):
        alerts: list[AlertCandidate] = []
        compiled = [(re.compile(p, re.IGNORECASE), t, s, m) for p, t, s, m in self.PATTERNS]

        for idx, row in enumerate(rows):
            for fld in self.CMD_FIELDS:
                val = str(row.get(fld, ""))
                if len(val) < 3:
                    continue
                for pattern, title, sev, mitre in compiled:
                    if pattern.search(val):
                        alerts.append(AlertCandidate(
                            analyzer=self.name,
                            title=title,
                            severity=sev,
                            description=f"Suspicious command pattern in row {idx}: {val[:200]}",
                            evidence=[{"row_index": idx, "field": fld, "value": val[:300]}],
                            mitre_technique=mitre,
                            tags=["command", "suspicious"],
                            score={"critical": 95, "high": 80, "medium": 60, "low": 30}.get(sev, 50),
                        ))
        return alerts


class NetworkAnomalyAnalyzer(BaseAnalyzer):
    """Detects anomalous network patterns (beaconing, unusual ports, large transfers)."""

    name = "network_anomaly"
    description = "Flags anomalous network behavior (beaconing, unusual ports, large transfers)"

    SUSPICIOUS_PORTS = {4444, 5555, 6666, 8888, 9999, 1234, 31337, 12345, 54321, 1337}
    C2_PORTS = {443, 8443, 8080, 4443, 9443}

    async def analyze(self, rows, config=None):
        config = config or {}
        alerts: list[AlertCandidate] = []

        # Track destination IP frequency for beaconing detection
        dst_freq: dict[str, list[int]] = defaultdict(list)
        port_hits: list[tuple[int, str, int]] = []

        for idx, row in enumerate(rows):
            dst_ip = str(row.get("dst_ip", row.get("destination_ip", row.get("dest_ip", ""))))
            dst_port = row.get("dst_port", row.get("destination_port", row.get("dest_port", "")))

            if dst_ip and dst_ip != "":
                dst_freq[dst_ip].append(idx)

            if dst_port:
                try:
                    port_num = int(dst_port)
                    if port_num in self.SUSPICIOUS_PORTS:
                        port_hits.append((idx, dst_ip, port_num))
                except (ValueError, TypeError):
                    pass

            # Large transfer detection
            bytes_val = row.get("bytes_sent", row.get("bytes_out", row.get("sent_bytes", 0)))
            try:
                if int(bytes_val or 0) > config.get("large_transfer_threshold", 10_000_000):
                    alerts.append(AlertCandidate(
                        analyzer=self.name,
                        title="Large data transfer detected",
                        severity="medium",
                        description=f"Row {idx}: {bytes_val} bytes sent to {dst_ip}",
                        evidence=[{"row_index": idx, "dst_ip": dst_ip, "bytes": str(bytes_val)}],
                        mitre_technique="T1048",
                        tags=["exfiltration", "network"],
                        score=65,
                    ))
            except (ValueError, TypeError):
                pass

        # Beaconing: IPs contacted more than threshold times
        beacon_thresh = config.get("beacon_threshold", 20)
        for ip, indices in dst_freq.items():
            if len(indices) >= beacon_thresh:
                alerts.append(AlertCandidate(
                    analyzer=self.name,
                    title=f"Possible beaconing to {ip}",
                    severity="high",
                    description=f"Destination {ip} contacted {len(indices)} times (threshold: {beacon_thresh})",
                    evidence=[{"dst_ip": ip, "contact_count": len(indices), "sample_rows": indices[:10]}],
                    mitre_technique="T1071",
                    tags=["beaconing", "c2", "network"],
                    score=min(95, 50 + len(indices)),
                ))

        # Suspicious ports
        for idx, ip, port in port_hits:
            alerts.append(AlertCandidate(
                analyzer=self.name,
                title=f"Connection on suspicious port {port}",
                severity="medium",
                description=f"Row {idx}: connection to {ip}:{port}",
                evidence=[{"row_index": idx, "dst_ip": ip, "dst_port": port}],
                mitre_technique="T1571",
                tags=["suspicious_port", "network"],
                score=55,
            ))

        return alerts


class FrequencyAnomalyAnalyzer(BaseAnalyzer):
    """Detects statistically rare values that may indicate anomalies."""

    name = "frequency_anomaly"
    description = "Flags statistically rare field values (potential anomalies)"

    FIELDS_TO_CHECK = [
        "process_name", "image_name", "parent_process_name",
        "user", "username", "user_name",
        "event_type", "action", "status",
    ]

    async def analyze(self, rows, config=None):
        config = config or {}
        rarity_threshold = config.get("rarity_threshold", 0.01)  # <1% occurrence
        min_rows = config.get("min_rows", 50)
        alerts: list[AlertCandidate] = []

        if len(rows) < min_rows:
            return alerts

        for fld in self.FIELDS_TO_CHECK:
            values = [str(row.get(fld, "")) for row in rows if row.get(fld)]
            if not values:
                continue
            counts = Counter(values)
            total = len(values)

            for val, cnt in counts.items():
                pct = cnt / total
                if pct <= rarity_threshold and cnt <= 3:
                    # Find row indices
                    indices = [i for i, r in enumerate(rows) if str(r.get(fld, "")) == val]
                    alerts.append(AlertCandidate(
                        analyzer=self.name,
                        title=f"Rare {fld}: {val[:80]}",
                        severity="low",
                        description=f"'{val}' appears {cnt}/{total} times ({pct:.2%}) in field '{fld}'",
                        evidence=[{"field": fld, "value": val[:200], "count": cnt, "total": total, "rows": indices[:5]}],
                        tags=["anomaly", "rare"],
                        score=max(20, 50 - (pct * 5000)),
                    ))

        return alerts


class AuthAnomalyAnalyzer(BaseAnalyzer):
    """Detects authentication anomalies (brute force, unusual logon types)."""

    name = "auth_anomaly"
    description = "Flags authentication anomalies (failed logins, unusual logon types)"

    async def analyze(self, rows, config=None):
        config = config or {}
        alerts: list[AlertCandidate] = []

        # Track failed logins per user
        failed_by_user: dict[str, list[int]] = defaultdict(list)
        logon_types: dict[str, list[int]] = defaultdict(list)

        for idx, row in enumerate(rows):
            event_type = str(row.get("event_type", row.get("action", ""))).lower()
            status = str(row.get("status", row.get("result", ""))).lower()
            user = str(row.get("username", row.get("user", row.get("user_name", ""))))
            logon_type = str(row.get("logon_type", ""))

            if "logon" in event_type or "auth" in event_type or "login" in event_type:
                if "fail" in status or "4625" in str(row.get("event_id", "")):
                    if user:
                        failed_by_user[user].append(idx)

                if logon_type in ("3", "10"):  # Network/RemoteInteractive
                    logon_types[logon_type].append(idx)

        # Brute force: >5 failed logins for same user
        brute_thresh = config.get("brute_force_threshold", 5)
        for user, indices in failed_by_user.items():
            if len(indices) >= brute_thresh:
                alerts.append(AlertCandidate(
                    analyzer=self.name,
                    title=f"Possible brute force: {user}",
                    severity="high",
                    description=f"User '{user}' had {len(indices)} failed logins",
                    evidence=[{"user": user, "failed_count": len(indices), "rows": indices[:10]}],
                    mitre_technique="T1110",
                    tags=["brute_force", "authentication"],
                    score=min(90, 50 + len(indices) * 3),
                ))

        # Unusual logon types
        for ltype, indices in logon_types.items():
            label = "Network logon (Type 3)" if ltype == "3" else "Remote Desktop (Type 10)"
            if len(indices) >= 3:
                alerts.append(AlertCandidate(
                    analyzer=self.name,
                    title=f"{label} detected",
                    severity="medium" if ltype == "3" else "high",
                    description=f"{len(indices)} {label} events detected",
                    evidence=[{"logon_type": ltype, "count": len(indices), "rows": indices[:10]}],
                    mitre_technique="T1021",
                    tags=["authentication", "lateral_movement"],
                    score=55 if ltype == "3" else 70,
                ))

        return alerts


class PersistenceAnalyzer(BaseAnalyzer):
    """Detects persistence mechanisms (registry keys, services, scheduled tasks)."""

    name = "persistence"
    description = "Flags persistence mechanism installations"

    REGISTRY_PATTERNS = [
        (r"(?i)\\CurrentVersion\\Run", "Run key persistence", "T1547.001"),
        (r"(?i)\\Services\\", "Service installation", "T1543.003"),
        (r"(?i)\\Winlogon\\", "Winlogon persistence", "T1547.004"),
        (r"(?i)\\Image File Execution Options\\", "IFEO debugger persistence", "T1546.012"),
        (r"(?i)\\Explorer\\Shell Folders", "Shell folder hijack", "T1547.001"),
    ]

    async def analyze(self, rows, config=None):
        alerts: list[AlertCandidate] = []
        compiled = [(re.compile(p), t, m) for p, t, m in self.REGISTRY_PATTERNS]

        for idx, row in enumerate(rows):
            # Check registry paths
            reg_path = str(row.get("registry_key", row.get("target_object", row.get("registry_path", ""))))
            for pattern, title, mitre in compiled:
                if pattern.search(reg_path):
                    alerts.append(AlertCandidate(
                        analyzer=self.name,
                        title=title,
                        severity="high",
                        description=f"Row {idx}: {reg_path[:200]}",
                        evidence=[{"row_index": idx, "registry_key": reg_path[:300]}],
                        mitre_technique=mitre,
                        tags=["persistence", "registry"],
                        score=75,
                    ))

            # Check for service creation events
            event_type = str(row.get("event_type", "")).lower()
            if "service" in event_type and "creat" in event_type:
                svc_name = row.get("service_name", row.get("target_filename", "unknown"))
                alerts.append(AlertCandidate(
                    analyzer=self.name,
                    title=f"Service created: {svc_name}",
                    severity="medium",
                    description=f"Row {idx}: New service '{svc_name}' created",
                    evidence=[{"row_index": idx, "service_name": str(svc_name)}],
                    mitre_technique="T1543.003",
                    tags=["persistence", "service"],
                    score=60,
                ))

        return alerts


# ── Analyzer Registry ────────────────────────────────────────────────


_ALL_ANALYZERS: list[BaseAnalyzer] = [
    EntropyAnalyzer(),
    SuspiciousCommandAnalyzer(),
    NetworkAnomalyAnalyzer(),
    FrequencyAnomalyAnalyzer(),
    AuthAnomalyAnalyzer(),
    PersistenceAnalyzer(),
]


def get_available_analyzers() -> list[dict[str, str]]:
    """Return metadata about all registered analyzers."""
    return [{"name": a.name, "description": a.description} for a in _ALL_ANALYZERS]


def get_analyzer(name: str) -> BaseAnalyzer | None:
    """Get an analyzer by name."""
    for a in _ALL_ANALYZERS:
        if a.name == name:
            return a
    return None


async def run_all_analyzers(
    rows: list[dict[str, Any]],
    enabled: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> list[AlertCandidate]:
    """Run all (or selected) analyzers and return combined alert candidates.

    Args:
        rows: Flat list of row dicts (normalized_data or data from DatasetRow).
        enabled: Optional list of analyzer names to run. Runs all if None.
        config: Optional config overrides passed to each analyzer.

    Returns:
        Combined list of AlertCandidate from all analyzers, sorted by score desc.
    """
    config = config or {}
    results: list[AlertCandidate] = []

    for analyzer in _ALL_ANALYZERS:
        if enabled and analyzer.name not in enabled:
            continue
        try:
            candidates = await analyzer.analyze(rows, config)
            results.extend(candidates)
            logger.info("Analyzer %s produced %d alerts", analyzer.name, len(candidates))
        except Exception:
            logger.exception("Analyzer %s failed", analyzer.name)

    # Sort by score descending
    results.sort(key=lambda a: a.score, reverse=True)
    return results
