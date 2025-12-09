from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_tenant_id
from app.core.threat_intel import get_threat_analyzer
from app.models.user import User
from app.models.threat_score import ThreatScore
from app.models.host import Host
from app.models.artifact import Artifact
from app.schemas.threat_score import ThreatScoreRead, ThreatScoreCreate

router = APIRouter()


@router.post("/analyze/host/{host_id}", response_model=ThreatScoreRead)
async def analyze_host(
    host_id: int,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Analyze a host for threats using ML
    """
    host = db.query(Host).filter(
        Host.id == host_id,
        Host.tenant_id == tenant_id
    ).first()
    
    if not host:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Host not found"
        )
    
    # Analyze host
    analyzer = get_threat_analyzer()
    analysis = analyzer.analyze_host({
        "hostname": host.hostname,
        "ip_address": host.ip_address,
        "os": host.os,
        "host_metadata": host.host_metadata
    })
    
    # Store threat score
    threat_score = ThreatScore(
        tenant_id=tenant_id,
        host_id=host_id,
        score=analysis["score"],
        confidence=analysis["confidence"],
        threat_type=analysis["threat_type"],
        indicators=analysis["indicators"],
        ml_model_version=analysis["ml_model_version"]
    )
    db.add(threat_score)
    db.commit()
    db.refresh(threat_score)
    
    return threat_score


@router.post("/analyze/artifact/{artifact_id}", response_model=ThreatScoreRead)
async def analyze_artifact(
    artifact_id: int,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Analyze an artifact for threats
    """
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    # Analyze artifact
    analyzer = get_threat_analyzer()
    analysis = analyzer.analyze_artifact({
        "artifact_type": artifact.artifact_type,
        "value": artifact.value
    })
    
    # Store threat score
    threat_score = ThreatScore(
        tenant_id=tenant_id,
        artifact_id=artifact_id,
        score=analysis["score"],
        confidence=analysis["confidence"],
        threat_type=analysis["threat_type"],
        indicators=analysis["indicators"],
        ml_model_version=analysis["ml_model_version"]
    )
    db.add(threat_score)
    db.commit()
    db.refresh(threat_score)
    
    return threat_score


@router.get("/scores", response_model=List[ThreatScoreRead])
async def list_threat_scores(
    skip: int = 0,
    limit: int = 100,
    min_score: float = 0.0,
    threat_type: str = None,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    List threat scores with filtering
    """
    query = db.query(ThreatScore).filter(ThreatScore.tenant_id == tenant_id)
    
    if min_score:
        query = query.filter(ThreatScore.score >= min_score)
    if threat_type:
        query = query.filter(ThreatScore.threat_type == threat_type)
    
    scores = query.order_by(ThreatScore.score.desc()).offset(skip).limit(limit).all()
    return scores
