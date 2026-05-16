import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.goals import GoalCreate, GoalResponse, GoalUpdate
from app.services.goal_service import goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return goal_service.create_goal(
        db,
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        deadline=payload.deadline,
        value_level=payload.value_level,
    )


@router.get("", response_model=list[GoalResponse])
def list_goals(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return goal_service.list_goals(db, user_id=user_id, limit=limit, offset=offset)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return goal_service.get_goal(db, goal_id=goal_id, user_id=user_id)


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return goal_service.update_goal(
        db,
        goal_id=goal_id,
        user_id=user_id,
        updates=payload.model_dump(exclude_unset=True),
    )
