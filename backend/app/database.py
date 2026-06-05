"""PostgreSQL database client with async support."""

from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncSessionTransaction,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.config import settings


# ── Engine & Session ──────────────────────────────────────────────────────────

_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_transaction: Optional[AsyncSessionTransaction] = None


def get_engine() -> create_async_engine:
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized")
    return _engine


async def init_database():
    """Initialize the database engine and session factory."""
    global _engine, _session_factory
    
    # Parse SSL mode from DATABASE_URL if present, use connect_args for asyncpg
    connect_args = {}
    if "sslmode=require" in settings.database_url:
        connect_args["ssl"] = "require"
    
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=connect_args,
    )
    
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_database():
    """Close the database engine."""
    if _engine is not None:
        await _engine.dispose()


# ── Session Management ────────────────────────────────────────────────────────

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for dependency injection."""
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized")
    
    async with _session_factory() as session:
        yield session


async def get_session_no_yield() -> AsyncSession:
    """Get a database session without yield (for internal use)."""
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized")
    
    session = _session_factory()
    return session


# ── Helpers ───────────────────────────────────────────────────────────────────

async def execute_query(query, params: Optional[dict] = None):
    """Execute a raw SQL query."""
    async with get_session() as session:
        result = await session.execute(query, params or {})
        await session.commit()
        return result
