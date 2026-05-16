from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import GoalStatus, TaskStatus
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

    def dispatch_due_reminders(
        self,
        db: Session,
        *,
        now: datetime | None = None,
        limit: int = 50,
        channel: str | None = None,
    ) -> dict:
        resolved_now = now or datetime.now(UTC)
        if channel is not None and channel not in self.allowed_channels:
            raise ValidationDomainError(f"Reminder channel {channel} is not supported")
        stmt = (
            select(Reminder)
            .where(
                Reminder.status == "scheduled",
                Reminder.scheduled_for <= resolved_now,
            )
            .order_by(Reminder.scheduled_for, Reminder.created_at)
            .limit(min(max(limit, 1), 100))
        )
        if channel is not None:
            stmt = stmt.where(Reminder.channel == channel)
        due_reminders = list(db.scalars(stmt).all())
        for reminder in due_reminders:
            reminder.status = "sent"
            reminder.sent_at = resolved_now
        db.commit()
        for reminder in due_reminders:
            db.refresh(reminder)
        return {
            "status": "dispatched",
            "sent_count": len(due_reminders),
            "channel": channel,
            "sent_at": resolved_now,
            "reminders": due_reminders,
        }

    def generate_deadline_reminders(
        self,
        db: Session,
        *,
        user_id: uuid.UUID | None = None,
        target_date: date | None = None,
        window_days: int = 1,
        reminder_hour: int = 9,
    ) -> dict:
        resolved_date = target_date or date.today()
        window_days = min(max(window_days, 1), 14)
        reminder_hour = min(max(reminder_hour, 0), 23)
        users = [self._ensure_user(db, user_id=user_id)] if user_id is not None else self._active_users(db)
        created: list[Reminder] = []
        skipped_existing_count = 0
        for user in users:
            due_end = resolved_date + timedelta(days=window_days - 1)
            candidates = self._deadline_candidates(
                db,
                user_id=user.id,
                start_date=resolved_date,
                end_date=due_end,
            )
            for entity_type, entity in candidates:
                scheduled_for = self._deadline_scheduled_for(
                    user_timezone=user.timezone,
                    deadline=entity.deadline,
                    reminder_hour=reminder_hour,
                )
                if self._deadline_reminder_exists(
                    db,
                    user_id=user.id,
                    entity_type=entity_type,
                    entity_id=entity.id,
                    scheduled_for=scheduled_for,
                ):
                    skipped_existing_count += 1
                    continue
                reminder = Reminder(
                    user_id=user.id,
                    task_id=entity.id if entity_type == "task" else None,
                    goal_id=entity.id if entity_type == "goal" else None,
                    title=self._deadline_title(entity_type=entity_type, title=entity.title),
                    message=self._deadline_message(entity_type=entity_type, deadline=entity.deadline),
                    reminder_type="deadline",
                    status="scheduled",
                    scheduled_for=scheduled_for,
                    channel="in_app",
                    source="worker",
                    reminder_metadata={
                        "generator": "deadline_v1",
                        "entity_type": entity_type,
                        "deadline": entity.deadline.isoformat(),
                    },
                )
                db.add(reminder)
                created.append(reminder)
        db.commit()
        for reminder in created:
            db.refresh(reminder)
        return {
            "status": "generated",
            "created_count": len(created),
            "skipped_existing_count": skipped_existing_count,
            "target_date": resolved_date,
            "window_days": window_days,
            "reminders": created,
        }

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

    def _active_users(self, db: Session) -> list[User]:
        stmt = select(User).where(User.is_active.is_(True)).order_by(User.created_at)
        return list(db.scalars(stmt).all())

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

    def _deadline_candidates(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[tuple[str, Task | Goal]]:
        task_stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.deadline >= start_date,
                Task.deadline <= end_date,
                Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.ARCHIVED]),
            )
            .order_by(Task.deadline, Task.created_at)
        )
        goal_stmt = (
            select(Goal)
            .where(
                Goal.user_id == user_id,
                Goal.deadline >= start_date,
                Goal.deadline <= end_date,
                Goal.status == GoalStatus.ACTIVE,
            )
            .order_by(Goal.deadline, Goal.created_at)
        )
        candidates: list[tuple[str, Task | Goal]] = [("task", task) for task in db.scalars(task_stmt).all()]
        candidates.extend(("goal", goal) for goal in db.scalars(goal_stmt).all())
        return candidates

    def _deadline_scheduled_for(self, *, user_timezone: str, deadline: date, reminder_hour: int) -> datetime:
        try:
            timezone = ZoneInfo(user_timezone)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        return datetime.combine(deadline, time(hour=reminder_hour), tzinfo=timezone).astimezone(UTC)

    def _deadline_reminder_exists(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        scheduled_for: datetime,
    ) -> bool:
        stmt = select(Reminder.id).where(
            Reminder.user_id == user_id,
            Reminder.reminder_type == "deadline",
            Reminder.source == "worker",
            Reminder.scheduled_for == scheduled_for,
        )
        if entity_type == "task":
            stmt = stmt.where(Reminder.task_id == entity_id)
        else:
            stmt = stmt.where(Reminder.goal_id == entity_id)
        return db.scalars(stmt).first() is not None

    def _deadline_title(self, *, entity_type: str, title: str) -> str:
        prefix = "Task deadline" if entity_type == "task" else "Goal deadline"
        return f"{prefix}: {title}"

    def _deadline_message(self, *, entity_type: str, deadline: date) -> str:
        target = "task" if entity_type == "task" else "goal"
        return f"This {target} is due on {deadline.isoformat()}. Keep the reminder gentle and actionable."


reminder_service = ReminderService()
