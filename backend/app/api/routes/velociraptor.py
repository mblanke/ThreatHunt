from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_role
from app.core.velociraptor import get_velociraptor_client
from app.models.user import User

router = APIRouter()


class VelociraptorConfig(BaseModel):
    """Velociraptor server configuration"""
    base_url: str
    api_key: str


class ArtifactCollectionRequest(BaseModel):
    """Request to collect an artifact"""
    client_id: str
    artifact_name: str
    parameters: Optional[Dict[str, Any]] = None


class HuntCreateRequest(BaseModel):
    """Request to create a hunt"""
    hunt_name: str
    artifact_name: str
    description: str
    parameters: Optional[Dict[str, Any]] = None


# In a real implementation, this would be stored per-tenant in database
# For now, using a simple in-memory store
velociraptor_configs: Dict[int, VelociraptorConfig] = {}


@router.post("/config")
async def set_velociraptor_config(
    config: VelociraptorConfig,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Configure Velociraptor integration (admin only)
    
    Stores Velociraptor server URL and API key for the tenant.
    """
    velociraptor_configs[current_user.tenant_id] = config
    return {"message": "Velociraptor configuration saved"}


@router.get("/clients")
async def list_velociraptor_clients(
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List clients from Velociraptor server
    """
    config = velociraptor_configs.get(current_user.tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Velociraptor not configured for this tenant"
        )
    
    client = get_velociraptor_client(config.base_url, config.api_key)
    try:
        clients = await client.list_clients(limit=limit)
        return {"clients": clients}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clients: {str(e)}"
        )


@router.get("/clients/{client_id}")
async def get_velociraptor_client_info(
    client_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get information about a specific Velociraptor client
    """
    config = velociraptor_configs.get(current_user.tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Velociraptor not configured for this tenant"
        )
    
    client = get_velociraptor_client(config.base_url, config.api_key)
    try:
        client_info = await client.get_client(client_id)
        return client_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch client: {str(e)}"
        )


@router.post("/collect")
async def collect_artifact(
    request: ArtifactCollectionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Collect an artifact from a Velociraptor client
    """
    config = velociraptor_configs.get(current_user.tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Velociraptor not configured for this tenant"
        )
    
    client = get_velociraptor_client(config.base_url, config.api_key)
    try:
        result = await client.collect_artifact(
            request.client_id,
            request.artifact_name,
            request.parameters
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect artifact: {str(e)}"
        )


@router.post("/hunts")
async def create_hunt(
    request: HuntCreateRequest,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """
    Create a new hunt (admin only)
    """
    config = velociraptor_configs.get(current_user.tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Velociraptor not configured for this tenant"
        )
    
    client = get_velociraptor_client(config.base_url, config.api_key)
    try:
        result = await client.create_hunt(
            request.hunt_name,
            request.artifact_name,
            request.description,
            request.parameters
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create hunt: {str(e)}"
        )


@router.get("/hunts/{hunt_id}/results")
async def get_hunt_results(
    hunt_id: str,
    limit: int = 1000,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get results from a hunt
    """
    config = velociraptor_configs.get(current_user.tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Velociraptor not configured for this tenant"
        )
    
    client = get_velociraptor_client(config.base_url, config.api_key)
    try:
        results = await client.get_hunt_results(hunt_id, limit=limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch hunt results: {str(e)}"
        )
