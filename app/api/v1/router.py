from fastapi import APIRouter

from app.api.v1 import captures, focus_sessions, goals, inbox, tasks, today

api_router = APIRouter()
api_router.include_router(captures.router)
api_router.include_router(focus_sessions.router)
api_router.include_router(goals.router)
api_router.include_router(inbox.router)
api_router.include_router(tasks.router)
api_router.include_router(today.router)
