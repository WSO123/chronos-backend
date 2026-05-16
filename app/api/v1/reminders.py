from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.reminders import (
    ReminderBulkSeenRequest,
    ReminderBulkSeenResponse,
    ReminderCreate,
    ReminderListResponse,
    ReminderResponse,
    ReminderSummaryResponse,
)
from app.services.reminder_service import reminder_service

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=ReminderListResponse)
def list_reminders(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    result = reminder_service.list_reminders(
        db,
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "reminders": [reminder_service.to_response(reminder) for reminder in result["reminders"]],
        "scheduled_count": result["scheduled_count"],
        "overdue_count": result["overdue_count"],
    }


@router.get("/summary", response_model=ReminderSummaryResponse)
def get_reminder_summary(
    now: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    result = reminder_service.reminder_summary(db, user_id=user_id, now=now)
    next_reminder = result["next_reminder"]
    return {
        "pending_count": result["pending_count"],
        "unseen_count": result["unseen_count"],
        "due_count": result["due_count"],
        "execution_count": result["execution_count"],
        "deadline_count": result["deadline_count"],
        "next_reminder": reminder_service.to_response(next_reminder) if next_reminder else None,
    }


@router.post("", response_model=ReminderResponse, status_code=201)
def create_reminder(
    payload: ReminderCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    reminder = reminder_service.create_reminder(
        db,
        user_id=user_id,
        payload=payload.model_dump(),
    )
    return reminder_service.to_response(reminder)


@router.post("/seen", response_model=ReminderBulkSeenResponse)
def mark_reminders_seen(
    payload: ReminderBulkSeenRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    result = reminder_service.mark_reminders_seen(
        db,
        reminder_ids=payload.reminder_ids,
        user_id=user_id,
    )
    return {
        "updated_count": result["updated_count"],
        "already_seen_count": result["already_seen_count"],
        "reminders": [reminder_service.to_response(reminder) for reminder in result["reminders"]],
    }


@router.post("/{reminder_id}/seen", response_model=ReminderResponse)
def mark_reminder_seen(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    reminder = reminder_service.mark_reminder_seen(db, reminder_id=reminder_id, user_id=user_id)
    return reminder_service.to_response(reminder)


@router.post("/{reminder_id}/dismiss", response_model=ReminderResponse)
def dismiss_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    reminder = reminder_service.dismiss_reminder(db, reminder_id=reminder_id, user_id=user_id)
    return reminder_service.to_response(reminder)
