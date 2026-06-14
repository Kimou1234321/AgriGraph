"""Authentication API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.api.auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
    verify_password,
)
from backend.api.database import get_db
from backend.api.models import User

CONSTANTS: dict[str, Any] = {
    "ROUTER_PREFIX": "/api/auth",
    "MIN_PASSWORD_LENGTH": 8,
}

router = APIRouter(prefix=CONSTANTS["ROUTER_PREFIX"], tags=["auth"])


class SignupRequest(BaseModel):
    """Signup payload."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public user profile."""

    id: str
    email: str
    full_name: str | None
    created_at: str


def _user_to_response(user: User) -> UserResponse:
    """Map ORM user to API response."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/signup", response_model=UserResponse)
async def signup(payload: SignupRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    """Register a new user and set auth cookie."""
    if len(payload.password) < CONSTANTS["MIN_PASSWORD_LENGTH"]:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return _user_to_response(user)


@router.post("/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    """Authenticate user and set auth cookie."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(str(user.id))
    set_auth_cookie(response, token)
    return _user_to_response(user)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear auth cookie."""
    clear_auth_cookie(response)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return current authenticated user."""
    return _user_to_response(current_user)
