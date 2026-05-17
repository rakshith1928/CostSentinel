import asyncio
import json
from datetime import datetime, timezone
import redis.asyncio as aioredis
from app.config import settings
from app import team_client as tc

_redis: aioredis.Redis | None = None


# ── Connection guard ──────────────────────────────────────────────────────────

def redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis

async def init_redis():
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    tc.set_redis(_redis)

async def close_redis():
    await redis().aclose()          # was: redis.aclose() — calling module not guard


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Budget ops ────────────────────────────────────────────────────────────────

async def get_budget(user_id: str) -> int:
    raw = await redis().get(f"cost:budget:{user_id}")
    return int(raw) if raw else settings.default_budget_tokens

async def set_budget(user_id: str, tokens: int):
    if tokens <= 0:
        raise ValueError("Budget must be positive")
    await redis().set(f"cost:budget:{user_id}", tokens)

async def get_used(user_id: str) -> int:
    raw = await redis().get(f"cost:used:{user_id}:{_today()}")
    return int(raw) if raw else 0

async def increment_usage(user_id: str, tokens: int):
    key = f"cost:used:{user_id}:{_today()}"
    async with redis().pipeline(transaction=True) as pipe:
        pipe.incrby(key, tokens)
        pipe.expire(key, 60 * 60 * 48)
        await pipe.execute()

async def reset_usage(user_id: str):
    await redis().delete(f"cost:used:{user_id}:{_today()}")


# ── History ───────────────────────────────────────────────────────────────────

async def log_request(user_id: str, entry: dict):
    key = f"cost:history:{user_id}"
    async with redis().pipeline(transaction=True) as pipe:
        pipe.lpush(key, json.dumps(entry))
        pipe.ltrim(key, 0, 499)
        await pipe.execute()


# ── User listing — SCAN instead of KEYS ──────────────────────────────────────

async def list_users() -> list[dict]:
    user_ids = []
    async for key in redis().scan_iter(f"cost:used:*:{_today()}"):
        user_ids.append(key.split(":")[2])

    if not user_ids:
        return []

    # Fetch all users in parallel
    async def _build(uid: str) -> dict:
        used, budget = await asyncio.gather(get_used(uid), get_budget(uid))
        hard = int(budget * settings.hard_limit_multiplier)
        return {
            "user_id": uid,
            "used_tokens": used,
            "budget_tokens": budget,
            "hard_limit_tokens": hard,
            "budget_pct": round(used / budget * 100, 1) if budget else 0,
            "status": (
                "blocked"    if used >= hard   else
                "downgraded" if used >= budget else
                "ok"
            ),
        }

    users = await asyncio.gather(*[_build(uid) for uid in user_ids])
    return sorted(users, key=lambda u: -u["used_tokens"])


# ── User detail ───────────────────────────────────────────────────────────────

async def get_user_detail(user_id: str) -> dict:
    used, budget, history_raw = await asyncio.gather(
        get_used(user_id),
        get_budget(user_id),
        redis().lrange(f"cost:history:{user_id}", 0, 49),
    )
    hard = int(budget * settings.hard_limit_multiplier)
    return {
        "user_id": user_id,
        "today": _today(),
        "used_tokens": used,
        "budget_tokens": budget,
        "hard_limit_tokens": hard,
        "budget_pct": round(used / budget * 100, 1) if budget else 0,
        "status": (
            "blocked"    if used >= hard   else
            "downgraded" if used >= budget else
            "ok"
        ),
        "recent_requests": [json.loads(h) for h in history_raw],
    }