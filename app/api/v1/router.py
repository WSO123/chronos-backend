from fastapi import APIRouter

from app.api.v1 import captures, goals, inbox, tasks

api_router = APIRouter()
api_router.include_router(captures.router)
api_router.include_router(goals.router)
api_router.include_router(inbox.router)
api_router.include_router(tasks.router)
