from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class ThreatScoreBase(BaseModel):
    """Base threat score schema"""
    score: float
    confidence: float
    threat_type: str
    description: Optional[str] = None
    indicators: Optional[List[Dict[str, Any]]] = None


class ThreatScoreCreate(ThreatScoreBase):
    """Schema for creating a threat score"""
    host_id: Optional[int] = None
    artifact_id: Optional[int] = None
    ml_model_version: Optional[str] = None


class ThreatScoreRead(ThreatScoreBase):
    """Schema for reading threat score data"""
    id: int
    tenant_id: int
    host_id: Optional[int]
    artifact_id: Optional[int]
    ml_model_version: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
