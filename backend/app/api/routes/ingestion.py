from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_tenant_id
from app.models.user import User
from app.models.host import Host

router = APIRouter()


class IngestionData(BaseModel):
    hostname: str
    data: Dict[str, Any]


class IngestionResponse(BaseModel):
    message: str
    host_id: int


@router.post("/ingest", response_model=IngestionResponse)
async def ingest_data(
    ingestion: IngestionData,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Ingest data from Velociraptor
    
    Creates or updates host information scoped to the user's tenant.
    """
    # Find or create host
    host = db.query(Host).filter(
        Host.hostname == ingestion.hostname,
        Host.tenant_id == tenant_id
    ).first()
    
    if host:
        # Update existing host
        host.host_metadata = ingestion.data
    else:
        # Create new host
        host = Host(
            hostname=ingestion.hostname,
            tenant_id=tenant_id,
            host_metadata=ingestion.data
        )
        db.add(host)
    
    db.commit()
    db.refresh(host)
    
    return {
        "message": "Data ingested successfully",
        "host_id": host.id
    }
