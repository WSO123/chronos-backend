import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.db import get_db
from app.schemas.tasks import (
    ActivityEventResponse,
    TaskCreate,
    TaskBreakdownResponse,
    TaskDependenciesResponse,
    TaskDependencyCreate,
    TaskDependencyEdgeResponse,
    TaskDetailResponse,
    TaskResponse,
    TaskStepCreate,
    TaskStepResponse,
    TaskUpdate,
)
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.create_task(
        db,
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        goal_id=payload.goal_id,
        estimated_duration_min=payload.estimated_duration_min,
        priority=payload.priority,
        value_level=payload.value_level,
        deadline=payload.deadline,
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.get_task_detail(db, task_id=task_id, user_id=user_id)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.update_task(
        db,
        task_id=task_id,
        user_id=user_id,
        updates=payload.model_dump(exclude_unset=True),
    )


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.complete_task(db, task_id=task_id, user_id=user_id)


@router.post("/{task_id}/postpone", response_model=TaskResponse)
def postpone_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.postpone_task(db, task_id=task_id, user_id=user_id)


@router.post("/{task_id}/breakdown", response_model=TaskBreakdownResponse)
def breakdown_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.breakdown_task(db, task_id=task_id, user_id=user_id)


@router.get("/{task_id}/dependencies", response_model=TaskDependenciesResponse)
def get_task_dependencies(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.get_task_dependencies(db, task_id=task_id, user_id=user_id)


@router.post("/{task_id}/dependencies", response_model=TaskDependencyEdgeResponse, status_code=status.HTTP_201_CREATED)
def add_task_dependency(
    task_id: uuid.UUID,
    payload: TaskDependencyCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.add_task_dependency(
        db,
        task_id=task_id,
        user_id=user_id,
        prerequisite_task_id=payload.prerequisite_task_id,
        reason=payload.reason,
    )


@router.delete("/{task_id}/dependencies/{prerequisite_task_id}", response_model=TaskDependenciesResponse)
def delete_task_dependency(
    task_id: uuid.UUID,
    prerequisite_task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.delete_task_dependency(
        db,
        task_id=task_id,
        user_id=user_id,
        prerequisite_task_id=prerequisite_task_id,
    )


@router.post("/{task_id}/steps", response_model=TaskStepResponse, status_code=status.HTTP_201_CREATED)
def create_task_step(
    task_id: uuid.UUID,
    payload: TaskStepCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.create_step(
        db,
        task_id=task_id,
        user_id=user_id,
        title=payload.title,
        sort_order=payload.sort_order,
    )


@router.post("/{task_id}/steps/{step_id}/complete", response_model=TaskStepResponse)
def complete_task_step(
    task_id: uuid.UUID,
    step_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.complete_step(
        db,
        task_id=task_id,
        step_id=step_id,
        user_id=user_id,
    )


@router.get("/{task_id}/events", response_model=list[ActivityEventResponse])
def list_task_events(
    task_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return task_service.list_task_events(
        db,
        task_id=task_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
