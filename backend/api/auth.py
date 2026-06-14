"""JWT cookie authentication helpers and dependencies."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, Response
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.api.database import get_db
from backend.api.models import User

CONSTANTS: dict[str, Any] = {
    "JWT_ALGORITHM": "HS256",
    "JWT_SECRET_ENV": "JWT_SECRET",
    "JWT_EXPIRE_MINUTES_ENV": "JWT_EXPIRE_MINUTES",
    "DEFAULT_JWT_EXPIRE_MINUTES": 60 * 24 * 7,
    "COOKIE_NAME": "agrigraph_access_token",
    "COOKIE_SECURE_ENV": "COOKIE_SECURE",
    "DEV_JWT_SECRET": "change-me-in-production-use-env-jwt-secret",
}


def get_jwt_secret() -> str:
    """Return JWT signing secret from environment."""
    secret = os.getenv(CONSTANTS["JWT_SECRET_ENV"], CONSTANTS["DEV_JWT_SECRET"])
    if secret == CONSTANTS["DEV_JWT_SECRET"] and os.getenv(CONSTANTS["COOKIE_SECURE_ENV"], "").lower() == "true":
        raise RuntimeError("JWT_SECRET must be set when COOKIE_SECURE=true.")
    return secret


def get_token_expire_minutes() -> int:
    """Return access token lifetime in minutes."""
    raw = os.getenv(CONSTANTS["JWT_EXPIRE_MINUTES_ENV"])
    if raw is None:
        return int(CONSTANTS["DEFAULT_JWT_EXPIRE_MINUTES"])
    return int(raw)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    """Create a signed JWT for the given user id."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=get_token_expire_minutes())
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, get_jwt_secret(), algorithm=CONSTANTS["JWT_ALGORITHM"])


def set_auth_cookie(response: Response, token: str) -> None:
    """Attach httpOnly auth cookie to the response."""
    secure = os.getenv(CONSTANTS["COOKIE_SECURE_ENV"], "false").lower() == "true"
    max_age = get_token_expire_minutes() * 60
    response.set_cookie(
        key=CONSTANTS["COOKIE_NAME"],
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Remove auth cookie from the response."""
    response.delete_cookie(key=CONSTANTS["COOKIE_NAME"], path="/")


def _decode_token(token: str) -> str:
    """Decode JWT and return user id subject."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[CONSTANTS["JWT_ALGORITHM"]])
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        return str(subject)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.") from exc


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Return authenticated user from httpOnly cookie or raise 401."""
    token = request.cookies.get(CONSTANTS["COOKIE_NAME"])
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    user_id = _decode_token(token)
    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return user
