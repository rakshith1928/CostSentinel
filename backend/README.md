# CostSentinel Backend

FastAPI + PostgreSQL + TimescaleDB backend for the CostSentinel LLM gateway with durable request history.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Database Setup](#database-setup)
- [TTL Retention Policy](#ttl-retention-policy)
- [Configuration](#configuration)
- [Testing](#testing)
- [API Endpoints](#api-endpoints)

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+ with TimescaleDB extension
- Redis 7+ (for budget/rate-limit hot state)

### Installation

```bash
# Clone the repository
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

Copy the example environment file and update with your settings:

```bash
cp ../.env.example ../.env
# Edit .env with your database credentials and settings
```

### Database Initialization

```bash
# Start PostgreSQL + TimescaleDB (using Docker Compose from project root)
cd ..
docker-compose up -d postgres

# Or use a local PostgreSQL installation
# See "Database Setup" section below
```

### Run the Application

```bash
cd backend
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

API documentation: `http://localhost:8000/docs`

---

## Architecture

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Server** | FastAPI | Request proxy, admin endpoints |
| **Hot State** | Redis | Budget counters, rate limits, real-time state |
| **Durable History** | PostgreSQL + TimescaleDB | Request audit trail, 90-day retention |
| **LLM Proxy** | Ollama | Model inference |

### Request Flow

```
User Request → FastAPI → Redis (budget check) → Ollama (inference)
                                ↓
                        PostgreSQL (async write)
                                ↓
                        TimescaleDB (90-day retention)
```

---

## Database Setup

### Option 1: Docker Compose (Recommended)

From the project root:

```bash
docker-compose up -d postgres
```

This starts PostgreSQL 16 with the TimescaleDB extension pre-installed.

### Option 2: Local PostgreSQL

1. Install PostgreSQL 16+ from https://www.postgresql.org/download/
2. Install TimescaleDB: https://docs.timescale.com/self-hosted/latest/install/
3. Create the database:

```bash
createdb -U postgres costsentinel
```

4. Enable TimescaleDB extension:

```sql
psql -U postgres -d costsentinel -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```

5. Update your `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/costsentinel
```

### Option 3: TimescaleDB Cloud

1. Sign up at https://console.cloud.timescale.com
2. Create a new service
3. Copy the connection string
4. Update your `.env`:

```env
DATABASE_URL=postgresql+asyncpg://tsdbadmin:password@service-id.cloud.timescale.com:5432/tsdb?sslmode=require
```

---

## TTL Retention Policy

### Overview

CostSentinel enforces a **90-day retention policy** on all request history records using TimescaleDB's automatic retention feature.

### How It Works

1. **Write Time**: When a request is recorded, `expires_at` is set to `NOW() + 90 days`
2. **Automatic Deletion**: TimescaleDB runs a background job that deletes records where `expires_at < NOW()`
3. **No Manual Cleanup**: No cron jobs or custom delete logic required
4. **Configurable**: TTL can be adjusted via `HISTORY_TTL_DAYS` environment variable

### Setup

The retention policy is configured automatically when the `request_history` table is created (see `backend/app/models/request_history_sqla.py`):

```sql
-- Create hypertable (time-partitioned)
SELECT create_hypertable('request_history', 'timestamp', if_not_exists => TRUE);

-- Add 90-day retention policy
SELECT add_retention_policy(
    'request_history',
    INTERVAL '90 days',
    if_not_exists => TRUE
);
```

### Manual Verification

Connect to your database and run these queries:

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

#### 2. Check Oldest Record

```sql
SELECT
    MIN(timestamp) AS oldest_record,
    MAX(timestamp) AS newest_record,
    COUNT(*) AS total_records,
    MIN(expires_at) AS earliest_expiry
FROM request_history;
```

**Expected output:** `oldest_record` should be within the last 90 days.

#### 3. Count Records Expiring Soon (next 24 hours)

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

**Expected output:** Index `idx_expires_at` should be listed.

### Monitoring Queries

#### Alert: Records Older Than 91 Days

```sql
-- Should return 0 (indicates retention is working)
SELECT COUNT(*) AS stale_records
FROM request_history
WHERE timestamp < NOW() - INTERVAL '91 days';
```

**Action if > 0:** Retention policy is not running. Check TimescaleDB jobs.

#### Alert: Retention Job Failed

```sql
-- Check last successful retention run
SELECT
    hypertable_name,
    last_run_started_at,
    last_run_finished_at,
    last_run_status
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

3. Add the new policy (replace `90 days` with your new value):

```sql
SELECT add_retention_policy(
    'request_history',
    INTERVAL '<N> days',
    if_not_exists => TRUE
);
```

4. Update the `HISTORY_TTL_DAYS` constant in `backend/app/config.py` (already configurable via env var)

### Troubleshooting

#### Records Not Being Deleted

**Symptom:** Oldest record age exceeds 90 days

**Diagnosis:**
```sql
-- Check if retention job is scheduled
SELECT * FROM timescaledb_information.jobs
WHERE application_name LIKE '%Retention%';
```

**Fix:**
- Ensure TimescaleDB extension is enabled
- Verify retention policy exists (see query above)
- Check TimescaleDB logs for errors

#### `add_retention_policy` Fails

**Error:** `relation "request_history" is not a hypertable`

**Fix:** Run the hypertable conversion first:
```sql
SELECT create_hypertable('request_history', 'timestamp', if_not_exists => TRUE);
```

#### Permission Denied

**Error:** `permission denied for function add_retention_policy`

**Fix:** Grant necessary privileges to your database user:
```sql
GRANT ALL ON SCHEMA timescaledb TO your_user;
```

---

## Configuration

All configuration is via environment variables (see `.env.example` in project root).

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `OLLAMA_URL` | Ollama service URL | `http://localhost:11434` |
| `WS_TOKEN_SECRET` | Secret for signing WS tokens | `<random-secret>` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_ECHO` | `false` | Log all SQL queries |
| `DATABASE_POOL_SIZE` | `10` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | `20` | Max overflow connections |
| `HISTORY_TTL_DAYS` | `90` | Request history retention period |
| `SENTINEL_API_KEY` | `""` | General admin API key |
| `HISTORY_API_ADMIN_KEY` | `""` | History API admin key |
| `ADMIN_USERS` | `""` | Comma-separated admin user IDs |

---

## Testing

### Run All Tests

```bash
cd backend
python -m pytest -v
```

### Run Specific Test Files

```bash
# Request history model tests
python -m pytest app/models/test_request_history.py -v

# Database client tests
python -m pytest app/test_database.py -v

# Security/auth tests
python -m pytest app/test_security.py -v
```

### Expected Output

All tests should pass (10/10 for each file).

---

## API Endpoints

### Admin Endpoints (require API key)

- `GET /v1/sentinel/users` - List all users
- `GET /v1/sentinel/usage/{user_id}` - Get user usage detail
- `PUT /v1/sentinel/budget/{user_id}` - Set user budget
- `DELETE /v1/sentinel/usage/{user_id}/reset` - Reset usage

### Auth Endpoints

- `POST /v1/sentinel/auth/ws-token` - Issue WebSocket token

### History Endpoints (Phase 3)

- `GET /v1/history/requests` - List request history (admin)
- `GET /v1/history/requests/{id}` - Get request detail (admin)
- `GET /v1/history/analytics/7day` - 7-day analytics (admin)

### Health Endpoints

- `GET /v1/health` - Service health check

---

## Project Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── request_history.py          # Pydantic model (canonical schema)
│   │   ├── request_history_sqla.py     # SQLAlchemy model (hypertable)
│   │   └── test_request_history.py     # Pydantic model tests
│   ├── routes/
│   │   ├── admin.py                    # Admin endpoints
│   │   ├── auth.py                     # Auth endpoints
│   │   ├── chat.py                     # Chat completions proxy
│   │   ├── health.py                   # Health check
│   │   ├── teams.py                    # Team management
│   │   └── ws.py                       # WebSocket
│   ├── security.py                     # Admin auth guard
│   ├── database.py                     # PostgreSQL client
│   ├── redis_client.py                 # Redis client
│   ├── config.py                       # Settings (Pydantic)
│   ├── main.py                         # FastAPI app
│   ├── proxy.py                        # Ollama proxy
│   ├── team_client.py                  # Team management
│   ├── ws_manager.py                   # WebSocket manager
│   ├── ws_token.py                     # Token sign/verify
│   ├── test_database.py                # Database tests
│   └── test_security.py                # Security tests
├── scripts/
│   └── init-db.sql                     # Database initialization
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Container image
└── README.md                           # This file
```

---

## Additional Resources

- [DATABASE.md](../DATABASE.md) - Detailed database design
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

*CostSentinel Backend - Durable Request History*
