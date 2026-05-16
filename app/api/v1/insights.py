from datetime import date
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.insights import InsightDetailResponse
from app.services.insight_service import insight_service

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/detail", response_model=InsightDetailResponse)
def get_insight_detail(
    anchor_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return insight_service.get_detail(db, user_id=user_id, anchor_date=anchor_date)
