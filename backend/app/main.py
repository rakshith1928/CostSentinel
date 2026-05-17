from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app import redis_client as rc
from app.routes import chat, admin, health, ws, teams

app = FastAPI(title="CostSentinel", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(health.router)
app.include_router(ws.router) 
app.include_router(teams.router)

@app.on_event("startup")
async def startup():
    await rc.init_redis()

@app.on_event("shutdown")
async def shutdown():
    await rc.close_redis()