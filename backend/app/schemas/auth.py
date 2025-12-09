from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    role: Optional[str] = None


class UserLogin(BaseModel):
    """User login request schema"""
    username: str
    password: str


class UserRegister(BaseModel):
    """User registration request schema"""
    username: str
    password: str
    tenant_id: Optional[int] = None
    role: str = "user"
