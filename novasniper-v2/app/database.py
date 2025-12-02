"""
NovaSniper v2.0 Database Configuration
SQLAlchemy engine and session management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator

from app.config import settings
from app.models import Base

# Create engine based on database URL
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite-specific configuration
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DEBUG,
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL/MySQL configuration
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.DEBUG,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables (use with caution)"""
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database session (for background tasks)"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseManager:
    """Utility class for database operations"""
    
    @staticmethod
    def init_db():
        """Initialize database with tables"""
        create_tables()
    
    @staticmethod
    def reset_db():
        """Reset database (drop and recreate all tables)"""
        drop_tables()
        create_tables()
    
    @staticmethod
    def health_check() -> bool:
        """Check database connectivity"""
        try:
            with get_db_context() as db:
                db.execute("SELECT 1")
            return True
        except Exception:
            return False
