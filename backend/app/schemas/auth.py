"""Pydantic schemas for authentication and user management."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

SAFE_DEFAULT_ROLE = "viewer"
SAFE_DEFAULT_JURISDICTION = "GLOBAL"
ALLOWED_JURISDICTIONS = {"GLOBAL", "EU", "US", "INDIA", "HIPAA", "GDPR"}
ALLOWED_ROLES = {"admin", "compliance_officer", "analyst", "auditor", "viewer"}


class UserRegisterRequest(BaseModel):
    """Public registration request.
    
    Security: Role cannot be specified by the client during public registration.
    All self-registered users are assigned the safe default 'viewer' role.
    """
    email: str = Field(..., pattern=r"^[\w\.\+\-]+@[\w\.\-]+\.\w+$", description="Valid email address.")
    password: str = Field(..., min_length=8, max_length=128, description="Password must be at least 8 characters.")
    jurisdiction: str = Field(default=SAFE_DEFAULT_JURISDICTION, description="User's regional jurisdiction.")


class UserLoginRequest(BaseModel):
    email: str = Field(..., pattern=r"^[\w\.\+\-]+@[\w\.\-]+\.\w+$")
    password: str = Field(..., min_length=1)


class UserRoleUpdateRequest(BaseModel):
    """Admin-only schema for updating a user's role and jurisdiction."""
    role: str = Field(..., description="Role to assign (admin, compliance_officer, analyst, auditor, viewer)")
    jurisdiction: str | None = Field(default=None, description="Updated jurisdiction code")


class UserProvisionRequest(BaseModel):
    """Admin-only schema for provisioning users with pre-assigned roles."""
    email: str = Field(..., pattern=r"^[\w\.\+\-]+@[\w\.\-]+\.\w+$")
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="viewer")
    jurisdiction: str = Field(default=SAFE_DEFAULT_JURISDICTION)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user_id: uuid.UUID
    email: str
    role: str
    jurisdiction: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    jurisdiction: str
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

