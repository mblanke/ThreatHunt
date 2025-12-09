from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary containing user_id, tenant_id, role
        expires_delta: Optional expiration time delta
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def create_refresh_token() -> str:
    """
    Create a secure random refresh token
    
    Returns:
        Random token string
    """
    return secrets.token_urlsafe(32)


def create_reset_token() -> str:
    """
    Create a secure random password reset token
    
    Returns:
        Random token string
    """
    return secrets.token_urlsafe(32)


def generate_totp_secret() -> str:
    """
    Generate a TOTP secret for 2FA
    
    Returns:
        Base32 encoded secret
    """
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code
    
    Args:
        secret: TOTP secret
        code: 6-digit code from authenticator app
    
    Returns:
        True if code is valid
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_totp_uri(secret: str, username: str) -> str:
    """
    Get TOTP provisioning URI for QR code
    
    Args:
        secret: TOTP secret
        username: User's username
    
    Returns:
        otpauth:// URI
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="VelociCompanion")
