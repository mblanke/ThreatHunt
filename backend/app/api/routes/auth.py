from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import io
import qrcode

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, create_reset_token, generate_totp_secret,
    verify_totp, get_totp_uri
)
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.tenant import Tenant
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken
from app.schemas.auth import (
    Token, UserLogin, UserRegister, RefreshTokenRequest,
    PasswordResetRequest, PasswordResetConfirm,
    TwoFactorSetup, TwoFactorVerify
)
from app.schemas.user import UserRead, UserUpdate

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    Creates a new user with hashed password. If tenant_id is not provided,
    a default tenant is created or used.
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Handle tenant_id
    tenant_id = user_data.tenant_id
    if tenant_id is None:
        # Create or get default tenant
        default_tenant = db.query(Tenant).filter(Tenant.name == "default").first()
        if not default_tenant:
            default_tenant = Tenant(name="default", description="Default tenant")
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
        tenant_id = default_tenant.id
    else:
        # Verify tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
    
    # Create new user with hashed password
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        password_hash=hashed_password,
        role=user_data.role,
        tenant_id=tenant_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    
    Uses OAuth2 password flow for compatibility with OpenAPI docs.
    """
    # Find user by username
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Check 2FA if enabled (TOTP code should be in scopes for OAuth2)
    if user.totp_enabled:
        # For OAuth2 password flow, we'll check totp in scopes
        totp_code = form_data.scopes[0] if form_data.scopes else None
        if not totp_code or not verify_totp(user.totp_secret, totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "tenant_id": user.tenant_id,
            "role": user.role
        }
    )
    
    # Create refresh token
    refresh_token_str = create_refresh_token()
    refresh_token_obj = RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(refresh_token_obj)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user profile
    
    Returns the profile of the authenticated user.
    """
    return current_user


@router.put("/me", response_model=UserRead)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile
    
    Allows users to update their own profile information.
    """
    # Update username if provided
    if user_update.username is not None:
        # Check if new username is already taken
        existing_user = db.query(User).filter(
            User.username == user_update.username,
            User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = user_update.username
    
    # Update password if provided
    if user_update.password is not None:
        current_user.password_hash = get_password_hash(user_update.password)
    
    # Users cannot change their own role through this endpoint
    # (admin users should use the admin endpoints in /users)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    Provides a new access token without requiring login.
    """
    # Find refresh token
    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_request.refresh_token,
        RefreshToken.is_revoked == False
    ).first()
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if expired
    if refresh_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    
    # Get user
    user = db.query(User).filter(User.id == refresh_token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "tenant_id": user.tenant_id,
            "role": user.role
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_request.refresh_token,
        "token_type": "bearer"
    }


@router.post("/2fa/setup", response_model=TwoFactorSetup)
async def setup_two_factor(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Set up two-factor authentication
    
    Generates a TOTP secret and QR code URI for the user.
    """
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled"
        )
    
    # Generate secret
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    db.commit()
    
    # Get QR code URI
    qr_uri = get_totp_uri(secret, current_user.username)
    
    return {
        "secret": secret,
        "qr_code_uri": qr_uri
    }


@router.post("/2fa/verify")
async def verify_two_factor(
    verify_request: TwoFactorVerify,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Verify and enable two-factor authentication
    
    User must provide a valid TOTP code to enable 2FA.
    """
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled"
        )
    
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated. Call /2fa/setup first."
        )
    
    # Verify code
    if not verify_totp(current_user.totp_secret, verify_request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Enable 2FA
    current_user.totp_enabled = True
    db.commit()
    
    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_two_factor(
    verify_request: TwoFactorVerify,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Disable two-factor authentication
    
    User must provide a valid TOTP code to disable 2FA.
    """
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled"
        )
    
    # Verify code
    if not verify_totp(current_user.totp_secret, verify_request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Disable 2FA
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()
    
    return {"message": "2FA disabled successfully"}


@router.post("/password-reset/request")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset
    
    Sends a password reset email to the user (mock implementation).
    """
    # Find user by email
    user = db.query(User).filter(User.email == reset_request.email).first()
    
    # Don't reveal if email exists or not (security best practice)
    # Always return success even if email doesn't exist
    if user:
        # Create reset token
        reset_token = create_reset_token()
        reset_token_obj = PasswordResetToken(
            token=reset_token,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        db.add(reset_token_obj)
        db.commit()
        
        # TODO: Send email with reset link
        # For now, we'll just log it (in production, use an email service)
        print(f"Password reset token for {user.email}: {reset_token}")
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    reset_confirm: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm password reset with token
    
    Sets a new password for the user.
    """
    # Find reset token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == reset_confirm.token,
        PasswordResetToken.is_used == False
    ).first()
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Check if expired
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token expired"
        )
    
    # Get user
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = get_password_hash(reset_confirm.new_password)
    reset_token.is_used = True
    db.commit()
    
    return {"message": "Password reset successful"}
