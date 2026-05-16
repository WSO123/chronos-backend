from datetime import date
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.me import MeOverviewResponse
from app.services.me_service import me_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/overview", response_model=MeOverviewResponse)
def get_me_overview(
    today: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return me_service.get_overview(db, user_id=user_id, today=today)
