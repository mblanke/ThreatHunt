from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, index=True)
    artifact_type = Column(String, nullable=False)  # hash, ip, domain, email, etc.
    value = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    artifact_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    case = relationship("Case", back_populates="artifacts")
