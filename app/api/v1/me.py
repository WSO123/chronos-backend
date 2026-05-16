from datetime import date
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.me import MeOverviewResponse
from app.schemas.settings import UserSettingsResponse, UserSettingsUpdate
from app.services.me_service import me_service
from app.services.settings_service import settings_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/overview", response_model=MeOverviewResponse)
def get_me_overview(
    today: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return me_service.get_overview(db, user_id=user_id, today=today)


@router.get("/settings", response_model=UserSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    settings = settings_service.get_settings(db, user_id=user_id)
    return settings_service.to_response(settings)


@router.patch("/settings", response_model=UserSettingsResponse)
def update_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    settings = settings_service.update_settings(
        db,
        user_id=user_id,
        payload=payload.model_dump(exclude_unset=True),
    )
    return settings_service.to_response(settings)
