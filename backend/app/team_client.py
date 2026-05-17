import json
from datetime import datetime, timezone
import redis.asyncio as aioredis
from app.config import settings

# Shares the same Redis connection as redis_client
# We import the redis instance lazily to avoid circular imports
_redis = None

def set_redis(r):
    global _redis
    _redis = r

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ── Team membership ───────────────────────────────────────────────────────────

async def get_user_team(user_id: str) -> str | None:
    """Returns team name for a user, or None if not in any team."""
    return await _redis.get(f"team:member:{user_id}")

async def set_user_team(user_id: str, team: str):
    await _redis.set(f"team:member:{user_id}", team)

async def remove_user_team(user_id: str):
    await _redis.delete(f"team:member:{user_id}")

async def get_team_members(team: str) -> list[str]:
    raw = await _redis.get(f"team:members:{team}")
    return json.loads(raw) if raw else []

async def add_team_member(team: str, user_id: str):
    members = await get_team_members(team)
    if user_id not in members:
        members.append(user_id)
    await _redis.set(f"team:members:{team}", json.dumps(members))
    await set_user_team(user_id, team)

async def remove_team_member(team: str, user_id: str):
    members = await get_team_members(team)
    members = [m for m in members if m != user_id]
    await _redis.set(f"team:members:{team}", json.dumps(members))
    await remove_user_team(user_id)

# ── Team budgets ──────────────────────────────────────────────────────────────

async def get_team_budget(team: str) -> int:
    raw = await _redis.get(f"team:budget:{team}")
    return int(raw) if raw else settings.default_team_budget_tokens

async def set_team_budget(team: str, tokens: int):
    await _redis.set(f"team:budget:{team}", tokens)

async def get_team_used(team: str) -> int:
    raw = await _redis.get(f"team:used:{team}:{_today()}")
    return int(raw) if raw else 0

async def increment_team_usage(team: str, tokens: int):
    key = f"team:used:{team}:{_today()}"
    await _redis.incrby(key, tokens)
    await _redis.expire(key, 60 * 60 * 48)

async def reset_team_usage(team: str):
    await _redis.delete(f"team:used:{team}:{_today()}")

# ── Team status ───────────────────────────────────────────────────────────────

async def get_team_status(team: str) -> dict:
    used   = await get_team_used(team)
    budget = await get_team_budget(team)
    hard   = int(budget * settings.hard_limit_multiplier)
    members = await get_team_members(team)
    return {
        "team": team,
        "members": members,
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

async def list_teams() -> list[dict]:
    keys = await _redis.keys("team:budget:*")
    teams = []
    for k in keys:
        team = k.split(":")[-1]
        teams.append(await get_team_status(team))
    return sorted(teams, key=lambda t: -t["used_tokens"])