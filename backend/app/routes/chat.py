import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from app.config import settings
from app import redis_client as rc
from app import team_client as tc
from app import proxy
from app.ws_manager import manager

router = APIRouter()

def _check_key(x_api_key: Optional[str]):
    if settings.sentinel_api_key and x_api_key != settings.sentinel_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(default=None),
):
    _check_key(x_api_key)
    body       = await request.json()
    user_id    = proxy.resolve_user(request)
    orig_model = body.get("model", "llama3.2")
    messages   = body.get("messages", [])

    # Generate deterministic request ID for idempotent retries
    request_id = proxy.make_request_id(user_id, orig_model, messages)

    input_tokens = proxy.count_tokens(
        " ".join(m.get("content", "") for m in messages)
    )

    # ── User budget ──────────────────────────────────────────────────────────
    user_budget = await rc.get_budget(user_id)
    user_used   = await rc.get_used(user_id)
    user_hard   = int(user_budget * settings.hard_limit_multiplier)

    # ── Team budget (optional) ───────────────────────────────────────────────
    team        = await tc.get_user_team(user_id)
    team_budget = team_used = team_hard = None
    if team:
        team_budget = await tc.get_team_budget(team)
        team_used   = await tc.get_team_used(team)
        team_hard   = int(team_budget * settings.hard_limit_multiplier)

    # ── Hard block — user ────────────────────────────────────────────────────
    if user_used >= user_hard:
        await rc.log_request(user_id, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": orig_model, "original_model": orig_model,
            "input_tokens": input_tokens, "output_tokens": 0,
            "total_tokens": 0, "blocked": True, "downgraded": False,
            "block_reason": "user_budget_exceeded",
        })
        background_tasks.add_task(manager.broadcast, {
            "type": "request_blocked",
            "user_id": user_id,
            "block_reason": "user_budget_exceeded",
        })
        return JSONResponse(status_code=429, content={"error": {
            "type": "budget_exceeded",
            "code": "user_budget_exceeded",
            "user_id": user_id,
            "used_tokens": user_used,
            "budget_tokens": user_budget,
        }})

    # ── Hard block — team ────────────────────────────────────────────────────
    if team and team_used >= team_hard:
        await rc.log_request(user_id, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": orig_model, "original_model": orig_model,
            "input_tokens": input_tokens, "output_tokens": 0,
            "total_tokens": 0, "blocked": True, "downgraded": False,
            "block_reason": "team_budget_exceeded",
            "team": team,
        })
        background_tasks.add_task(manager.broadcast, {
            "type": "request_blocked",
            "user_id": user_id,
            "team": team,
            "block_reason": "team_budget_exceeded",
        })
        return JSONResponse(status_code=429, content={"error": {
            "type": "budget_exceeded",
            "code": "team_budget_exceeded",
            "user_id": user_id,
            "team": team,
            "team_used_tokens": team_used,
            "team_budget_tokens": team_budget,
        }})

    # ── Soft downgrade — either limit triggers it ────────────────────────────
    user_over_soft = user_used >= user_budget
    team_over_soft = team and team_used >= team_budget
    downgraded = user_over_soft or team_over_soft
    model      = settings.downgrade_model if downgraded else orig_model

    start = time.monotonic()
    try:
        data = await proxy.call_ollama(model, messages, body.get("options"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")

    latency_ms     = int((time.monotonic() - start) * 1000)
    assistant_text = data.get("message", {}).get("content", "")
    output_tokens  = proxy.count_tokens(assistant_text)
    total_tokens   = input_tokens + output_tokens
    new_user_used  = user_used + total_tokens

    # ── Increment both buckets ───────────────────────────────────────────────
    await rc.increment_usage(user_id, total_tokens)
    if team:
        await tc.increment_team_usage(team, total_tokens)

    await rc.log_request(user_id, {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model, "original_model": orig_model,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "total_tokens": total_tokens, "blocked": False,
        "downgraded": downgraded,
        "team": team,
        "downgrade_reason": (
            "team_soft_limit"  if team_over_soft  else
            "user_soft_limit"  if user_over_soft  else None
        ),
    })

    background_tasks.add_task(manager.broadcast, {
        "type": "request_completed",
        "user_id": user_id,
        "team": team,
        "model_used": model,
        "original_model": orig_model,
        "downgraded": downgraded,
        "total_tokens": total_tokens,
        "tokens_used_today": new_user_used,
        "budget_pct": round(new_user_used / user_budget * 100, 1),
        "status": "downgraded" if downgraded else "ok",
    })

    return {
        "id": f"cs-{request_id}",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": assistant_text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens, "total_tokens": total_tokens},
        "sentinel": {
            "user_id": user_id,
            "team": team,
            "original_model": orig_model,
            "model_used": model,
            "downgraded": downgraded,
            "downgrade_reason": (
                "team_soft_limit" if team_over_soft else
                "user_soft_limit" if user_over_soft else None
            ),
            "blocked": False,
            "tokens_this_request": total_tokens,
            "request_id": request_id,
            "user": {
                "used_tokens": new_user_used,
                "budget_tokens": user_budget,
                "budget_pct": round(new_user_used / user_budget * 100, 1),
            },
            "team_pool": {
                "team": team,
                "used_tokens": (team_used or 0) + total_tokens,
                "budget_tokens": team_budget,
                "budget_pct": round(((team_used or 0) + total_tokens) / team_budget * 100, 1),
            } if team else None,
            "latency_ms": latency_ms,
        },
    }