"""SQLAlchemy database engine and session factory."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

CONSTANTS: dict[str, Any] = {
    "DEFAULT_DATABASE_URL": "postgresql+psycopg://agrigraph:agrigraph@localhost:5432/agrigraph",
    "ENV_DATABASE_URL": "DATABASE_URL",
}


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


def get_database_url() -> str:
    """Return database URL from environment or prototype default."""
    return os.getenv(CONSTANTS["ENV_DATABASE_URL"], CONSTANTS["DEFAULT_DATABASE_URL"])


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create database tables if they do not exist."""
    from backend.api import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for request-scoped dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
