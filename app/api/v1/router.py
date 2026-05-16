from fastapi import APIRouter

from app.api.v1 import ai_jobs, captures, data_sources, focus_sessions, goals, inbox, insights, me, reports, tasks, today

api_router = APIRouter()
api_router.include_router(ai_jobs.router)
api_router.include_router(captures.router)
api_router.include_router(data_sources.router)
api_router.include_router(focus_sessions.router)
api_router.include_router(goals.router)
api_router.include_router(inbox.router)
api_router.include_router(insights.router)
api_router.include_router(me.router)
api_router.include_router(reports.router)
api_router.include_router(tasks.router)
api_router.include_router(today.router)
