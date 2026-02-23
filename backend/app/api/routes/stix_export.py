"""STIX 2.1 export endpoint.

Aggregates hunt data (IOCs, techniques, host profiles, hypotheses) into a
STIX 2.1 Bundle JSON download. No external dependencies required  we
build the JSON directly following the OASIS STIX 2.1 spec.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import (
    Hunt, Dataset, Hypothesis, TriageResult, HostProfile,
    EnrichmentResult, HuntReport,
)

router = APIRouter(prefix="/api/export", tags=["export"])

STIX_SPEC_VERSION = "2.1"


def _stix_id(stype: str) -> str:
    return f"{stype}--{uuid.uuid4()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _build_identity(hunt_name: str) -> dict:
    return {
        "type": "identity",
        "spec_version": STIX_SPEC_VERSION,
        "id": _stix_id("identity"),
        "created": _now_iso(),
        "modified": _now_iso(),
        "name": f"ThreatHunt - {hunt_name}",
        "identity_class": "system",
    }


def _ioc_to_indicator(ioc_value: str, ioc_type: str, identity_id: str, verdict: str = None) -> dict:
    pattern_map = {
        "ipv4": f"[ipv4-addr:value = '{ioc_value}']",
        "ipv6": f"[ipv6-addr:value = '{ioc_value}']",
        "domain": f"[domain-name:value = '{ioc_value}']",
        "url": f"[url:value = '{ioc_value}']",
        "hash_md5": f"[file:hashes.'MD5' = '{ioc_value}']",
        "hash_sha1": f"[file:hashes.'SHA-1' = '{ioc_value}']",
        "hash_sha256": f"[file:hashes.'SHA-256' = '{ioc_value}']",
        "email": f"[email-addr:value = '{ioc_value}']",
    }
    pattern = pattern_map.get(ioc_type, f"[artifact:payload_bin = '{ioc_value}']")
    now = _now_iso()
    return {
        "type": "indicator",
        "spec_version": STIX_SPEC_VERSION,
        "id": _stix_id("indicator"),
        "created": now,
        "modified": now,
        "name": f"{ioc_type}: {ioc_value}",
        "pattern": pattern,
        "pattern_type": "stix",
        "valid_from": now,
        "created_by_ref": identity_id,
        "labels": [verdict or "suspicious"],
    }


def _technique_to_attack_pattern(technique_id: str, identity_id: str) -> dict:
    now = _now_iso()
    return {
        "type": "attack-pattern",
        "spec_version": STIX_SPEC_VERSION,
        "id": _stix_id("attack-pattern"),
        "created": now,
        "modified": now,
        "name": technique_id,
        "created_by_ref": identity_id,
        "external_references": [
            {
                "source_name": "mitre-attack",
                "external_id": technique_id,
                "url": f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}/",
            }
        ],
    }


def _hypothesis_to_report(hyp, identity_id: str) -> dict:
    now = _now_iso()
    return {
        "type": "report",
        "spec_version": STIX_SPEC_VERSION,
        "id": _stix_id("report"),
        "created": now,
        "modified": now,
        "name": hyp.title,
        "description": hyp.description or "",
        "published": now,
        "created_by_ref": identity_id,
        "labels": ["threat-hunt-hypothesis"],
        "object_refs": [],
    }


@router.get("/stix/{hunt_id}")
async def export_stix(hunt_id: str, db: AsyncSession = Depends(get_db)):
    """Export hunt data as a STIX 2.1 Bundle JSON file."""
    # Fetch hunt
    hunt = (await db.execute(select(Hunt).where(Hunt.id == hunt_id))).scalar_one_or_none()
    if not hunt:
        raise HTTPException(404, "Hunt not found")

    identity = _build_identity(hunt.name)
    objects: list[dict] = [identity]
    seen_techniques: set[str] = set()
    seen_iocs: set[str] = set()

    # Gather IOCs from enrichment results for hunt's datasets
    datasets_q = await db.execute(select(Dataset.id).where(Dataset.hunt_id == hunt_id))
    ds_ids = [r[0] for r in datasets_q.all()]

    if ds_ids:
        enrichments = (await db.execute(
            select(EnrichmentResult).where(EnrichmentResult.dataset_id.in_(ds_ids))
        )).scalars().all()
        for e in enrichments:
            key = f"{e.ioc_type}:{e.ioc_value}"
            if key not in seen_iocs:
                seen_iocs.add(key)
                objects.append(_ioc_to_indicator(e.ioc_value, e.ioc_type, identity["id"], e.verdict))

        # Gather techniques from triage results
        triages = (await db.execute(
            select(TriageResult).where(TriageResult.dataset_id.in_(ds_ids))
        )).scalars().all()
        for t in triages:
            for tech in (t.mitre_techniques or []):
                tid = tech if isinstance(tech, str) else tech.get("technique_id", str(tech))
                if tid not in seen_techniques:
                    seen_techniques.add(tid)
                    objects.append(_technique_to_attack_pattern(tid, identity["id"]))

    # Gather techniques from host profiles
    profiles = (await db.execute(
        select(HostProfile).where(HostProfile.hunt_id == hunt_id)
    )).scalars().all()
    for p in profiles:
        for tech in (p.mitre_techniques or []):
            tid = tech if isinstance(tech, str) else tech.get("technique_id", str(tech))
            if tid not in seen_techniques:
                seen_techniques.add(tid)
                objects.append(_technique_to_attack_pattern(tid, identity["id"]))

    # Gather hypotheses
    hypos = (await db.execute(
        select(Hypothesis).where(Hypothesis.hunt_id == hunt_id)
    )).scalars().all()
    for h in hypos:
        objects.append(_hypothesis_to_report(h, identity["id"]))
        if h.mitre_technique and h.mitre_technique not in seen_techniques:
            seen_techniques.add(h.mitre_technique)
            objects.append(_technique_to_attack_pattern(h.mitre_technique, identity["id"]))

    bundle = {
        "type": "bundle",
        "id": _stix_id("bundle"),
        "objects": objects,
    }

    filename = f"threathunt-{hunt.name.replace(' ', '_')}-stix.json"
    return Response(
        content=json.dumps(bundle, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
