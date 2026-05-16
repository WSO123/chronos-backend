from fastapi import APIRouter

from app.api.v1 import goals, tasks

api_router = APIRouter()
api_router.include_router(goals.router)
api_router.include_router(tasks.router)
