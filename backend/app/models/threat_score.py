from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class ThreatScore(Base):
    __tablename__ = "threat_scores"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    host_id = Column(Integer, ForeignKey("hosts.id"), nullable=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.id"), nullable=True)
    score = Column(Float, nullable=False, index=True)  # 0.0 to 1.0
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    threat_type = Column(String, nullable=False)  # malware, suspicious, anomaly, etc.
    description = Column(Text, nullable=True)
    indicators = Column(JSON, nullable=True)  # List of indicators that contributed to score
    ml_model_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    tenant = relationship("Tenant")
    host = relationship("Host")
    artifact = relationship("Artifact")
