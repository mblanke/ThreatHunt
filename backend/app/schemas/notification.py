from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationBase(BaseModel):
    """Base notification schema"""
    title: str
    message: str
    notification_type: str
    link: Optional[str] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a notification"""
    user_id: int
    tenant_id: int


class NotificationRead(NotificationBase):
    """Schema for reading notification data"""
    id: int
    user_id: int
    tenant_id: int
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationUpdate(BaseModel):
    """Schema for updating a notification"""
    is_read: bool
