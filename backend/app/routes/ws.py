from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.ws_manager import manager
from app.ws_token import verify_token
from app import redis_client as rc
from app.config import settings

router = APIRouter()

@router.websocket("/ws/feed")
async def ws_feed(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    # Validate token
    payload = verify_token(token) if token else None

    # If no token and auth is disabled (dev mode) — allow as admin
    if payload is None and not settings.ws_token_secret != "change-me-in-production":
        payload = {"user_id": "dev", "role": "admin", "team": None}

    # If token auth is active and token is invalid — reject
    if payload is None:
        await websocket.close(code=4001)
        return

    user_id = payload['user_id']
    role    = payload['role']
    team    = payload.get('team')

    await manager.connect(websocket, user_id, role, team)

    try:
        # Send scoped snapshot on connect
        if role == 'admin':
            users = await rc.list_users()
            await websocket.send_json({
                "type":             "snapshot",
                "users":            users,
                "connected_clients": manager.count,
            })
        else:
            # Members only get their own usage on connect
            detail = await rc.get_user_detail(user_id)
            await websocket.send_json({
                "type":    "snapshot",
                "user_id": user_id,
                "detail":  detail,
                "connected_clients": manager.count,
            })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)