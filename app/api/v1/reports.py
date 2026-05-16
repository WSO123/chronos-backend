from datetime import date
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.reports import DailyReportResponse, MonthlyReportResponse, WeeklyReportResponse
from app.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly", response_model=WeeklyReportResponse)
def get_weekly_report(
    week_start: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return report_service.get_weekly_report(db, user_id=user_id, week_start=week_start)


@router.get("/monthly", response_model=MonthlyReportResponse)
def get_monthly_report(
    month: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return report_service.get_monthly_report(db, user_id=user_id, month=month)


@router.get("/daily", response_model=DailyReportResponse)
def get_daily_report(
    report_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return report_service.get_or_generate_daily_report(db, user_id=user_id, report_date=report_date)


@router.post("/daily/generate", response_model=DailyReportResponse)
def generate_daily_report(
    report_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return report_service.generate_daily_report(db, user_id=user_id, report_date=report_date)


@router.get("/daily/{report_date}", response_model=DailyReportResponse)
def get_daily_report_by_date(
    report_date: date,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return report_service.get_or_generate_daily_report(db, user_id=user_id, report_date=report_date)
