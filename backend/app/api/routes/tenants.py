from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_role
from app.models.user import User
from app.models.tenant import Tenant
from pydantic import BaseModel

router = APIRouter()


class TenantCreate(BaseModel):
    name: str
    description: str = None


class TenantRead(BaseModel):
    id: int
    name: str
    description: str = None
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[TenantRead])
async def list_tenants(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List tenants
    
    Regular users can only see their own tenant.
    Admins can see all tenants (cross-tenant access).
    """
    if current_user.role == "admin":
        # Admins can see all tenants
        tenants = db.query(Tenant).all()
    else:
        # Regular users only see their tenant
        tenants = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).all()
    
    return tenants


@router.post("/", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Create a new tenant (admin only)
    """
    # Check if tenant name already exists
    existing_tenant = db.query(Tenant).filter(Tenant.name == tenant_data.name).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant name already exists"
        )
    
    new_tenant = Tenant(
        name=tenant_data.name,
        description=tenant_data.description
    )
    
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    
    return new_tenant


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get tenant by ID
    
    Users can only view their own tenant unless they are admin.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check permissions
    if current_user.role != "admin" and tenant.id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this tenant"
        )
    
    return tenant
