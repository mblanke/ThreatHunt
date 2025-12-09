from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_role, get_tenant_id
from app.core.playbook_engine import get_playbook_engine
from app.models.user import User
from app.models.playbook import Playbook, PlaybookExecution
from app.schemas.playbook import PlaybookCreate, PlaybookRead, PlaybookUpdate, PlaybookExecutionRead

router = APIRouter()


@router.get("/", response_model=List[PlaybookRead])
async def list_playbooks(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """List playbooks scoped to user's tenant"""
    playbooks = db.query(Playbook).filter(
        Playbook.tenant_id == tenant_id
    ).offset(skip).limit(limit).all()
    return playbooks


@router.post("/", response_model=PlaybookRead, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    playbook_data: PlaybookCreate,
    current_user: User = Depends(require_role(["admin"])),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """Create a new playbook (admin only)"""
    playbook = Playbook(
        tenant_id=tenant_id,
        created_by=current_user.id,
        **playbook_data.dict()
    )
    db.add(playbook)
    db.commit()
    db.refresh(playbook)
    return playbook


@router.get("/{playbook_id}", response_model=PlaybookRead)
async def get_playbook(
    playbook_id: int,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """Get playbook by ID"""
    playbook = db.query(Playbook).filter(
        Playbook.id == playbook_id,
        Playbook.tenant_id == tenant_id
    ).first()
    
    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )
    
    return playbook


@router.post("/{playbook_id}/execute", response_model=PlaybookExecutionRead)
async def execute_playbook(
    playbook_id: int,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """Execute a playbook"""
    playbook = db.query(Playbook).filter(
        Playbook.id == playbook_id,
        Playbook.tenant_id == tenant_id
    ).first()
    
    if not playbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found"
        )
    
    if not playbook.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playbook is disabled"
        )
    
    # Create execution record
    execution = PlaybookExecution(
        playbook_id=playbook_id,
        tenant_id=tenant_id,
        status="running",
        triggered_by=current_user.id
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Execute playbook asynchronously
    try:
        engine = get_playbook_engine()
        result = await engine.execute_playbook(
            {"actions": playbook.actions},
            {"tenant_id": tenant_id, "user_id": current_user.id}
        )
        
        execution.status = result["status"]
        execution.result = result
        from datetime import datetime, timezone
        execution.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
    
    db.commit()
    db.refresh(execution)
    
    return execution


@router.get("/{playbook_id}/executions", response_model=List[PlaybookExecutionRead])
async def list_playbook_executions(
    playbook_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """List executions for a playbook"""
    executions = db.query(PlaybookExecution).filter(
        PlaybookExecution.playbook_id == playbook_id,
        PlaybookExecution.tenant_id == tenant_id
    ).order_by(PlaybookExecution.started_at.desc()).offset(skip).limit(limit).all()
    
    return executions
