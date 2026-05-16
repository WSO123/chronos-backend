from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.reminder import Reminder
from app.models.task import Task
from app.models.user import User
from app.services.errors import InvalidStateError, NotFoundError, ValidationDomainError


class ReminderService:
    allowed_types = {"execution", "deadline", "system", "team"}
    allowed_channels = {"in_app", "push", "email"}
    allowed_sources = {"manual", "system", "ai", "worker"}
    allowed_statuses = {"scheduled", "sent", "dismissed", "canceled"}

    def create_reminder(self, db: Session, *, user_id: uuid.UUID, payload: dict) -> Reminder:
        self._ensure_user(db, user_id=user_id)
        self._validate_create_payload(payload)
        task_id = payload.get("task_id")
        goal_id = payload.get("goal_id")
        if task_id is not None:
            self._ensure_task(db, user_id=user_id, task_id=task_id)
        if goal_id is not None:
            self._ensure_goal(db, user_id=user_id, goal_id=goal_id)

        reminder = Reminder(
            user_id=user_id,
            task_id=task_id,
            goal_id=goal_id,
            title=payload["title"].strip(),
            message=payload.get("message"),
            reminder_type=payload.get("reminder_type") or "execution",
            scheduled_for=self._normalize_datetime(payload["scheduled_for"]),
            channel=payload.get("channel") or "in_app",
            source=payload.get("source") or "manual",
            status="scheduled",
            reminder_metadata=payload.get("reminder_metadata") or {},
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    def list_reminders(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        self._ensure_user(db, user_id=user_id)
        if status is not None and status not in self.allowed_statuses:
            raise ValidationDomainError(f"Reminder status {status} is not supported")
        stmt = select(Reminder).where(Reminder.user_id == user_id)
        if status is not None:
            stmt = stmt.where(Reminder.status == status)
        reminders = list(
            db.scalars(
                stmt.order_by(Reminder.scheduled_for, Reminder.created_at)
                .limit(min(max(limit, 1), 100))
                .offset(max(offset, 0))
            ).all()
        )
        scheduled_count = self._count_by_status(db, user_id=user_id, status="scheduled")
        overdue_count = self._overdue_count(db, user_id=user_id)
        return {
            "reminders": reminders,
            "scheduled_count": scheduled_count,
            "overdue_count": overdue_count,
        }

    def dismiss_reminder(self, db: Session, *, reminder_id: uuid.UUID, user_id: uuid.UUID) -> Reminder:
        reminder = self._get_user_reminder(db, reminder_id=reminder_id, user_id=user_id)
        if reminder.status in {"dismissed", "canceled"}:
            return reminder
        if reminder.status == "sent":
            raise InvalidStateError("Sent reminders cannot be dismissed from the pending center")
        reminder.status = "dismissed"
        reminder.dismissed_at = datetime.now(UTC)
        db.commit()
        db.refresh(reminder)
        return reminder

    def to_response(self, reminder: Reminder) -> dict:
        return {
            "id": reminder.id,
            "created_at": reminder.created_at,
            "updated_at": reminder.updated_at,
            "user_id": reminder.user_id,
            "task_id": reminder.task_id,
            "goal_id": reminder.goal_id,
            "title": reminder.title,
            "message": reminder.message,
            "reminder_type": reminder.reminder_type,
            "status": reminder.status,
            "scheduled_for": reminder.scheduled_for,
            "channel": reminder.channel,
            "source": reminder.source,
            "dismissed_at": reminder.dismissed_at,
            "sent_at": reminder.sent_at,
            "reminder_metadata": reminder.reminder_metadata,
        }

    def _ensure_user(self, db: Session, *, user_id: uuid.UUID) -> User:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _ensure_task(self, db: Session, *, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
        task = db.get(Task, task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("Task not found")
        return task

    def _ensure_goal(self, db: Session, *, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
        goal = db.get(Goal, goal_id)
        if goal is None or goal.user_id != user_id:
            raise NotFoundError("Goal not found")
        return goal

    def _get_user_reminder(self, db: Session, *, reminder_id: uuid.UUID, user_id: uuid.UUID) -> Reminder:
        reminder = db.get(Reminder, reminder_id)
        if reminder is None or reminder.user_id != user_id:
            raise NotFoundError("Reminder not found")
        return reminder

    def _validate_create_payload(self, payload: dict) -> None:
        if not payload["title"].strip():
            raise ValidationDomainError("Reminder title cannot be empty")
        if payload.get("task_id") is not None and payload.get("goal_id") is not None:
            raise ValidationDomainError("Reminder can link to either a task or a goal, not both")
        reminder_type = payload.get("reminder_type") or "execution"
        if reminder_type not in self.allowed_types:
            raise ValidationDomainError(f"Reminder type {reminder_type} is not supported")
        channel = payload.get("channel") or "in_app"
        if channel not in self.allowed_channels:
            raise ValidationDomainError(f"Reminder channel {channel} is not supported")
        source = payload.get("source") or "manual"
        if source not in self.allowed_sources:
            raise ValidationDomainError(f"Reminder source {source} is not supported")

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _count_by_status(self, db: Session, *, user_id: uuid.UUID, status: str) -> int:
        stmt = select(Reminder.id).where(Reminder.user_id == user_id, Reminder.status == status)
        return len(list(db.scalars(stmt).all()))

    def _overdue_count(self, db: Session, *, user_id: uuid.UUID) -> int:
        stmt = select(Reminder.id).where(
            Reminder.user_id == user_id,
            Reminder.status == "scheduled",
            Reminder.scheduled_for < datetime.now(UTC),
        )
        return len(list(db.scalars(stmt).all()))


reminder_service = ReminderService()
