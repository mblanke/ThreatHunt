"""Investigation Notebook & Playbook Engine for ThreatHunt.

Notebooks:  Analyst-facing, cell-based documents (markdown + code cells)
            stored as JSON in the database.  Each cell can contain free-form
            markdown notes *or* a structured query/command that the backend
            evaluates against datasets.

Playbooks:  Pre-defined, step-by-step investigation workflows.  Each step
            defines an action (query, analyze, enrich, tag) and expected
            outcomes.  Analysts can run through playbooks interactively or
            trigger them automatically on new alerts.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Notebook helpers ──────────────────────────────────────────────────


@dataclass
class NotebookCell:
    id: str
    cell_type: str  # markdown | query | code
    source: str
    output: Optional[str] = None
    metadata: dict = field(default_factory=dict)


def validate_notebook_cells(cells: list[dict]) -> list[dict]:
    """Ensure each cell has required keys."""
    cleaned: list[dict] = []
    for i, c in enumerate(cells):
        cleaned.append({
            "id": c.get("id", f"cell-{i}"),
            "cell_type": c.get("cell_type", "markdown"),
            "source": c.get("source", ""),
            "output": c.get("output"),
            "metadata": c.get("metadata", {}),
        })
    return cleaned


# ── Built-in Playbook Templates ──────────────────────────────────────


BUILT_IN_PLAYBOOKS: list[dict[str, Any]] = [
    {
        "name": "Suspicious Process Investigation",
        "description": "Step-by-step investigation of a potentially malicious process execution.",
        "category": "incident_response",
        "tags": ["process", "malware", "T1059"],
        "steps": [
            {
                "order": 1,
                "title": "Identify the suspicious process",
                "description": "Search for the process name/PID across all datasets. Note the command line, parent, and user context.",
                "action": "search",
                "action_config": {"fields": ["process_name", "command_line", "parent_process_name", "username"]},
                "expected_outcome": "Process details, parent chain, and execution context identified.",
            },
            {
                "order": 2,
                "title": "Build process tree",
                "description": "View the full parent→child process tree to understand the execution chain.",
                "action": "process_tree",
                "action_config": {},
                "expected_outcome": "Complete process lineage showing how the suspicious process was spawned.",
            },
            {
                "order": 3,
                "title": "Check network connections",
                "description": "Search for network events associated with the same host and timeframe.",
                "action": "search",
                "action_config": {"fields": ["src_ip", "dst_ip", "dst_port", "protocol"]},
                "expected_outcome": "Network connections revealing potential C2 or data exfiltration.",
            },
            {
                "order": 4,
                "title": "Run analyzers",
                "description": "Execute the suspicious_commands and entropy analyzers against the dataset.",
                "action": "analyze",
                "action_config": {"analyzers": ["suspicious_commands", "entropy"]},
                "expected_outcome": "Automated detection of known-bad patterns.",
            },
            {
                "order": 5,
                "title": "Map to MITRE ATT&CK",
                "description": "Check which MITRE techniques the process behavior maps to.",
                "action": "mitre_map",
                "action_config": {},
                "expected_outcome": "MITRE technique mappings for the suspicious activity.",
            },
            {
                "order": 6,
                "title": "Document findings & create case",
                "description": "Summarize investigation findings, annotate key evidence, and create a case if warranted.",
                "action": "create_case",
                "action_config": {},
                "expected_outcome": "Investigation documented with annotations and optionally escalated.",
            },
        ],
    },
    {
        "name": "Lateral Movement Hunt",
        "description": "Systematic hunt for lateral movement indicators across the environment.",
        "category": "threat_hunting",
        "tags": ["lateral_movement", "T1021", "T1047"],
        "steps": [
            {
                "order": 1,
                "title": "Search for remote access tools",
                "description": "Look for PsExec, WMI, WinRM, RDP, and SSH usage across datasets.",
                "action": "search",
                "action_config": {"query": "psexec|wmic|winrm|rdp|ssh"},
                "expected_outcome": "Identify all remote access tool usage.",
            },
            {
                "order": 2,
                "title": "Analyze authentication events",
                "description": "Run the auth anomaly analyzer to find brute force, unusual logon types.",
                "action": "analyze",
                "action_config": {"analyzers": ["auth_anomaly"]},
                "expected_outcome": "Authentication anomalies detected.",
            },
            {
                "order": 3,
                "title": "Check network anomalies",
                "description": "Run network anomaly analyzer for beaconing and suspicious connections.",
                "action": "analyze",
                "action_config": {"analyzers": ["network_anomaly"]},
                "expected_outcome": "Beaconing or unusual network patterns identified.",
            },
            {
                "order": 4,
                "title": "Build knowledge graph",
                "description": "Visualize entity relationships to identify pivot paths.",
                "action": "knowledge_graph",
                "action_config": {},
                "expected_outcome": "Entity relationship graph showing lateral movement paths.",
            },
            {
                "order": 5,
                "title": "Document and escalate",
                "description": "Create annotations for key findings and escalate to case if needed.",
                "action": "create_case",
                "action_config": {"tags": ["lateral_movement"]},
                "expected_outcome": "Findings documented and case created.",
            },
        ],
    },
    {
        "name": "Data Exfiltration Check",
        "description": "Investigate potential data exfiltration activity.",
        "category": "incident_response",
        "tags": ["exfiltration", "T1048", "T1567"],
        "steps": [
            {
                "order": 1,
                "title": "Identify large transfers",
                "description": "Search for network events with unusually high byte counts.",
                "action": "analyze",
                "action_config": {"analyzers": ["network_anomaly"], "config": {"large_transfer_threshold": 5000000}},
                "expected_outcome": "Large data transfers identified.",
            },
            {
                "order": 2,
                "title": "Check DNS anomalies",
                "description": "Look for DNS tunneling or unusual DNS query patterns.",
                "action": "search",
                "action_config": {"fields": ["dns_query", "query_length"]},
                "expected_outcome": "Suspicious DNS activity identified.",
            },
            {
                "order": 3,
                "title": "Timeline analysis",
                "description": "Examine the timeline for data staging and exfiltration windows.",
                "action": "timeline",
                "action_config": {},
                "expected_outcome": "Time windows of suspicious activity identified.",
            },
            {
                "order": 4,
                "title": "Correlate with process activity",
                "description": "Match network exfiltration with process execution times.",
                "action": "search",
                "action_config": {"fields": ["process_name", "dst_ip", "bytes_sent"]},
                "expected_outcome": "Process responsible for data transfer identified.",
            },
            {
                "order": 5,
                "title": "MITRE mapping & documentation",
                "description": "Map findings to MITRE exfiltration techniques and document.",
                "action": "mitre_map",
                "action_config": {},
                "expected_outcome": "Complete exfiltration investigation documented.",
            },
        ],
    },
    {
        "name": "Ransomware Triage",
        "description": "Rapid triage of potential ransomware activity.",
        "category": "incident_response",
        "tags": ["ransomware", "T1486", "T1490"],
        "steps": [
            {
                "order": 1,
                "title": "Search for ransomware indicators",
                "description": "Look for shadow copy deletion, boot config changes, encryption activity.",
                "action": "search",
                "action_config": {"query": "vssadmin|bcdedit|cipher|.encrypted|.locked|ransom"},
                "expected_outcome": "Ransomware indicators identified.",
            },
            {
                "order": 2,
                "title": "Run all analyzers",
                "description": "Execute all analyzers to get comprehensive threat picture.",
                "action": "analyze",
                "action_config": {},
                "expected_outcome": "Full automated analysis of ransomware indicators.",
            },
            {
                "order": 3,
                "title": "Check persistence mechanisms",
                "description": "Look for persistence that may indicate pre-ransomware staging.",
                "action": "analyze",
                "action_config": {"analyzers": ["persistence"]},
                "expected_outcome": "Persistence mechanisms identified.",
            },
            {
                "order": 4,
                "title": "LLM deep analysis",
                "description": "Run deep LLM analysis for comprehensive ransomware assessment.",
                "action": "llm_analyze",
                "action_config": {"mode": "deep", "focus": "ransomware"},
                "expected_outcome": "AI-powered ransomware analysis with recommendations.",
            },
            {
                "order": 5,
                "title": "Create critical case",
                "description": "Immediately create a critical-severity case for the ransomware incident.",
                "action": "create_case",
                "action_config": {"severity": "critical", "tags": ["ransomware"]},
                "expected_outcome": "Critical case created for incident response.",
            },
        ],
    },
]


def get_builtin_playbooks() -> list[dict]:
    """Return list of all built-in playbook templates."""
    return BUILT_IN_PLAYBOOKS


def get_playbook_template(name: str) -> dict | None:
    """Get a specific built-in playbook by name."""
    for pb in BUILT_IN_PLAYBOOKS:
        if pb["name"] == name:
            return pb
    return None
