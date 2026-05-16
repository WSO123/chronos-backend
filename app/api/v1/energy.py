from datetime import date
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.energy import EnergyDailyMetricResponse, EnergyDailyMetricUpsert, EnergyDashboardResponse
from app.services.energy_service import energy_service

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/dashboard", response_model=EnergyDashboardResponse)
def get_energy_dashboard(
    end_date: date | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=31),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return energy_service.get_dashboard(db, user_id=user_id, end_date=end_date, days=days)


@router.put("/daily-metrics", response_model=EnergyDailyMetricResponse)
def upsert_energy_daily_metric(
    payload: EnergyDailyMetricUpsert,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    metric = energy_service.upsert_daily_metric(
        db,
        user_id=user_id,
        payload=payload.model_dump(),
    )
    return energy_service.to_response(metric)
