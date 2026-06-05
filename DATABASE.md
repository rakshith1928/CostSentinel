# Database Design: PostgreSQL + TimescaleDB

**Last Updated:** 2026-05-22
**Status:** Implemented
**Type:** Durable Request History Storage

---

## Executive Summary

CostSentinel uses **PostgreSQL with TimescaleDB** for durable request history storage. This provides:

- No vendor lock-in (standard SQL)
- Better analytics with full SQL support
- Lower cost at scale
- Automatic 90-day retention via TimescaleDB
- Time-series optimized queries

---

## Architecture

### Storage Layers

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Hot State** | Redis | Budget counters, rate limits, real-time state |
| **Durable History** | PostgreSQL + TimescaleDB | Request audit trail, analytics source |
| **Cache** | Redis | Session data, temporary aggregations |

### Why TimescaleDB?

TimescaleDB is a PostgreSQL extension that adds:

- **Hypertables**: Automatic time-based partitioning
- **Retention policies**: Automatic data deletion after N days
- **Compression**: Columnar storage for old data
- **Continuous aggregates**: Materialized views for analytics

---

## Schema Design

### Primary Table: `request_history`

```sql
CREATE TABLE request_history (
    -- Primary Key
    id TEXT PRIMARY KEY,

    -- Core Fields (14 canonical fields)
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

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
```

### Hypertable Conversion

```sql
-- Convert to hypertable (time-partitioned)
SELECT create_hypertable('request_history', 'timestamp');

-- Add 90-day retention policy
SELECT add_retention_policy('request_history', INTERVAL '90 days');
```

### Indexes

```sql
-- Time-range queries (most common)
CREATE INDEX idx_timestamp ON request_history(timestamp DESC);

-- User-specific lookups
CREATE INDEX idx_user_id ON request_history(user_id);

-- Team analytics
CREATE INDEX idx_team ON request_history(team);

-- Model performance analysis
CREATE INDEX idx_model ON request_history(model);

-- Blocked request investigation
CREATE INDEX idx_blocked ON request_history(blocked) WHERE blocked = TRUE;

-- TTL monitoring
CREATE INDEX idx_expires_at ON request_history(expires_at);
```

---

## TTL Retention Policy

### Overview

CostSentinel enforces a **90-day retention policy** on all request history records. The `expires_at` field is calculated at write time as `NOW() + HISTORY_TTL_DAYS` and TimescaleDB automatically deletes records past their expiry.

### Configuration

**Environment variable** (in `.env`):
```env
HISTORY_TTL_DAYS=90
```

**Python setting** (in `backend/app/config.py`):
```python
history_ttl_days: int = 90
```

### How It Works

1. **Write Time**: `expires_at` = `datetime.utcnow() + timedelta(days=90)`
2. **Automatic Deletion**: TimescaleDB background job deletes records where `expires_at < NOW()`
3. **Frequency**: Retention job runs every hour by default
4. **No Manual Cleanup**: No cron jobs or custom delete logic required

### Verification Queries

#### 1. Check Retention Policy is Active

```sql
SELECT
    hypertable_name,
    config_interval::interval AS retention_period,
    job_id
FROM timescaledb_information.jobs j
JOIN timescaledb_information.retention_policies rp
    ON j.hypertable_name = rp.hypertable_name
WHERE j.application_name LIKE '%Retention%'
  AND rp.hypertable_name = 'request_history';
```

**Expected output:**
```
hypertable_name  | retention_period | job_id
-----------------+------------------+--------
request_history  | 90 days          | <number>
```

#### 2. Check Oldest Record (Should Be Within 90 Days)

```sql
SELECT
    MIN(timestamp) AS oldest_record,
    MAX(timestamp) AS newest_record,
    COUNT(*) AS total_records,
    MIN(expires_at) AS earliest_expiry,
    EXTRACT(DAY FROM (NOW() - MIN(timestamp))) AS days_old
FROM request_history;
```

#### 3. Count Records Expiring Soon

```sql
SELECT COUNT(*) AS records_to_be_deleted
FROM request_history
WHERE expires_at < NOW() + INTERVAL '1 day';
```

#### 4. Verify TTL Field is Indexed

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'request_history'
  AND indexname LIKE '%expires%';
```

### Monitoring Queries

#### Alert: Records Older Than 91 Days (Should Be 0)

```sql
SELECT COUNT(*) AS stale_records
FROM request_history
WHERE timestamp < NOW() - INTERVAL '91 days';
```

**Action if > 0:** Retention policy is not running. Check TimescaleDB jobs.

#### Alert: Retention Job Status

```sql
SELECT
    hypertable_name,
    last_run_started_at,
    last_run_finished_at,
    last_run_status,
    last_run_duration
FROM timescaledb_information.job_stats
WHERE application_name LIKE '%Retention%'
ORDER BY last_run_started_at DESC
LIMIT 1;
```

**Expected:** `last_run_status` = `'Success'`

#### Disk Usage

```sql
SELECT
    hypertable_name,
    pg_size_pretty(hypertable_size(hypertable_name)) AS size
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'request_history';
```

### Modifying Retention Period

To change the retention period:

1. Update `HISTORY_TTL_DAYS` in your `.env` file
2. Remove the old policy:

```sql
SELECT remove_retention_policy('request_history');
```

3. Add the new policy:

```sql
SELECT add_retention_policy(
    'request_history',
    INTERVAL '<N> days',
    if_not_exists => TRUE
);
```

---

## Configuration

### Environment Variables

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
DATABASE_ECHO=false          # Set to 'true' for SQL logging

# Optional (defaults shown)
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
HISTORY_TTL_DAYS=90
```

### Connection String Format

```
postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>?sslmode=require
```

**Example (TimescaleDB Cloud):**
```
postgresql+asyncpg://tsdbadmin:password@service-id.aws.cloud.timescale.com:5432/tsdb?sslmode=require
```

---

## Implementation

### Files

| File | Purpose |
|------|---------|
| `backend/app/database.py` | Async engine, session management |
| `backend/app/config.py` | Settings with Pydantic v2 |
| `backend/app/models/request_history_sqla.py` | SQLAlchemy model |
| `backend/app/test_database.py` | Unit tests |
| `backend/scripts/verify_ttl.py` | TTL verification script |
| `backend/README.md` | Complete setup guide |

### Initialization

```python
from app.database import init_database, close_database, get_session

# On application startup
await init_database()

# Get session for queries
async with get_session() as session:
    # Use session
    pass

# On application shutdown
await close_database()
```

### Insert Example

```python
from app.models.request_history import RequestHistory

async def log_request(session: AsyncSession, data: dict):
    history = RequestHistory(
        id=data["request_id"],
        timestamp=datetime.utcnow(),
        user_id=data["user_id"],
        # ... other fields
    )
    session.add(history)
    await session.commit()
```

### Query Examples

#### Find by ID

```python
from sqlalchemy import select
from app.models.request_history_sqla import RequestHistory

stmt = select(RequestHistory).where(RequestHistory.id == request_id)
result = await session.execute(stmt)
return result.first()
```

#### Time Range Query

```python
from datetime import datetime, timedelta

start = datetime.utcnow() - timedelta(days=7)
end = datetime.utcnow()

stmt = (
    select(RequestHistory)
    .where(RequestHistory.timestamp >= start)
    .where(RequestHistory.timestamp <= end)
    .order_by(RequestHistory.timestamp.desc())
)
```

#### User History with Pagination

```python
stmt = (
    select(RequestHistory)
    .where(RequestHistory.user_id == user_id)
    .order_by(RequestHistory.timestamp.desc())
    .limit(100)
    .offset(offset)
)
```

---

## Performance

### Expected Latency (p95)

| Operation | Target | Notes |
|-----------|--------|-------|
| Insert (single) | <10ms | Async, non-blocking |
| Point query (by ID) | <5ms | Indexed primary key |
| Time range (1 day) | <50ms | Hypertable partition |
| User history (100 rows) | <100ms | With pagination |
| Aggregation (7 days) | <500ms | Pre-aggregated rollups |

### Optimization Strategies

1. **Hypertable chunking**: 1-day chunks for efficient time queries
2. **Compression**: Old data compressed to save storage
3. **Connection pooling**: 10 connections + 20 overflow
4. **Async I/O**: Non-blocking database operations

---

## Testing

### Run Tests

```bash
cd backend
python -m pytest app/test_database.py -v
python -m pytest app/models/test_request_history.py -v
python -m pytest app/test_security.py -v
```

### Test Connection

```python
import asyncio
from app.database import init_database, close_database

async def test():
    await init_database()
    print("Connected!")
    await close_database()

asyncio.run(test())
```

### Verify TTL Policy

```bash
cd backend
python scripts/verify_ttl.py
```

This script runs all verification queries and reports:
- Retention policy status
- Oldest record age
- Records expiring soon
- Index status
- Disk usage

---

## Troubleshooting

### Connection Refused

```bash
# Check service is running
docker ps | grep postgres  # For local
# Or check TimescaleDB Cloud dashboard

# Verify connection string
echo $DATABASE_URL
```

### Extra Fields Error

If you see `Extra inputs are not permitted`:
- Ensure `.env` doesn't have undefined fields
- Or add `extra="ignore"` to `SettingsConfigDict`

### SSL Mode Issues

For TimescaleDB Cloud, always include `?sslmode=require`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db?sslmode=require
```

### Hypertable Not Created

```sql
-- Manually create
SELECT create_hypertable('request_history', 'timestamp', if_not_exists => TRUE);
```

### Records Not Being Deleted

**Symptom:** Oldest record age exceeds 90 days

**Diagnosis:**
```sql
SELECT * FROM timescaledb_information.jobs
WHERE application_name LIKE '%Retention%';
```

**Fix:**
- Ensure TimescaleDB extension is enabled
- Verify retention policy exists
- Check TimescaleDB logs for errors

---

## Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [PostgreSQL Tutorial](https://www.postgresql.org/docs/)
- [TimescaleDB Cloud](https://console.cloud.timescale.com/)
- [backend/README.md](backend/README.md) - Complete setup guide

---

*This document is part of the CostSentinel Durable History milestone.*
