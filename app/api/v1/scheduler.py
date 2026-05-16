import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.scheduler import (
    DataSourceCeleryBeatScheduleResponse,
    DataSourceSchedulerPlanResponse,
    ReminderCeleryBeatScheduleResponse,
    ReminderSchedulerPlanResponse,
)
from app.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/data-sources", response_model=DataSourceSchedulerPlanResponse)
def get_data_source_scheduler_plan(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # User dependency keeps the endpoint behind the same development auth boundary as other P3 APIs.
    _ = user_id
    return scheduler_service.data_source_schedule_plan()


@router.get("/data-sources/celery-beat", response_model=DataSourceCeleryBeatScheduleResponse)
def get_data_source_celery_beat_schedule(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Read-only proposal. It does not mutate celery_app.conf or trigger workers.
    _ = user_id
    return scheduler_service.data_source_celery_beat_schedule()


@router.get("/reminders", response_model=ReminderSchedulerPlanResponse)
def get_reminder_scheduler_plan(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # User dependency keeps the endpoint behind the same development auth boundary as other P3 APIs.
    _ = user_id
    return scheduler_service.reminder_schedule_plan()


@router.get("/reminders/celery-beat", response_model=ReminderCeleryBeatScheduleResponse)
def get_reminder_celery_beat_schedule(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Read-only proposal. It does not mutate celery_app.conf or trigger workers.
    _ = user_id
    return scheduler_service.reminder_celery_beat_schedule()
