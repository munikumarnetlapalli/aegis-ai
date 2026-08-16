"""Authentication and User Management API routes.

Provides:
- POST /auth/register              — public user registration (strictly assigns safe 'viewer' role)
- POST /auth/login                 — user authentication returning signed JWT Bearer token
- GET  /auth/me                    — profile and role/jurisdiction inspection for current user
- POST /auth/users/{user_id}/role  — admin-only endpoint to update user roles & jurisdiction
- POST /auth/provision             — admin-only endpoint to provision users with custom roles
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ALLOWED_JURISDICTIONS,
    ALLOWED_ROLES,
    SAFE_DEFAULT_JURISDICTION,
    SAFE_DEFAULT_ROLE,
    TokenResponse,
    UserLoginRequest,
    UserProvisionRequest,
    UserRegisterRequest,
    UserResponse,
    UserRoleUpdateRequest,
)
from app.security.audit import audit_log
from app.security.auth import create_access_token
from app.security.dependencies import get_current_user, require_roles
from app.security.password import hash_password, verify_password
from app.security.rate_limit import check_rate_limit_or_raise

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register_user(
    body: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user account.
    
    Security:
        - Public registration strictly assigns the safe default 'viewer' role.
        - Client cannot supply or escalate to 'admin' or other privileged roles.
        - Jurisdiction is validated against allowed regions, defaulting to GLOBAL.
    """
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"

    await check_rate_limit_or_raise(
        request=request,
        scope="auth_register",
        max_requests=settings.rate_limit_auth_per_minute,
    )

    # Check for existing email
    normalized_email = body.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        audit_log(
            "AUTH_REGISTER_FAILED",
            email=normalized_email,
            ip_address=client_ip,
            status="FAILURE",
            details={"reason": "Email already registered"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "A user with this email already exists."},
        )

    # Validate jurisdiction against allowed list, fallback to GLOBAL
    jurisdiction_candidate = (body.jurisdiction or "").strip().upper()
    effective_jurisdiction = (
        jurisdiction_candidate
        if jurisdiction_candidate in ALLOWED_JURISDICTIONS
        else SAFE_DEFAULT_JURISDICTION
    )

    # Enforce safe default role
    assigned_role = SAFE_DEFAULT_ROLE

    user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        hashed_password=hash_password(body.password),
        role=assigned_role,
        jurisdiction=effective_jurisdiction,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    audit_log(
        "AUTH_REGISTER_SUCCESS",
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        jurisdiction=user.jurisdiction,
        ip_address=client_ip,
        status="SUCCESS",
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT token",
)
async def login_user(
    body: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Validate credentials and return signed JWT Bearer access token."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"

    await check_rate_limit_or_raise(
        request=request,
        scope="auth_login",
        max_requests=settings.rate_limit_auth_per_minute,
    )

    normalized_email = body.email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        audit_log(
            "AUTH_LOGIN_FAILED",
            email=normalized_email,
            ip_address=client_ip,
            status="FAILURE",
            details={"reason": "Invalid email or password"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        audit_log(
            "AUTH_LOGIN_FAILED",
            user_id=str(user.id),
            email=normalized_email,
            ip_address=client_ip,
            status="FAILURE",
            details={"reason": "Account is inactive"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Account is disabled."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        jurisdiction=user.jurisdiction,
    )

    audit_log(
        "AUTH_LOGIN_SUCCESS",
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        jurisdiction=user.jurisdiction,
        ip_address=client_ip,
        status="SUCCESS",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
        user_id=user.id,
        email=user.email,
        role=user.role,
        jurisdiction=user.jurisdiction,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile and permissions",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile, role, and jurisdiction of the authenticated user."""
    return UserResponse.model_validate(current_user)


# ── Admin-Only Provisioning & Role Management ──────────────────────────────────

@router.post(
    "/users/{user_id}/role",
    response_model=UserResponse,
    summary="Admin: Update a user's role and jurisdiction",
)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdateRequest,
    current_admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Assign or modify a user's role. Restricted strictly to administrators."""
    target_role = body.role.strip().lower()
    if target_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ROLE",
                "message": f"Role '{target_role}' is invalid. Allowed roles: {list(ALLOWED_ROLES)}",
            },
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": f"User {user_id} not found."},
        )

    old_role = user.role
    user.role = target_role

    if body.jurisdiction is not None:
        target_jur = body.jurisdiction.strip().upper()
        if target_jur in ALLOWED_JURISDICTIONS:
            user.jurisdiction = target_jur

    await db.commit()
    await db.refresh(user)

    audit_log(
        "USER_ROLE_MODIFIED",
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        jurisdiction=user.jurisdiction,
        status="SUCCESS",
        details={
            "admin_id": str(current_admin.id),
            "admin_email": current_admin.email,
            "old_role": old_role,
            "new_role": target_role,
        },
    )
    return UserResponse.model_validate(user)


@router.post(
    "/provision",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Provision a new user with custom role",
)
async def provision_user(
    body: UserProvisionRequest,
    current_admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Provision a user account with explicit role and jurisdiction. Admin-only."""
    target_role = body.role.strip().lower()
    if target_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ROLE",
                "message": f"Role '{target_role}' is invalid. Allowed roles: {list(ALLOWED_ROLES)}",
            },
        )

    normalized_email = body.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "A user with this email already exists."},
        )

    jurisdiction_candidate = (body.jurisdiction or "").strip().upper()
    effective_jurisdiction = (
        jurisdiction_candidate
        if jurisdiction_candidate in ALLOWED_JURISDICTIONS
        else SAFE_DEFAULT_JURISDICTION
    )

    user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        hashed_password=hash_password(body.password),
        role=target_role,
        jurisdiction=effective_jurisdiction,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    audit_log(
        "USER_PROVISIONED_BY_ADMIN",
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        jurisdiction=user.jurisdiction,
        status="SUCCESS",
        details={"admin_id": str(current_admin.id), "admin_email": current_admin.email},
    )
    return UserResponse.model_validate(user)
