from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class Playbook(Base):
    __tablename__ = "playbooks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    trigger_type = Column(String, nullable=False)  # manual, scheduled, event
    trigger_config = Column(JSON, nullable=True)
    actions = Column(JSON, nullable=False)  # List of action definitions
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")
    creator = relationship("User", foreign_keys=[created_by])
    executions = relationship("PlaybookExecution", back_populates="playbook")


class PlaybookExecution(Base):
    __tablename__ = "playbook_executions"

    id = Column(Integer, primary_key=True, index=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    status = Column(String, nullable=False)  # pending, running, completed, failed
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    playbook = relationship("Playbook", back_populates="executions")
    tenant = relationship("Tenant")
    trigger_user = relationship("User")
