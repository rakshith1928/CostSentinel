"""Request History model for PostgreSQL + TimescaleDB."""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_session_no_yield


class RequestHistory:
    """
    Canonical schema for durable request history in PostgreSQL.
    
    This table is designed for TimescaleDB hypertable conversion.
    Partitioned by timestamp for efficient 90-day retention queries.
    
    Fields:
        id: Deterministic request ID (format: req_{timestamp}_{hash})
        timestamp: ISO 8601 UTC timestamp of the request
        user_id: User identifier from auth context
        team: Optional team identifier
        model: Actual model used (post-fallback)
        original_model: Originally requested model
        input_tokens: Prompt token count
        output_tokens: Completion token count
        total_tokens: Sum of input and output tokens
        blocked: Whether the request was blocked by budget/rate policy
        downgraded: Whether the model was downgraded
        block_reason: Reason code if blocked
        latency_ms: Total request latency in milliseconds
        created_at: Record creation timestamp
        expires_at: TTL field for 90-day auto-deletion
    """
    
    __tablename__ = "request_history"
    __table_args__ = (
        Index("idx_timestamp", "timestamp"),
        Index("idx_user_id", "user_id"),
        Index("idx_team", "team"),
        Index("idx_model", "model"),
        Index("idx_blocked", "blocked"),
        Index("idx_expires_at", "expires_at"),
    )
    
    @classmethod
    async def create_table(cls, session: AsyncSession):
        """Create the request_history table with TimescaleDB extension."""
        await session.execute(text("""
            -- Enable TimescaleDB extension
            CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
        """))
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
            );
        """))
        await session.commit()
        
        # Convert to hypertable for time-partitioning
        await session.execute(text("""
            SELECT create_hypertable('request_history', 'timestamp', if_not_exists => TRUE);
        """))
        await session.commit()
        
        # Add retention policy (90 days)
        await session.execute(text("""
            SELECT add_retention_policy(
                'request_history',
                INTERVAL '90 days',
                if_not_exists => TRUE
            );
        """))
        await session.commit()
    
    @classmethod
    async def insert(cls, session: AsyncSession, data: dict):
        """Insert a request history record."""
        from sqlalchemy import insert as sql_insert
        
        stmt = sql_insert(cls.__table__).values(**data)
        result = await session.execute(stmt)
        await session.commit()
        return result
    
    @classmethod
    async def find_by_id(cls, session: AsyncSession, request_id: str):
        """Find a request by ID."""
        stmt = select(cls.__table__).where(cls.__table__.c.id == request_id)
        result = await session.execute(stmt)
        return result.first()
    
    @classmethod
    async def find_by_user(
        cls,
        session: AsyncSession,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ):
        """Find requests by user ID with pagination."""
        stmt = (
            select(cls.__table__)
            .where(cls.__table__.c.user_id == user_id)
            .order_by(cls.__table__.c.timestamp.desc())
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
        limit: int = 1000
    ):
        """Find requests in a time range."""
        stmt = (
            select(cls.__table__)
            .where(cls.__table__.c.timestamp >= start_time)
            .where(cls.__table__.c.timestamp <= end_time)
            .order_by(cls.__table__.c.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.all()
