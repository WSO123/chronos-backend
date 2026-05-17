from datetime import date
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.today import (
    StrategyDetailResponse,
    TodayItemUpdate,
    TodayPlanningSignalsPrepareResponse,
    TodayReplanRequest,
    TodayResponse,
    TodayTaskResponse,
)
from app.services.planning_service import planning_service

router = APIRouter(prefix="/today", tags=["today"])


@router.get("", response_model=TodayResponse)
def get_today(
    plan_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return planning_service.get_today(db, user_id=user_id, plan_date=plan_date)


@router.get("/strategy", response_model=StrategyDetailResponse)
def get_strategy_detail(
    plan_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return planning_service.get_strategy_detail(db, user_id=user_id, plan_date=plan_date)


@router.post("/replan", response_model=TodayResponse)
def replan_today(
    payload: TodayReplanRequest | None = None,
    plan_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return planning_service.replan_today(
        db,
        user_id=user_id,
        plan_date=plan_date,
        reason=payload.reason if payload else None,
    )


@router.post("/planning-signals", response_model=TodayPlanningSignalsPrepareResponse)
def prepare_today_planning_signals(
    plan_date: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=20),
    replan: bool = Query(default=True),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return planning_service.prepare_today_planning_signals(
        db,
        user_id=user_id,
        plan_date=plan_date,
        limit=limit,
        replan=replan,
    )


@router.patch("/items/{item_id}", response_model=TodayTaskResponse)
def update_today_item(
    item_id: uuid.UUID,
    payload: TodayItemUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return planning_service.update_item_status(
        db,
        item_id=item_id,
        user_id=user_id,
        status=payload.status,
    )
