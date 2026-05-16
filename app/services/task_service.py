from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.activity_event import ActivityEvent
from app.models.ai_job import AIJob
from app.models.daily_plan import DailyPlan, DailyPlanItem
from app.models.enums import (
    AIJobStatus,
    AIJobType,
    DailyPlanStatus,
    EntityType,
    FocusSessionStatus,
    TaskSource,
    TaskStatus,
    ValueLevel,
)
from app.models.focus_session import FocusSession
from app.models.goal import Goal
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.task_step import TaskStep
from app.models.user import User
from app.models.mixins import utc_now
from app.services.activity_event_service import activity_event_service
from app.services.ai_job_service import ai_job_service
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
        commit: bool = True,
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
        if commit:
            db.commit()
            db.refresh(task)
            return self.get_task(db, task_id=task.id, user_id=user_id)
        return task

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

    def get_task_detail(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        task = self.get_task(db, task_id=task_id, user_id=user_id)
        active_focus = self._active_focus_session(db, user_id=user_id)
        today_item = self._today_plan_item(db, task=task)
        steps = sorted(task.steps, key=lambda step: (step.sort_order, step.created_at))
        return {
            "id": task.id,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "user_id": task.user_id,
            "goal_id": task.goal_id,
            "title": task.title,
            "description": task.description,
            "estimated_duration_min": task.estimated_duration_min,
            "actual_duration_min": task.actual_duration_min,
            "priority": task.priority,
            "value_level": task.value_level,
            "deadline": task.deadline,
            "progress": task.progress,
            "status": task.status,
            "source": task.source,
            "steps": steps,
            "goal": self._goal_summary(db, task=task),
            "ai_info": {
                "recommended_duration_min": task.estimated_duration_min or 25,
                "priority": task.priority,
                "value_level": task.value_level,
                "execution_suggestion": self._execution_suggestion(task),
            },
            "progress_info": {
                "progress": task.progress,
                "status": task.status,
                "actual_duration_min": task.actual_duration_min,
            },
            "today_context": self._today_context(today_item),
            "dependency_info": self.get_task_dependencies(db, task_id=task.id, user_id=user_id),
            "focus_state": {
                "active_focus_session_id": active_focus.id if active_focus else None,
                "is_currently_focusing_this_task": active_focus is not None and active_focus.task_id == task.id,
            },
            "actions": {
                "can_start_focus": task.status in {TaskStatus.ACTIVE, TaskStatus.POSTPONED} and active_focus is None,
                "can_complete": task.status in {TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
                "can_postpone": task.status in {TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
                "can_edit": task.status != TaskStatus.ARCHIVED,
            },
        }

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

    def complete_task(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        related_daily_plan_id: uuid.UUID | None = None,
        related_focus_session_id: uuid.UUID | None = None,
        actual_duration_min_delta: int = 0,
        commit: bool = True,
    ) -> Task:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
            action="completed",
        )

        task.status = TaskStatus.COMPLETED
        task.progress = Decimal("1.00")
        if actual_duration_min_delta:
            task.actual_duration_min += actual_duration_min_delta
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_COMPLETED",
            related_task_id=task.id,
            related_daily_plan_id=related_daily_plan_id,
            related_focus_session_id=related_focus_session_id,
            payload={"actual_duration_min_delta": actual_duration_min_delta},
        )
        if commit:
            db.commit()
            db.refresh(task)
            return self.get_task(db, task_id=task.id, user_id=user_id)
        db.flush()
        return task

    def postpone_task(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        related_daily_plan_id: uuid.UUID | None = None,
        related_focus_session_id: uuid.UUID | None = None,
        actual_duration_min_delta: int = 0,
        commit: bool = True,
    ) -> Task:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS},
            action="postponed",
        )

        task.status = TaskStatus.POSTPONED
        if actual_duration_min_delta:
            task.actual_duration_min += actual_duration_min_delta
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_POSTPONED",
            related_task_id=task.id,
            related_daily_plan_id=related_daily_plan_id,
            related_focus_session_id=related_focus_session_id,
            payload={"actual_duration_min_delta": actual_duration_min_delta},
        )
        if commit:
            db.commit()
            db.refresh(task)
            return self.get_task(db, task_id=task.id, user_id=user_id)
        db.flush()
        return task

    def breakdown_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        task = self.get_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED},
            action="broken down",
        )
        job = ai_job_service.create_job(
            db,
            user_id=user_id,
            job_type=AIJobType.TASK_BREAKDOWN,
            input_entity_type=EntityType.TASK.value,
            input_entity_id=task.id,
            provider="rule",
            model="task-breakdown-rule",
            prompt_version="p1-rule-v1",
            metadata={"mode": "sync_rule_mock"},
            commit=False,
        )
        job.status = AIJobStatus.RUNNING
        job.started_at = utc_now()

        existing_steps = sorted(task.steps, key=lambda step: (step.sort_order, step.created_at))
        if existing_steps:
            job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
            job.result_entity_type = EntityType.TASK.value
            job.result_entity_id = task.id
            job.job_metadata = {
                **job.job_metadata,
                "fallback_reason": "existing_steps_preserved",
                "created_step_ids": [],
            }
            job.finished_at = utc_now()
            self._add_breakdown_event(db, task=task, user_id=user_id, job=job, created_steps=[])
            db.commit()
            db.refresh(job)
            return {"ai_job": self._ai_job_summary(job), "created_steps": []}

        created_steps = self._create_breakdown_steps(db, task=task, user_id=user_id)
        job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
        job.result_entity_type = EntityType.TASK.value
        job.result_entity_id = task.id
        job.job_metadata = {
            **job.job_metadata,
            "fallback_reason": "rule_mock_breakdown",
            "created_step_ids": [str(step.id) for step in created_steps],
        }
        job.finished_at = utc_now()
        self._add_breakdown_event(db, task=task, user_id=user_id, job=job, created_steps=created_steps)
        db.commit()
        for step in created_steps:
            db.refresh(step)
        db.refresh(job)
        return {"ai_job": self._ai_job_summary(job), "created_steps": created_steps}

    def _add_breakdown_event(
        self,
        db: Session,
        *,
        task: Task,
        user_id: uuid.UUID,
        job: AIJob,
        created_steps: list[TaskStep],
    ) -> None:
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_BREAKDOWN_GENERATED",
            related_task_id=task.id,
            payload={
                "ai_job_id": str(job.id),
                "created_step_ids": [str(step.id) for step in created_steps],
                "fallback_reason": job.job_metadata.get("fallback_reason"),
                "mode": "rule_mock",
            },
        )

    def activate_task(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        related_daily_plan_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> Task:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        self._ensure_task_status(
            task,
            allowed={TaskStatus.POSTPONED},
            action="marked planned",
        )

        task.status = TaskStatus.ACTIVE
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            event_type="TASK_ACTIVATED",
            related_task_id=task.id,
            related_daily_plan_id=related_daily_plan_id,
        )
        if commit:
            db.commit()
            db.refresh(task)
            return self.get_task(db, task_id=task.id, user_id=user_id)
        db.flush()
        return task

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

    def get_task_dependencies(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        prerequisites = self._dependency_edges(db, user_id=user_id, dependent_task_id=task.id)
        dependents = self._dependency_edges(db, user_id=user_id, prerequisite_task_id=task.id)
        return {
            "task_id": task.id,
            "prerequisites": [self._dependency_response(edge) for edge in prerequisites],
            "dependents": [self._dependency_response(edge) for edge in dependents],
        }

    def add_task_dependency(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        prerequisite_task_id: uuid.UUID,
        reason: str | None = None,
    ) -> dict:
        dependent_task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        prerequisite_task = self._get_user_task(db, task_id=prerequisite_task_id, user_id=user_id)
        if dependent_task.id == prerequisite_task.id:
            raise ValidationDomainError("Task cannot depend on itself")
        existing = self._get_dependency_edge(
            db,
            user_id=user_id,
            dependent_task_id=dependent_task.id,
            prerequisite_task_id=prerequisite_task.id,
        )
        if existing is not None:
            return self._dependency_response(existing)
        if self._would_create_dependency_cycle(
            db,
            user_id=user_id,
            dependent_task_id=dependent_task.id,
            prerequisite_task_id=prerequisite_task.id,
        ):
            raise InvalidStateError("Task dependency would create a cycle")
        edge = TaskDependency(
            user_id=user_id,
            dependent_task_id=dependent_task.id,
            prerequisite_task_id=prerequisite_task.id,
            reason=reason,
        )
        db.add(edge)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=dependent_task.id,
            event_type="TASK_DEPENDENCY_CREATED",
            related_task_id=dependent_task.id,
            payload={
                "dependency_id": str(edge.id),
                "prerequisite_task_id": str(prerequisite_task.id),
                "reason": reason,
            },
        )
        db.commit()
        db.refresh(edge)
        return self._dependency_response(edge)

    def delete_task_dependency(
        self,
        db: Session,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        prerequisite_task_id: uuid.UUID,
    ) -> dict:
        dependent_task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        prerequisite_task = self._get_user_task(db, task_id=prerequisite_task_id, user_id=user_id)
        edge = self._get_dependency_edge(
            db,
            user_id=user_id,
            dependent_task_id=dependent_task.id,
            prerequisite_task_id=prerequisite_task.id,
        )
        if edge is None:
            raise NotFoundError("Task dependency not found")
        db.delete(edge)
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=dependent_task.id,
            event_type="TASK_DEPENDENCY_DELETED",
            related_task_id=dependent_task.id,
            payload={"prerequisite_task_id": str(prerequisite_task.id)},
        )
        db.commit()
        return self.get_task_dependencies(db, task_id=dependent_task.id, user_id=user_id)

    def _get_user_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = db.get(Task, task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("Task not found")
        return task

    def _dependency_edges(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        dependent_task_id: uuid.UUID | None = None,
        prerequisite_task_id: uuid.UUID | None = None,
    ) -> list[TaskDependency]:
        stmt = (
            select(TaskDependency)
            .options(
                selectinload(TaskDependency.dependent_task),
                selectinload(TaskDependency.prerequisite_task),
            )
            .where(TaskDependency.user_id == user_id)
        )
        if dependent_task_id is not None:
            stmt = stmt.where(TaskDependency.dependent_task_id == dependent_task_id)
        if prerequisite_task_id is not None:
            stmt = stmt.where(TaskDependency.prerequisite_task_id == prerequisite_task_id)
        return list(db.scalars(stmt.order_by(TaskDependency.created_at)).all())

    def _get_dependency_edge(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        dependent_task_id: uuid.UUID,
        prerequisite_task_id: uuid.UUID,
    ) -> TaskDependency | None:
        stmt = (
            select(TaskDependency)
            .options(
                selectinload(TaskDependency.dependent_task),
                selectinload(TaskDependency.prerequisite_task),
            )
            .where(
                TaskDependency.user_id == user_id,
                TaskDependency.dependent_task_id == dependent_task_id,
                TaskDependency.prerequisite_task_id == prerequisite_task_id,
            )
        )
        return db.scalars(stmt).first()

    def _would_create_dependency_cycle(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        dependent_task_id: uuid.UUID,
        prerequisite_task_id: uuid.UUID,
    ) -> bool:
        stmt = select(TaskDependency).where(TaskDependency.user_id == user_id)
        outgoing: dict[uuid.UUID, list[uuid.UUID]] = {}
        for edge in db.scalars(stmt).all():
            outgoing.setdefault(edge.prerequisite_task_id, []).append(edge.dependent_task_id)
        outgoing.setdefault(prerequisite_task_id, []).append(dependent_task_id)

        visited: set[uuid.UUID] = set()
        stack = [dependent_task_id]
        while stack:
            current_id = stack.pop()
            if current_id == prerequisite_task_id:
                return True
            if current_id in visited:
                continue
            visited.add(current_id)
            stack.extend(outgoing.get(current_id, []))
        return False

    def _dependency_response(self, edge: TaskDependency) -> dict:
        return {
            "id": edge.id,
            "prerequisite_task": self._dependency_node(edge.prerequisite_task),
            "dependent_task": self._dependency_node(edge.dependent_task),
            "reason": edge.reason,
        }

    def _dependency_node(self, task: Task) -> dict:
        return {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "value_level": task.value_level,
            "deadline": task.deadline,
        }

    def _create_breakdown_steps(self, db: Session, *, task: Task, user_id: uuid.UUID) -> list[TaskStep]:
        titles = self._breakdown_step_titles(task)
        created_steps: list[TaskStep] = []
        for sort_order, title in enumerate(titles, start=1):
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
                payload={"step_id": str(step.id), "title": title, "source": "task_breakdown"},
            )
            created_steps.append(step)
        return created_steps

    def _breakdown_step_titles(self, task: Task) -> list[str]:
        if task.estimated_duration_min and task.estimated_duration_min >= 60:
            return [
                "Clarify the finished state",
                "Prepare the needed context",
                "Do the main work",
                "Review and finish",
            ]
        return [
            "Clarify the finished state",
            "Do the main work",
            "Review and finish",
        ]

    def _ai_job_summary(self, job: AIJob) -> dict:
        return {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "result_entity_type": job.result_entity_type,
            "result_entity_id": job.result_entity_id,
            "error_message": job.error_message,
            "job_metadata": job.job_metadata,
        }

    def _goal_summary(self, db: Session, *, task: Task) -> dict | None:
        if task.goal_id is None:
            return None
        goal = db.get(Goal, task.goal_id)
        if goal is None:
            return None
        return {
            "id": goal.id,
            "title": goal.title,
            "deadline": goal.deadline,
            "value_level": goal.value_level,
        }

    def _today_plan_item(self, db: Session, *, task: Task) -> DailyPlanItem | None:
        plan_date = self._current_user_date(db, user_id=task.user_id)
        stmt = (
            select(DailyPlanItem)
            .join(DailyPlan)
            .where(
                DailyPlanItem.task_id == task.id,
                DailyPlan.user_id == task.user_id,
                DailyPlan.plan_date == plan_date,
                DailyPlan.status == DailyPlanStatus.ACTIVE,
                DailyPlan.current_revision_id == DailyPlanItem.plan_revision_id,
            )
            .order_by(DailyPlanItem.sort_order)
        )
        return db.scalars(stmt).first()

    def _today_context(self, item: DailyPlanItem | None) -> dict | None:
        if item is None:
            return None
        return {
            "daily_plan_id": item.daily_plan_id,
            "daily_plan_item_id": item.id,
            "plan_date": item.daily_plan.plan_date,
            "plan_version": item.daily_plan.current_version,
            "section": item.section,
            "item_status": item.status,
            "sort_order": item.sort_order,
            "recommendation_reason": item.recommendation_reason,
        }

    def _active_focus_session(self, db: Session, *, user_id: uuid.UUID) -> FocusSession | None:
        stmt = select(FocusSession).where(
            FocusSession.user_id == user_id,
            FocusSession.status == FocusSessionStatus.ACTIVE,
        )
        return db.scalars(stmt).first()

    def _execution_suggestion(self, task: Task) -> str:
        if task.status == TaskStatus.COMPLETED:
            return "This task is already complete."
        incomplete_steps = [step for step in task.steps if not step.is_completed]
        if incomplete_steps:
            next_step = sorted(incomplete_steps, key=lambda step: (step.sort_order, step.created_at))[0]
            return f"Continue with: {next_step.title}"
        if task.status == TaskStatus.POSTPONED:
            return "Bring this back only if it still matters today."
        if task.value_level == ValueLevel.HIGH or task.priority <= 2:
            return "Start this early and protect a focused block."
        return "Start with one clear step and keep the session light."

    def _current_user_date(self, db: Session, *, user_id: uuid.UUID) -> date:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        try:
            timezone = ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        return datetime.now(timezone).date()

    def _validate_user_goal(self, db: Session, *, goal_id: uuid.UUID, user_id: uuid.UUID) -> None:
        goal = db.get(Goal, goal_id)
        if goal is None or goal.user_id != user_id:
            raise ValidationDomainError("Goal not found")

    def _ensure_task_status(self, task: Task, *, allowed: set[TaskStatus], action: str) -> None:
        if task.status not in allowed:
            raise InvalidStateError(f"{task.status.value} task cannot be {action}")


task_service = TaskService()
