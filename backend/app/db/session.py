"""
Database Session Management

This module handles database session creation and management:
- Session factory configuration
- Connection pooling
- Session lifecycle management
- Dependency injection for FastAPI
"""

from typing import Generator, AsyncGenerator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE ENGINE CONFIGURATION
# ============================================================================

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before using them
    poolclass=QueuePool,
)

# Create async SQLAlchemy engine
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
)


# ============================================================================
# CONNECTION EVENT LISTENERS
# ============================================================================

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """
    Event listener for new database connections.
    Can be used for connection-level configuration.
    """
    logger.debug("New database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """
    Event listener when a connection is checked out from the pool.
    """
    logger.debug("Connection checked out from pool")


# ============================================================================
# SESSION FACTORY
# ============================================================================

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False
)


# ============================================================================
# DATABASE SESSION DEPENDENCY
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    
    Usage in routes:
    ```python
    @app.get("/items")
    def read_items(db: Session = Depends(get_db)):
        items = db.query(Item).all()
        return items
    ```
    
    Yields:
        Session: SQLAlchemy database session
        
    Note:
        - Session is automatically closed after request
        - Transactions are rolled back on exception
        - Use this for all database operations in routes
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    
    Usage in async routes:
    ```python
    @app.get("/items")
    async def read_items(db: AsyncSession = Depends(get_async_db)):
        result = await db.execute(select(Item))
        items = result.scalars().all()
        return items
    ```
    
    Yields:
        AsyncSession: SQLAlchemy async database session
        
    Note:
        - Session is automatically closed after request
        - Transactions are rolled back on exception
        - Use this for all async database operations in routes
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception as e:
            logger.error(f"Database session error: {str(e)}")
            await db.rollback()
            raise


def get_db_session() -> Session:
    """
    Get a database session directly (not as a dependency).
    
    Usage in services:
    ```python
    db = get_db_session()
    try:
        # Use db session
        pass
    finally:
        db.close()
    ```
    
    Returns:
        Session: SQLAlchemy database session
        
    Note:
        - Caller is responsible for closing the session
        - Use DatabaseSession context manager for automatic cleanup
    """
    return SessionLocal()


# ============================================================================
# DATABASE UTILITIES
# ============================================================================

def init_db() -> None:
    """
    Initialize database.
    Create all tables defined in models.
    
    Note: In production, use Alembic migrations instead.
    This is mainly for development and testing.
    """
    from app.db.base import Base
    from app.db.models import (
        user, organization, bot, knowledge_base, 
        conversation, subscription, audit_log
    )
    
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


def drop_db() -> None:
    """
    Drop all database tables.
    
    Warning: This will delete all data!
    Use only in development/testing.
    """
    from app.db.base import Base
    
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped")


def check_db_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


# ============================================================================
# CONTEXT MANAGER FOR SESSIONS
# ============================================================================

class DatabaseSession:
    """
    Context manager for database sessions.
    
    Usage:
    ```python
    with DatabaseSession() as db:
        user = db.query(User).first()
    ```
    """
    
    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
        self.db.close()


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "get_db_session",
    "init_db",
    "drop_db",
    "check_db_connection",
    "DatabaseSession"
]

