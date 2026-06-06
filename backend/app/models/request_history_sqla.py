"""Request History model for PostgreSQL + TimescaleDB."""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    Index,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_session_no_yield


metadata = MetaData()


request_history = Table(
    "request_history",
    metadata,
    Column("id", String, primary_key=True),
    Column("timestamp", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("user_id", String, nullable=False),
    Column("team", String, nullable=True),
    Column("model", String, nullable=False),
    Column("original_model", String, nullable=False),
    Column("input_tokens", Integer, nullable=False, server_default=text("0")),
    Column("output_tokens", Integer, nullable=False, server_default=text("0")),
    Column("total_tokens", Integer, nullable=False, server_default=text("0")),
    Column("blocked", Boolean, nullable=False, server_default=text("FALSE")),
    Column("downgraded", Boolean, nullable=False, server_default=text("FALSE")),
    Column("block_reason", String, nullable=True),
    Column("latency_ms", Integer, nullable=False, server_default=text("0")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Index("idx_timestamp", "timestamp"),
    Index("idx_user_id", "user_id"),
    Index("idx_team", "team"),
    Index("idx_model", "model"),
    Index("idx_blocked", "blocked"),
    Index("idx_expires_at", "expires_at"),
)


RequestHistory = request_history


class RequestHistoryRepo:
    """Repository methods for request_history table operations."""

    @classmethod
    async def create_table(cls, session: AsyncSession):
        """Create the request_history table with TimescaleDB extension."""
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        await session.commit()

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS request_history (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_id TEXT NOT NULL,
                team TEXT,
                model TEXT NOT NULL,
                original_model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                blocked BOOLEAN NOT NULL DEFAULT FALSE,
                downgraded BOOLEAN NOT NULL DEFAULT FALSE,
                block_reason TEXT,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL
            )
        """))
        await session.commit()

        await session.execute(text("""
            SELECT create_hypertable('request_history', 'timestamp', if_not_exists => TRUE)
        """))
        await session.commit()

        await session.execute(text("""
            SELECT add_retention_policy(
                'request_history',
                INTERVAL '90 days',
                if_not_exists => TRUE
            )
        """))
        await session.commit()

    @classmethod
    async def insert(cls, session: AsyncSession, data: dict):
        """Insert a request history record. Returns the insert result."""
        from sqlalchemy import insert as sql_insert
        stmt = sql_insert(request_history).values(**data)
        result = await session.execute(stmt)
        await session.commit()
        return result

    @classmethod
    async def find_by_id(cls, session: AsyncSession, request_id: str):
        """Find a request by ID."""
        stmt = select(request_history).where(request_history.c.id == request_id)
        result = await session.execute(stmt)
        return result.first()

    @classmethod
    async def find_by_user(
        cls,
        session: AsyncSession,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ):
        """Find requests by user ID with pagination."""
        stmt = (
            select(request_history)
            .where(request_history.c.user_id == user_id)
            .order_by(request_history.c.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return result.all()

    @classmethod
    async def find_by_time_range(
        cls,
        session: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ):
        """Find requests in a time range."""
        stmt = (
            select(request_history)
            .where(request_history.c.timestamp >= start_time)
            .where(request_history.c.timestamp <= end_time)
            .order_by(request_history.c.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.all()
