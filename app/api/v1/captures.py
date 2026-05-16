import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.captures import CaptureCreate, CaptureCreateResponse, CaptureResponse
from app.services.capture_service import capture_service

router = APIRouter(prefix="/captures", tags=["captures"])


@router.post("", response_model=CaptureCreateResponse, status_code=status.HTTP_201_CREATED)
def create_capture(
    payload: CaptureCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    capture, parse_result, inbox_item = capture_service.create_text_capture(
        db,
        user_id=user_id,
        raw_text=payload.raw_text,
    )
    return {
        "capture": capture,
        "parse_result": parse_result,
        "inbox_item": inbox_item,
    }


@router.get("/{capture_id}", response_model=CaptureResponse)
def get_capture(
    capture_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return capture_service.get_capture(db, capture_id=capture_id, user_id=user_id)
