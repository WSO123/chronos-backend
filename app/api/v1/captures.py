import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.captures import (
    CaptureCreate,
    CaptureCreateResponse,
    CaptureResponse,
    ExternalCaptureImportCreate,
    ExternalCaptureImportCreateResponse,
)
from app.services.capture_service import capture_service
from app.services.external_capture_import_service import external_capture_import_service

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


@router.post("/external-imports", response_model=ExternalCaptureImportCreateResponse)
def import_external_capture(
    payload: ExternalCaptureImportCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return external_capture_import_service.import_item(
        db,
        user_id=user_id,
        data_source_connection_id=payload.data_source_connection_id,
        external_item_id=payload.external_item_id,
        external_item_type=payload.external_item_type,
        title=payload.title,
        body=payload.body,
        occurred_at=payload.occurred_at,
        external_payload=payload.external_payload,
    )


@router.get("/{capture_id}", response_model=CaptureResponse)
def get_capture(
    capture_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return capture_service.get_capture(db, capture_id=capture_id, user_id=user_id)
