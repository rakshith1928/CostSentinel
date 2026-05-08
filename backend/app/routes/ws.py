from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws_manager import manager
from app import redis_client as rc

router = APIRouter()

@router.websocket("/ws/feed")
async def ws_feed(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send a snapshot immediately on connect
        # so the dashboard doesn't wait for the first event
        users = await rc.list_users()
        await websocket.send_json({
            "type": "snapshot",
            "users": users,
            "connected_clients": manager.count,
        })
        # Keep connection alive — just wait for disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)