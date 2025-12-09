from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema"""
    username: str
    email: Optional[EmailStr] = None
    role: str = "user"
    tenant_id: int


class UserCreate(UserBase):
    """Schema for creating a user"""
    password: str


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    """Schema for reading user data (excludes password_hash and secrets)"""
    id: int
    is_active: bool
    email_verified: bool
    totp_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True
