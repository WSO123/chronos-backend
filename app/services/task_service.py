from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.activity_event import ActivityEvent
from app.models.enums import EntityType, TaskSource, TaskStatus, ValueLevel
from app.models.goal import Goal
from app.models.task import Task
from app.models.task_step import TaskStep
from app.models.mixins import utc_now
from app.services.activity_event_service import activity_event_service
from app.services.errors import InvalidStateError, NotFoundError, ValidationDomainError


class TaskService:
    def create_task(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        title: str,
        description: str | None = None,
        goal_id: uuid.UUID | None = None,
        estimated_duration_min: int | None = None,
        priority: int = 3,
        value_level: ValueLevel = ValueLevel.MEDIUM,
        deadline: date | None = None,
        source: TaskSource = TaskSource.MANUAL,
    ) -> Task:
        if goal_id is not None:
            self._validate_user_goal(db, goal_id=goal_id, user_id=user_id)

        task = Task(
            user_id=user_id,
            goal_id=goal_id,
            title=title,
            description=description,
            estimated_duration_min=estimated_duration_min,
            priority=priority,
            value_level=value_level,
            deadline=deadline,
            source=source,
            status=TaskStatus.ACTIVE,
            progress=Decimal("0.00"),
        )
        db.add(task)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_CREATED",
            related_task_id=task.id,
            payload={"title": title, "source": source.value},
        )
        db.commit()
        db.refresh(task)
        return self.get_task(db, task_id=task.id, user_id=user_id)

    def get_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        stmt = (
            select(Task)
            .options(selectinload(Task.steps))
            .where(Task.id == task_id, Task.user_id == user_id)
        )
        task = db.scalars(stmt).first()
        if task is None:
            raise NotFoundError("Task not found")
        return task

    def update_task(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        updates: dict,
    ) -> Task:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)

        if "goal_id" in updates and updates["goal_id"] is not None:
            self._validate_user_goal(db, goal_id=updates["goal_id"], user_id=user_id)

        changed_fields: list[str] = []
        for field in (
            "title",
            "description",
            "goal_id",
            "estimated_duration_min",
            "priority",
            "value_level",
            "deadline",
        ):
            if field in updates:
                setattr(task, field, updates[field])
                changed_fields.append(field)

        if changed_fields:
            activity_event_service.add_event(
                db,
                user_id=user_id,
                entity_type=EntityType.TASK,
                entity_id=task.id,
                event_type="TASK_UPDATED",
                related_task_id=task.id,
                payload={"changed_fields": changed_fields},
            )

        db.commit()
        db.refresh(task)
        return self.get_task(db, task_id=task.id, user_id=user_id)

    def complete_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
            action="completed",
        )

        task.status = TaskStatus.COMPLETED
        task.progress = Decimal("1.00")
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_COMPLETED",
            related_task_id=task.id,
        )
        db.commit()
        db.refresh(task)
        return self.get_task(db, task_id=task.id, user_id=user_id)

    def postpone_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
            action="postponed",
        )

        task.status = TaskStatus.POSTPONED
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_POSTPONED",
            related_task_id=task.id,
        )
        db.commit()
        db.refresh(task)
        return self.get_task(db, task_id=task.id, user_id=user_id)

    def create_step(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        sort_order: int = 0,
    ) -> TaskStep:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED},
            action="updated with a new step",
        )
        step = TaskStep(task_id=task.id, title=title, sort_order=sort_order)
        db.add(step)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_STEP_CREATED",
            related_task_id=task.id,
            payload={"step_id": str(step.id), "title": title},
        )
        db.commit()
        db.refresh(step)
        return step

    def complete_step(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        step_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TaskStep:
        step = db.get(TaskStep, step_id)
        if step is None:
            raise NotFoundError("Task step not found")

        task = self._get_user_task(db, task_id=step.task_id, user_id=user_id)
        if task.id != task_id:
            raise NotFoundError("Task step not found")
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
            action="updated by completing a step",
        )
        if step.is_completed:
            raise InvalidStateError("Task step is already completed")

        step.is_completed = True
        step.completed_at = utc_now()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_STEP_COMPLETED",
            related_task_id=task.id,
            payload={"step_id": str(step.id)},
        )
        db.commit()
        db.refresh(step)
        return step

    def list_task_events(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActivityEvent]:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        stmt = (
            select(ActivityEvent)
            .where(
                ActivityEvent.user_id == user_id,
                ActivityEvent.related_task_id == task.id,
            )
            .order_by(ActivityEvent.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(stmt).all())

    def _get_user_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = db.get(Task, task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("Task not found")
        return task

    def _validate_user_goal(self, db: Session, *, goal_id: uuid.UUID, user_id: uuid.UUID) -> None:
        goal = db.get(Goal, goal_id)
        if goal is None or goal.user_id != user_id:
            raise ValidationDomainError("Goal not found")

    def _ensure_task_status(self, task: Task, *, allowed: set[TaskStatus], action: str) -> None:
        if task.status not in allowed:
            raise InvalidStateError(f"{task.status.value} task cannot be {action}")


task_service = TaskService()
