# CostSentinel

**Version:** 0.2.0

CostSentinel is a real-time token budget management and LLM proxy system that provides cost control, usage tracking, and team-based budget allocation for AI applications.

## Features

- 🛡️ **Token Budget Management** - Set individual and team token budgets with automatic enforcement
- 🔄 **Model Downgrading** - Automatically downgrade to cheaper models when budgets are exceeded
- 📊 **Real-time Analytics** - Track usage, costs, and blocked requests in real-time
- 👥 **Team Support** - Manage budgets across multiple teams with hierarchical controls
- 🔐 **Authentication** - Secure API access with WebSocket-based token management
- 📈 **Request History** - Durable storage with PostgreSQL + TimescaleDB for analytics
- ⚡ **High Performance** - Redis-backed counters for low-latency budget checks

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Dashboard  │────▶│  FastAPI     │────▶│  Ollama         │
│  (React)    │     │  Backend     │     │  (LLM Server)   │
└─────────────┘     └──────────────┘     └─────────────────┘
                          │
                    ┌─────┴─────┐
                    ▼           ▼
            ┌───────────┐ ┌─────────────┐
            │  Redis    │ │ PostgreSQL  │
            │  (Cache)  │ │ + Timescale │
            └───────────┘ └─────────────┘
```

### Storage Layers

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Hot State** | Redis | Budget counters, rate limits, real-time state |
| **Durable History** | PostgreSQL + TimescaleDB | Request audit trail, analytics |
| **Cache** | Redis | Session data, temporary aggregations |

## Project Structure

```
costsentinel/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── routes/         # API endpoints
│   │   │   ├── chat.py     # Chat/completion proxy
│   │   │   ├── admin.py    # Admin operations
│   │   │   ├── auth.py     # Authentication
│   │   │   ├── teams.py    # Team management
│   │   │   ├── ws.py       # WebSocket handlers
│   │   │   └── health.py   # Health checks
│   │   ├── models/         # Data models
│   │   │   └── request_history_sqla.py
│   │   ├── config.py       # Configuration
│   │   ├── database.py     # DB connection
│   │   ├── redis_client.py # Redis client
│   │   ├── proxy.py        # LLM proxy logic
│   │   └── ws_manager.py   # WebSocket manager
│   ├── scripts/
│   │   └── init-db.sql     # Database initialization
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/              # React frontend
│   ├── src/
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env.example            # Environment template
├── docker-compose.yml      # Docker orchestration
└── DATABASE-SETUP.md       # Database documentation
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ with TimescaleDB
- Redis 6+
- Ollama (for LLM serving)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd costsentinel
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# See Environment Variables section below
```

### 3. Start Services

#### Option A: Docker Compose (Recommended)

```bash
docker-compose up -d
```

#### Option B: Manual Setup

**Start PostgreSQL + TimescaleDB:**
```bash
# Use TimescaleDB Docker image
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg14
```

**Start Redis:**
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

**Start Ollama:**
```bash
docker run -d --name ollama -p 11434:11434 ollama/ollama
```

### 4. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
psql $DATABASE_URL -f scripts/init-db.sql

# Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Setup Dashboard

```bash
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

The dashboard will be available at `http://localhost:3000`

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Database Configuration (Required)

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname?sslmode=require
DATABASE_ECHO=false
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

### Redis Configuration (Required)

```env
REDIS_URL=redis://redis:6379
```

### Ollama Configuration (Required)

```env
OLLAMA_URL=http://ollama:11434
```

### API & Authentication (Required)

```env
SENTINEL_API_KEY=your-sentinel-api-key-here
WS_TOKEN_SECRET=generate-a-random-secret-here
ADMIN_USERS=admin
CORS_ORIGINS=http://localhost:3000
```

### Budget Defaults (Optional)

```env
DEFAULT_BUDGET_TOKENS=100000
DEFAULT_TEAM_BUDGET_TOKENS=500000
HARD_LIMIT_MULTIPLIER=1.2
DOWNGRADE_MODEL=tinyllama
```

### History Retention (Optional)

```env
HISTORY_TTL_DAYS=90
```

### Dashboard (Optional)

```env
VITE_USER_ID=admin
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Authenticate user |
| POST | `/api/auth/logout` | Logout user |

### Chat/Completion

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/completions` | Proxy chat completions through Ollama |

### Teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/teams` | List all teams |
| GET | `/api/teams/{team_id}` | Get team details |
| POST | `/api/teams` | Create new team |
| PUT | `/api/teams/{team_id}` | Update team |
| DELETE | `/api/teams/{team_id}` | Delete team |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/users` | List all users |
| GET | `/api/admin/budgets` | View all budgets |
| PUT | `/api/admin/budgets/{user_id}` | Update user budget |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws` | Real-time updates for budget and usage |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check endpoint |

## Usage Examples

### Send a Chat Completion

```bash
curl -X POST http://localhost:8000/api/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "llama2",
    "messages": [{"role": "user", "content": "Hello!"}],
    "user_id": "admin"
  }'
```

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=YOUR_TOKEN');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Budget update:', data);
};
```

## Development

### Running Tests

```bash
cd backend
python -m pytest app/test_database.py -v
python -m pytest app/models/test_request_history.py -v
```

### Backend Development

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd dashboard
npm run dev
```

### Building for Production

```bash
# Build frontend
cd dashboard
npm run build

# Backend is ready for production with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Database Schema

The main table `request_history` stores all LLM requests:

```sql
CREATE TABLE request_history (
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
```

TimescaleDB hypertable with 90-day automatic retention is configured on startup.

See [DATABASE-SETUP.md](DATABASE-SETUP.md) for detailed database documentation.

## Troubleshooting

### Connection Issues

```bash
# Check if services are running
docker ps

# Check backend logs
docker logs costsentinel-backend

# Test database connection
psql $DATABASE_URL -c "SELECT 1"
```

### Redis Connection

```bash
# Test Redis connectivity
redis-cli ping
# Should return: PONG
```

### Database Errors

See [DATABASE-SETUP.md](DATABASE-SETUP.md) troubleshooting section.

## License

[Specify your license here]

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Ollama Documentation](https://ollama.ai/)

---

*CostSentinel - Monitor and control your LLM costs effectively.*