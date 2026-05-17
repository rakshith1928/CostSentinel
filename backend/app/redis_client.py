##Redis data layer — it handles all storage + retrieval for usage, budgets, and history
import json
from datetime import datetime, timezone
import redis.asyncio as aioredis
from app.config import settings
from app import team_client as tc 

redis: aioredis.Redis = None

async def init_redis():
    global redis
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    tc.set_redis(redis) 

async def close_redis():
    await redis.aclose()

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

async def get_budget(user_id: str) -> int:
    raw = await redis.get(f"cost:budget:{user_id}")
    return int(raw) if raw else settings.default_budget_tokens

async def get_used(user_id: str) -> int:
    raw = await redis.get(f"cost:used:{user_id}:{_today()}")
    return int(raw) if raw else 0

async def increment_usage(user_id: str, tokens: int):
    key = f"cost:used:{user_id}:{_today()}"
    await redis.incrby(key, tokens)
    await redis.expire(key, 60 * 60 * 48)

async def log_request(user_id: str, entry: dict):
    await redis.lpush(f"cost:history:{user_id}", json.dumps(entry))
    await redis.ltrim(f"cost:history:{user_id}", 0, 499)

async def set_budget(user_id: str, tokens: int):
    await redis.set(f"cost:budget:{user_id}", tokens)

async def reset_usage(user_id: str):
    await redis.delete(f"cost:used:{user_id}:{_today()}")

async def list_users() -> list[dict]:
    keys = await redis.keys(f"cost:used:*:{_today()}")
    users = []
    for k in keys:
        uid = k.split(":")[2]
        used   = await get_used(uid)
        budget = await get_budget(uid)
        hard   = int(budget * settings.hard_limit_multiplier)
        users.append({
            "user_id": uid,
            "used_tokens": used,
            "budget_tokens": budget,
            "hard_limit_tokens": hard,
            "budget_pct": round(used / budget * 100, 1) if budget else 0,
            "status": "blocked" if used >= hard else "downgraded" if used >= budget else "ok",
        })
    return sorted(users, key=lambda u: -u["used_tokens"])

async def get_user_detail(user_id: str) -> dict:
    used   = await get_used(user_id)
    budget = await get_budget(user_id)
    hard   = int(budget * settings.hard_limit_multiplier)
    history_raw = await redis.lrange(f"cost:history:{user_id}", 0, 49)
    return {
        "user_id": user_id,
        "today": _today(),
        "used_tokens": used,
        "budget_tokens": budget,
        "hard_limit_tokens": hard,
        "budget_pct": round(used / budget * 100, 1) if budget else 0,
        "status": "blocked" if used >= hard else "downgraded" if used >= budget else "ok",
        "recent_requests": [json.loads(h) for h in history_raw],
    }
    