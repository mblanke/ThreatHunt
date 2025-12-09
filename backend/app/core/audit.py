from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: Optional[int],
    tenant_id: int,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
):
    """
    Log an action to the audit log
    
    Args:
        db: Database session
        user_id: ID of user performing action (None for system actions)
        tenant_id: Tenant ID
        action: Action type (CREATE, READ, UPDATE, DELETE, LOGIN, etc.)
        resource_type: Type of resource (user, host, case, etc.)
        resource_id: ID of the resource (if applicable)
        details: Additional details as JSON
        request: FastAPI request object (for IP and user agent)
    """
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    audit_log = AuditLog(
        user_id=user_id,
        tenant_id=tenant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(audit_log)
    db.commit()
    
    return audit_log
