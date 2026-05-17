from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.ws_manager import manager
from app.ws_token import verify_token
from app import redis_client as rc
from app import team_client as tc
from app.config import settings

router = APIRouter()

@router.websocket("/ws/feed")
async def ws_feed(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    payload = verify_token(token) if token else None

    # Dev mode fallback — no secret configured
    if payload is None and settings.ws_token_secret == "change-me-in-production":
        payload = {"user_id": "dev", "role": "admin", "team": None}

    if payload is None:
        await websocket.close(code=4001)
        return

    user_id = payload['user_id']
    role    = payload['role']
    team    = payload.get('team')

    await manager.connect(websocket, user_id, role, team)

    try:
        if role == 'admin':
            # Admin snapshot — everything
            users = await rc.list_users()
            teams = await tc.list_teams()
            await websocket.send_json({
                "type":              "snapshot",
                "scope":             "global",
                "users":             users,
                "teams":             teams,
                "connected_clients": manager.count,
            })
        else:
            # Member snapshot — their team only
            team_detail  = await tc.get_team_status(team) if team else None
            team_members = await tc.get_team_members(team) if team else []

            # Fetch usage for every member of their team
            member_usage = []
            for uid in team_members:
                try:
                    detail = await rc.get_user_detail(uid)
                    member_usage.append(detail)
                except Exception:
                    pass

            await websocket.send_json({
                "type":        "snapshot",
                "scope":       "team",
                "team":        team,
                "team_detail": team_detail,
                "members":     member_usage,
            })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)