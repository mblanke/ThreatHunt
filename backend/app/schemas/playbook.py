from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class PlaybookBase(BaseModel):
    """Base playbook schema"""
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]]
    is_enabled: bool = True


class PlaybookCreate(PlaybookBase):
    """Schema for creating a playbook"""
    pass


class PlaybookUpdate(BaseModel):
    """Schema for updating a playbook"""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    is_enabled: Optional[bool] = None


class PlaybookRead(PlaybookBase):
    """Schema for reading playbook data"""
    id: int
    tenant_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlaybookExecutionRead(BaseModel):
    """Schema for playbook execution"""
    id: int
    playbook_id: int
    tenant_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]

    class Config:
        from_attributes = True
