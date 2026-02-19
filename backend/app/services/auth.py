"""Authentication & security — JWT tokens, password hashing, role-based access.

Provides:
- Password hashing (bcrypt via passlib)
- JWT access/refresh token creation and verification
- FastAPI dependency for protecting routes
- Role-based enforcement (analyst, admin, viewer)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db.models import User

logger = logging.getLogger(__name__)

# ── Password hashing ─────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT tokens ────────────────────────────────────────────────────────

ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    sub: str  # user_id
    role: str
    exp: datetime
    type: str  # "access" or "refresh"


def create_access_token(user_id: str, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_MINUTES
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expires,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_DAYS
    )
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expires,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_token_pair(user_id: str, role: str) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id, role),
        refresh_token=create_refresh_token(user_id, role),
        expires_in=settings.JWT_ACCESS_TOKEN_MINUTES * 60,
    )


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependencies ──────────────────────────────────────────────


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from JWT.

    When AUTH is disabled (no JWT secret configured), returns a default analyst user.
    """
    # If auth is disabled (dev mode), return a default user
    if settings.JWT_SECRET == "CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET":
        return User(
            id="dev-user",
            username="analyst",
            email="analyst@local",
            role="analyst",
            display_name="Dev Analyst",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(credentials.credentials)

    if token_data.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — use access token",
        )

    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user, but returns None instead of raising if no token."""
    if not credentials:
        if settings.JWT_SECRET == "CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET":
            return User(
                id="dev-user",
                username="analyst",
                email="analyst@local",
                role="analyst",
                display_name="Dev Analyst",
            )
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_role(*roles: str):
    """Dependency factory that requires the current user to have one of the specified roles."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}. You have: {user.role}",
            )
        return user

    return _check


# Convenience dependencies
require_analyst = require_role("analyst", "admin")
require_admin = require_role("admin")
