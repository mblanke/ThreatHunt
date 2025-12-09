from pydantic import BaseModel, EmailStr
from typing import Optional


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: Optional[str] = None
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
    totp_code: Optional[str] = None


class UserRegister(BaseModel):
    """User registration request schema"""
    username: str
    password: str
    email: Optional[EmailStr] = None
    tenant_id: Optional[int] = None
    role: str = "user"


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request schema"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema"""
    token: str
    new_password: str


class TwoFactorSetup(BaseModel):
    """2FA setup response schema"""
    secret: str
    qr_code_uri: str


class TwoFactorVerify(BaseModel):
    """2FA verification schema"""
    code: str
