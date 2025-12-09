from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AuditLogBase(BaseModel):
    """Base audit log schema"""
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class AuditLogCreate(AuditLogBase):
    """Schema for creating an audit log entry"""
    pass


class AuditLogRead(AuditLogBase):
    """Schema for reading audit log data"""
    id: int
    user_id: Optional[int]
    tenant_id: int
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
