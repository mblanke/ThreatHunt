from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # user, admin
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    email = Column(String, unique=True, nullable=True, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
