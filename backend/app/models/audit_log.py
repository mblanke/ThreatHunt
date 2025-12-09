from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    action = Column(String, nullable=False)  # CREATE, READ, UPDATE, DELETE
    resource_type = Column(String, nullable=False)  # user, host, case, etc.
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = relationship("User")
    tenant = relationship("Tenant")
