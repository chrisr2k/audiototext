"""
Database configuration and session management.

Supports both SQLite (development) and PostgreSQL (production).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


def _get_engine_kwargs():
    """Get engine kwargs based on database type."""
    kwargs = {}
    if "sqlite" in settings.DATABASE_URL:
        kwargs["connect_args"] = {"check_same_thread": False}
    elif "postgresql" in settings.DATABASE_URL:
        # PostgreSQL connection pool settings for production
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 3600
    return kwargs


engine = create_engine(
    settings.DATABASE_URL,
    **_get_engine_kwargs(),
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
