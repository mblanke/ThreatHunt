from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_tenant_id
from app.models.user import User
from app.models.host import Host

router = APIRouter()


class HostCreate(BaseModel):
    hostname: str
    ip_address: Optional[str] = None
    os: Optional[str] = None
    host_metadata: Optional[dict] = None


class HostRead(BaseModel):
    id: int
    hostname: str
    ip_address: Optional[str] = None
    os: Optional[str] = None
    tenant_id: int
    host_metadata: Optional[dict] = None
    created_at: datetime
    last_seen: datetime
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[HostRead])
async def list_hosts(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    List hosts scoped to user's tenant
    """
    hosts = db.query(Host).filter(Host.tenant_id == tenant_id).offset(skip).limit(limit).all()
    return hosts


@router.post("/", response_model=HostRead, status_code=status.HTTP_201_CREATED)
async def create_host(
    host_data: HostCreate,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Create a new host
    """
    new_host = Host(
        hostname=host_data.hostname,
        ip_address=host_data.ip_address,
        os=host_data.os,
        tenant_id=tenant_id,
        host_metadata=host_data.host_metadata
    )
    
    db.add(new_host)
    db.commit()
    db.refresh(new_host)
    
    return new_host


@router.get("/{host_id}", response_model=HostRead)
async def get_host(
    host_id: int,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get host by ID (scoped to tenant)
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
    
    return host
