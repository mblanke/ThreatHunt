"""API routes for MITRE ATT&CK coverage visualization."""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import (
    TriageResult, HostProfile, Hypothesis, HuntReport, Dataset, Hunt
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mitre", tags=["mitre"])

# Canonical MITRE ATT&CK tactics in kill-chain order
TACTICS = [
    "Reconnaissance", "Resource Development", "Initial Access",
    "Execution", "Persistence", "Privilege Escalation",
    "Defense Evasion", "Credential Access", "Discovery",
    "Lateral Movement", "Collection", "Command and Control",
    "Exfiltration", "Impact",
]

# Simplified technique-to-tactic mapping (top techniques)
TECHNIQUE_TACTIC: dict[str, str] = {
    "T1059": "Execution", "T1059.001": "Execution", "T1059.003": "Execution",
    "T1059.005": "Execution", "T1059.006": "Execution", "T1059.007": "Execution",
    "T1053": "Persistence", "T1053.005": "Persistence",
    "T1547": "Persistence", "T1547.001": "Persistence",
    "T1543": "Persistence", "T1543.003": "Persistence",
    "T1078": "Privilege Escalation", "T1078.001": "Privilege Escalation",
    "T1078.002": "Privilege Escalation", "T1078.003": "Privilege Escalation",
    "T1055": "Privilege Escalation", "T1055.001": "Privilege Escalation",
    "T1548": "Privilege Escalation", "T1548.002": "Privilege Escalation",
    "T1070": "Defense Evasion", "T1070.001": "Defense Evasion",
    "T1070.004": "Defense Evasion",
    "T1036": "Defense Evasion", "T1036.005": "Defense Evasion",
    "T1027": "Defense Evasion", "T1140": "Defense Evasion",
    "T1218": "Defense Evasion", "T1218.011": "Defense Evasion",
    "T1003": "Credential Access", "T1003.001": "Credential Access",
    "T1110": "Credential Access", "T1558": "Credential Access",
    "T1087": "Discovery", "T1087.001": "Discovery", "T1087.002": "Discovery",
    "T1082": "Discovery", "T1083": "Discovery", "T1057": "Discovery",
    "T1018": "Discovery", "T1049": "Discovery", "T1016": "Discovery",
    "T1021": "Lateral Movement", "T1021.001": "Lateral Movement",
    "T1021.002": "Lateral Movement", "T1021.006": "Lateral Movement",
    "T1570": "Lateral Movement",
    "T1560": "Collection", "T1074": "Collection", "T1005": "Collection",
    "T1071": "Command and Control", "T1071.001": "Command and Control",
    "T1105": "Command and Control", "T1572": "Command and Control",
    "T1095": "Command and Control",
    "T1048": "Exfiltration", "T1041": "Exfiltration",
    "T1486": "Impact", "T1490": "Impact", "T1489": "Impact",
    "T1566": "Initial Access", "T1566.001": "Initial Access",
    "T1566.002": "Initial Access",
    "T1190": "Initial Access", "T1133": "Initial Access",
    "T1195": "Initial Access", "T1195.002": "Initial Access",
}


def _get_tactic(technique_id: str) -> str:
    """Map a technique ID to its tactic."""
    tech = technique_id.strip().upper()
    if tech in TECHNIQUE_TACTIC:
        return TECHNIQUE_TACTIC[tech]
    # Try parent technique
    if "." in tech:
        parent = tech.split(".")[0]
        if parent in TECHNIQUE_TACTIC:
            return TECHNIQUE_TACTIC[parent]
    return "Unknown"


@router.get("/coverage")
async def get_mitre_coverage(
    hunt_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Aggregate all MITRE techniques from triage, host profiles, hypotheses, and reports."""

    techniques: dict[str, dict] = {}

    # Collect from triage results
    triage_q = select(TriageResult)
    if hunt_id:
        triage_q = triage_q.join(Dataset).where(Dataset.hunt_id == hunt_id)
    result = await db.execute(triage_q.limit(500))
    for t in result.scalars().all():
        for tech in (t.mitre_techniques or []):
            if tech not in techniques:
                techniques[tech] = {"id": tech, "tactic": _get_tactic(tech), "sources": [], "count": 0}
            techniques[tech]["count"] += 1
            techniques[tech]["sources"].append({"type": "triage", "risk_score": t.risk_score})

    # Collect from host profiles
    profile_q = select(HostProfile)
    if hunt_id:
        profile_q = profile_q.where(HostProfile.hunt_id == hunt_id)
    result = await db.execute(profile_q.limit(200))
    for p in result.scalars().all():
        for tech in (p.mitre_techniques or []):
            if tech not in techniques:
                techniques[tech] = {"id": tech, "tactic": _get_tactic(tech), "sources": [], "count": 0}
            techniques[tech]["count"] += 1
            techniques[tech]["sources"].append({"type": "host_profile", "hostname": p.hostname})

    # Collect from hypotheses
    hyp_q = select(Hypothesis)
    if hunt_id:
        hyp_q = hyp_q.where(Hypothesis.hunt_id == hunt_id)
    result = await db.execute(hyp_q.limit(200))
    for h in result.scalars().all():
        tech = h.mitre_technique
        if tech:
            if tech not in techniques:
                techniques[tech] = {"id": tech, "tactic": _get_tactic(tech), "sources": [], "count": 0}
            techniques[tech]["count"] += 1
            techniques[tech]["sources"].append({"type": "hypothesis", "title": h.title})

    # Build tactic-grouped response
    tactic_groups: dict[str, list] = {t: [] for t in TACTICS}
    tactic_groups["Unknown"] = []
    for tech in techniques.values():
        tactic = tech["tactic"]
        if tactic not in tactic_groups:
            tactic_groups[tactic] = []
        tactic_groups[tactic].append(tech)

    total_techniques = len(techniques)
    total_detections = sum(t["count"] for t in techniques.values())

    return {
        "tactics": TACTICS,
        "technique_count": total_techniques,
        "detection_count": total_detections,
        "tactic_coverage": {
            t: {"techniques": techs, "count": len(techs)}
            for t, techs in tactic_groups.items()
            if techs
        },
        "all_techniques": list(techniques.values()),
    }
