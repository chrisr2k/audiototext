"""
Database configuration and session management.

Supports both SQLite (development) and PostgreSQL (production).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


def _get_engine_args():
    """Get engine connection args based on database type."""
    if "sqlite" in settings.DATABASE_URL:
        return {"check_same_thread": False}
    elif "postgresql" in settings.DATABASE_URL:
        # PostgreSQL connection pool settings for production
        return {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }
    return {}


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_get_engine_args(),
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
