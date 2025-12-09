from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_role
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogRead

router = APIRouter()


@router.get("/", response_model=List[AuditLogRead])
async def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    List audit logs (admin only, scoped to tenant)
    
    Provides a complete audit trail of actions within the tenant.
    """
    # Base query scoped to tenant
    query = db.query(AuditLog).filter(AuditLog.tenant_id == current_user.tenant_id)
    
    # Apply filters
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    # Order by most recent first
    query = query.order_by(AuditLog.created_at.desc())
    
    # Paginate
    logs = query.offset(skip).limit(limit).all()
    
    return logs


@router.get("/{log_id}", response_model=AuditLogRead)
async def get_audit_log(
    log_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Get a specific audit log entry (admin only)
    """
    from fastapi import HTTPException, status
    
    log = db.query(AuditLog).filter(
        AuditLog.id == log_id,
        AuditLog.tenant_id == current_user.tenant_id
    ).first()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )
    
    return log
