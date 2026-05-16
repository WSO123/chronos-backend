import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.scheduler import ReminderSchedulerPlanResponse
from app.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/reminders", response_model=ReminderSchedulerPlanResponse)
def get_reminder_scheduler_plan(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # User dependency keeps the endpoint behind the same development auth boundary as other P3 APIs.
    _ = user_id
    return scheduler_service.reminder_schedule_plan()
