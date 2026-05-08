import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from app.config import settings
from app import redis_client as rc
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
    body        = await request.json()
    user_id     = proxy.resolve_user(request)
    orig_model  = body.get("model", "llama3.2")
    messages    = body.get("messages", [])

    input_tokens = proxy.count_tokens(
        " ".join(m.get("content", "") for m in messages)
    )
    budget     = await rc.get_budget(user_id)
    used       = await rc.get_used(user_id)
    hard_limit = int(budget * settings.hard_limit_multiplier)

    # Hard block
    if used >= hard_limit:
        await rc.log_request(user_id, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": orig_model, "original_model": orig_model,
            "input_tokens": input_tokens, "output_tokens": 0,
            "total_tokens": 0, "blocked": True, "downgraded": False,
        })
        background_tasks.add_task(manager.broadcast, {
            "type": "request_blocked",
            "user_id": user_id,
            "used_tokens": used,
            "budget_tokens": budget,
            "hard_limit_tokens": hard_limit,
        })
        return JSONResponse(status_code=429, content={"error": {
            "type": "budget_exceeded",
            "code": "hard_limit_reached",
            "used_tokens": used,
            "budget_tokens": budget,
            "hard_limit_tokens": hard_limit,
        }})

    model      = settings.downgrade_model if used >= budget else orig_model
    downgraded = model != orig_model

    start = time.monotonic()
    try:
        data = await proxy.call_ollama(model, messages, body.get("options"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")

    latency_ms     = int((time.monotonic() - start) * 1000)
    assistant_text = data.get("message", {}).get("content", "")
    output_tokens  = proxy.count_tokens(assistant_text)
    total_tokens   = input_tokens + output_tokens
    new_used       = used + total_tokens

    await rc.increment_usage(user_id, total_tokens)
    await rc.log_request(user_id, {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model, "original_model": orig_model,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "total_tokens": total_tokens, "blocked": False, "downgraded": downgraded,
    })

    background_tasks.add_task(manager.broadcast, {
        "type": "request_completed",
        "user_id": user_id,
        "model_used": model,
        "original_model": orig_model,
        "downgraded": downgraded,
        "blocked": False,
        "total_tokens": total_tokens,
        "tokens_used_today": new_used,
        "budget_tokens": budget,
        "hard_limit_tokens": hard_limit,
        "budget_pct": round(new_used / budget * 100, 1),
        "status": "downgraded" if downgraded else "ok",
        "latency_ms": latency_ms,
    })

    return {
        "id": f"cs-{proxy.make_request_id()}",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": assistant_text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens, "total_tokens": total_tokens},
        "sentinel": {
            "user_id": user_id, "original_model": orig_model, "model_used": model,
            "downgraded": downgraded, "blocked": False,
            "tokens_this_request": total_tokens,
            "tokens_used_today": new_used,
            "budget_tokens": budget, "hard_limit_tokens": hard_limit,
            "latency_ms": latency_ms,
            "budget_pct": round(new_used / budget * 100, 1),
        },
    }