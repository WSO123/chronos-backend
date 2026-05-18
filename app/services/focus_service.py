from __future__ import annotations

from math import ceil
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.daily_plan import DailyPlan, DailyPlanItem
from app.models.enums import (
    ActorType,
    DailyPlanItemStatus,
    EntityType,
    FocusSessionStatus,
    TaskStatus,
)
from app.models.focus_session import FocusSession
from app.models.task import Task
from app.models.mixins import utc_now
from app.services.activity_event_service import activity_event_service
from app.services.errors import InvalidStateError, NotFoundError, ValidationDomainError
from app.services.planning_service import planning_service
from app.services.task_service import task_service


class FocusService:
    def start_session(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        daily_plan_item_id: uuid.UUID | None = None,
        planned_duration_min: int | None = None,
    ) -> FocusSession:
        self._ensure_no_active_session(db, user_id=user_id)
        task = self._get_user_task(db, task_id=task_id, user_id=user_id)
        if task.status not in {TaskStatus.ACTIVE, TaskStatus.POSTPONED}:
            raise InvalidStateError(f"{task.status.value} task cannot start focus")

        daily_plan_id = None
        if daily_plan_item_id is not None:
            item = self._get_current_item(db, item_id=daily_plan_item_id, user_id=user_id)
            if item.task_id != task.id:
                raise ValidationDomainError("Daily plan item does not belong to task")
            if item.status in {DailyPlanItemStatus.COMPLETED, DailyPlanItemStatus.SKIPPED}:
                raise InvalidStateError(f"{item.status.value} daily plan item cannot start focus")
            daily_plan_id = item.daily_plan_id
        else:
            item = planning_service.get_current_today_item_for_task(
                db,
                user_id=user_id,
                task_id=task.id,
            )
            if item is not None:
                if item.status in {DailyPlanItemStatus.COMPLETED, DailyPlanItemStatus.SKIPPED}:
                    raise InvalidStateError(f"{item.status.value} daily plan item cannot start focus")
                daily_plan_item_id = item.id
                daily_plan_id = item.daily_plan_id

        task.status = TaskStatus.IN_FOCUS
        session = FocusSession(
            user_id=user_id,
            task_id=task.id,
            daily_plan_id=daily_plan_id,
            daily_plan_item_id=daily_plan_item_id,
            planned_duration_min=planned_duration_min,
            actual_duration_min=0,
            status=FocusSessionStatus.ACTIVE,
        )
        db.add(session)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.FOCUS_SESSION,
            entity_id=session.id,
            event_type="FOCUS_SESSION_STARTED",
            actor_type=ActorType.USER,
            related_task_id=task.id,
            related_daily_plan_id=daily_plan_id,
            related_focus_session_id=session.id,
            payload={"planned_duration_min": planned_duration_min},
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if self._is_active_session_unique_violation(exc):
                raise InvalidStateError("User already has an active focus session") from exc
            raise
        db.refresh(session)
        return session

    def get_session(self, db: Session, *, session_id: uuid.UUID, user_id: uuid.UUID) -> FocusSession:
        session = db.get(FocusSession, session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError("Focus session not found")
        return session

    def complete_session(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        actual_duration_min: int | None = None,
    ) -> FocusSession:
        session = self._get_active_session_for_update(db, session_id=session_id, user_id=user_id)
        actual_minutes = self._actual_minutes(session, actual_duration_min=actual_duration_min)
        session.status = FocusSessionStatus.COMPLETED
        session.ended_at = utc_now()
        session.actual_duration_min = actual_minutes
        progress_delta = self._minimum_viable_progress_delta(db, session=session, user_id=user_id)
        if progress_delta is None:
            updated_task = task_service.complete_task(
                db,
                task_id=session.task_id,
                user_id=user_id,
                related_daily_plan_id=session.daily_plan_id,
                related_focus_session_id=session.id,
                actual_duration_min_delta=actual_minutes,
                commit=False,
            )
        else:
            updated_task = task_service.record_partial_progress(
                db,
                task_id=session.task_id,
                user_id=user_id,
                related_daily_plan_id=session.daily_plan_id,
                related_focus_session_id=session.id,
                progress_delta=progress_delta,
                actual_duration_min_delta=actual_minutes,
                commit=False,
            )
        goal_progress_feedback = getattr(updated_task, "goal_progress_feedback", None)
        self._sync_daily_plan_item(
            db,
            session=session,
            user_id=user_id,
            status=DailyPlanItemStatus.COMPLETED,
            focus_minutes=actual_minutes,
        )
        self._add_finish_event(
            db,
            session=session,
            user_id=user_id,
            event_type="FOCUS_SESSION_COMPLETED",
            actual_duration_min=actual_minutes,
        )
        self._add_execution_learning_event(
            db,
            session=session,
            user_id=user_id,
            outcome="completed" if progress_delta is None else "partial_progress",
            actual_duration_min=actual_minutes,
        )
        db.commit()
        db.refresh(session)
        session.goal_progress_feedback = goal_progress_feedback
        return session

    def interrupt_session(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        actual_duration_min: int | None = None,
        interruption_reason: str | None = None,
    ) -> FocusSession:
        session = self._get_active_session_for_update(db, session_id=session_id, user_id=user_id)
        actual_minutes = self._actual_minutes(session, actual_duration_min=actual_duration_min)
        session.status = FocusSessionStatus.INTERRUPTED
        session.ended_at = utc_now()
        session.actual_duration_min = actual_minutes
        session.interruption_reason = interruption_reason

        task = self._get_user_task(db, task_id=session.task_id, user_id=user_id)
        if task.status == TaskStatus.IN_FOCUS:
            task.status = TaskStatus.ACTIVE
        if actual_minutes:
            task.actual_duration_min += actual_minutes
        self._sync_daily_plan_item(db, session=session, user_id=user_id, status=None, focus_minutes=actual_minutes)
        self._add_finish_event(
            db,
            session=session,
            user_id=user_id,
            event_type="FOCUS_SESSION_INTERRUPTED",
            actual_duration_min=actual_minutes,
            payload={"interruption_reason": interruption_reason},
        )
        self._add_execution_learning_event(
            db,
            session=session,
            user_id=user_id,
            outcome="interrupted",
            actual_duration_min=actual_minutes,
            payload={"interruption_reason": interruption_reason},
        )
        db.commit()
        db.refresh(session)
        return session

    def postpone_session(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        actual_duration_min: int | None = None,
        interruption_reason: str | None = None,
    ) -> FocusSession:
        session = self._get_active_session_for_update(db, session_id=session_id, user_id=user_id)
        actual_minutes = self._actual_minutes(session, actual_duration_min=actual_duration_min)
        session.status = FocusSessionStatus.POSTPONED
        session.ended_at = utc_now()
        session.actual_duration_min = actual_minutes
        session.interruption_reason = interruption_reason
        task_service.postpone_task(
            db,
            task_id=session.task_id,
            user_id=user_id,
            related_daily_plan_id=session.daily_plan_id,
            related_focus_session_id=session.id,
            actual_duration_min_delta=actual_minutes,
            commit=False,
        )
        self._sync_daily_plan_item(
            db,
            session=session,
            user_id=user_id,
            status=DailyPlanItemStatus.POSTPONED,
            focus_minutes=actual_minutes,
        )
        self._add_finish_event(
            db,
            session=session,
            user_id=user_id,
            event_type="FOCUS_SESSION_POSTPONED",
            actual_duration_min=actual_minutes,
            payload={"interruption_reason": interruption_reason},
        )
        self._add_execution_learning_event(
            db,
            session=session,
            user_id=user_id,
            outcome="postponed",
            actual_duration_min=actual_minutes,
            payload={"interruption_reason": interruption_reason},
        )
        db.commit()
        db.refresh(session)
        return session

    def _ensure_no_active_session(self, db: Session, *, user_id: uuid.UUID) -> None:
        stmt = select(FocusSession).where(
            FocusSession.user_id == user_id,
            FocusSession.status == FocusSessionStatus.ACTIVE,
        )
        if db.scalars(stmt).first() is not None:
            raise InvalidStateError("User already has an active focus session")

    def _is_active_session_unique_violation(self, exc: IntegrityError) -> bool:
        diag = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        if constraint_name == "uq_focus_sessions_user_active":
            return True
        message = str(exc.orig)
        return "uq_focus_sessions_user_active" in message or "UNIQUE constraint failed: focus_sessions.user_id" in message

    def _get_active_session_for_update(self, db: Session, *, session_id: uuid.UUID, user_id: uuid.UUID) -> FocusSession:
        stmt = (
            select(FocusSession)
            .where(
                FocusSession.id == session_id,
                FocusSession.user_id == user_id,
            )
            .with_for_update()
        )
        session = db.scalars(stmt).first()
        if session is None:
            raise NotFoundError("Focus session not found")
        if session.status != FocusSessionStatus.ACTIVE:
            raise InvalidStateError(f"{session.status.value} focus session cannot be updated")
        return session

    def _get_user_task(self, db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = db.get(Task, task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("Task not found")
        return task

    def _get_current_item(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID) -> DailyPlanItem:
        stmt = (
            select(DailyPlanItem)
            .join(DailyPlan)
            .where(
                DailyPlanItem.id == item_id,
                DailyPlan.user_id == user_id,
                DailyPlan.current_revision_id == DailyPlanItem.plan_revision_id,
            )
        )
        item = db.scalars(stmt).first()
        if item is None:
            raise NotFoundError("Daily plan item not found")
        return item

    def _sync_daily_plan_item(
        self,
        db: Session,
        *,
        session: FocusSession,
        user_id: uuid.UUID,
        status: DailyPlanItemStatus | None,
        focus_minutes: int,
    ) -> None:
        if session.daily_plan_item_id is None:
            return
        planning_service.apply_focus_result(
            db,
            item_id=session.daily_plan_item_id,
            user_id=user_id,
            status=status,
            focus_minutes=focus_minutes,
        )

    def _minimum_viable_progress_delta(
        self,
        db: Session,
        *,
        session: FocusSession,
        user_id: uuid.UUID,
    ):
        if session.daily_plan_item_id is None:
            return None
        item = self._get_current_item(db, item_id=session.daily_plan_item_id, user_id=user_id)
        return planning_service.minimum_viable_progress_delta_for_item(item)

    def _actual_minutes(self, session: FocusSession, *, actual_duration_min: int | None) -> int:
        if actual_duration_min is not None:
            return actual_duration_min
        elapsed_seconds = (utc_now() - session.started_at).total_seconds()
        return max(0, ceil(elapsed_seconds / 60))

    def _add_finish_event(
        self,
        db: Session,
        *,
        session: FocusSession,
        user_id: uuid.UUID,
        event_type: str,
        actual_duration_min: int,
        payload: dict | None = None,
    ) -> None:
        event_payload = {"actual_duration_min": actual_duration_min}
        if session.planned_duration_min is not None:
            event_payload["planned_duration_min"] = session.planned_duration_min
            event_payload["duration_delta_min"] = actual_duration_min - session.planned_duration_min
        if payload:
            event_payload.update(payload)
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.FOCUS_SESSION,
            entity_id=session.id,
            event_type=event_type,
            actor_type=ActorType.USER,
            related_task_id=session.task_id,
            related_daily_plan_id=session.daily_plan_id,
            related_focus_session_id=session.id,
            payload=event_payload,
        )

    def _add_execution_learning_event(
        self,
        db: Session,
        *,
        session: FocusSession,
        user_id: uuid.UUID,
        outcome: str,
        actual_duration_min: int,
        payload: dict | None = None,
    ) -> None:
        planned_minutes = session.planned_duration_min
        event_payload = {
            "version": "p2-execution-learning-v2",
            "source": "focus_session",
            "outcome": outcome,
            "planned_duration_min": planned_minutes,
            "actual_duration_min": actual_duration_min,
            "duration_delta_min": (
                actual_duration_min - planned_minutes if planned_minutes is not None else None
            ),
            "learning_contract": self._execution_learning_contract(),
        }
        if payload:
            event_payload.update(payload)
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.FOCUS_SESSION,
            entity_id=session.id,
            event_type="EXECUTION_LEARNING_OBSERVED",
            actor_type=ActorType.SYSTEM,
            related_task_id=session.task_id,
            related_daily_plan_id=session.daily_plan_id,
            related_focus_session_id=session.id,
            payload=event_payload,
        )

    def _execution_learning_contract(self) -> dict:
        return {
            "version": "p2-execution-learning-contract-v1",
            "scope": "focus_result_to_planning_calibration",
            "source_of_truth": "planning-engine-v1",
            "can_affect": [
                "today_item_estimated_duration_min",
                "planning_objective_score",
                "strategy_explanation",
                "task_rationale_score_signals",
            ],
            "cannot_affect": [
                "task_estimated_duration_min",
                "task_status",
                "goal_state",
                "llm_direct_sort_order",
            ],
            "task_mutation_allowed": False,
            "requires_confirmed_focus_result": True,
            "explanation": "Focus 执行结果只用于后续计划校准和解释，不会覆盖任务原始估时或让 LLM 直接排序。",
        }


focus_service = FocusService()
