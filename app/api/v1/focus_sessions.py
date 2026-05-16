import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.focus_sessions import FocusSessionCreate, FocusSessionFinishRequest, FocusSessionResponse
from app.services.focus_service import focus_service

router = APIRouter(prefix="/focus-sessions", tags=["focus-sessions"])


@router.post("", response_model=FocusSessionResponse, status_code=status.HTTP_201_CREATED)
def start_focus_session(
    payload: FocusSessionCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return focus_service.start_session(
        db,
        user_id=user_id,
        task_id=payload.task_id,
        daily_plan_item_id=payload.daily_plan_item_id,
        planned_duration_min=payload.planned_duration_min,
    )


@router.get("/{session_id}", response_model=FocusSessionResponse)
def get_focus_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return focus_service.get_session(db, session_id=session_id, user_id=user_id)


@router.post("/{session_id}/complete", response_model=FocusSessionResponse)
def complete_focus_session(
    session_id: uuid.UUID,
    payload: FocusSessionFinishRequest | None = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return focus_service.complete_session(
        db,
        session_id=session_id,
        user_id=user_id,
        actual_duration_min=payload.actual_duration_min if payload else None,
    )


@router.post("/{session_id}/interrupt", response_model=FocusSessionResponse)
def interrupt_focus_session(
    session_id: uuid.UUID,
    payload: FocusSessionFinishRequest | None = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return focus_service.interrupt_session(
        db,
        session_id=session_id,
        user_id=user_id,
        actual_duration_min=payload.actual_duration_min if payload else None,
        interruption_reason=payload.interruption_reason if payload else None,
    )


@router.post("/{session_id}/postpone", response_model=FocusSessionResponse)
def postpone_focus_session(
    session_id: uuid.UUID,
    payload: FocusSessionFinishRequest | None = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return focus_service.postpone_session(
        db,
        session_id=session_id,
        user_id=user_id,
        actual_duration_min=payload.actual_duration_min if payload else None,
        interruption_reason=payload.interruption_reason if payload else None,
    )
