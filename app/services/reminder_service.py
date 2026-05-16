from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_plan import DailyPlan, DailyPlanItem
from app.models.enums import (
    DailyPlanItemSection,
    DailyPlanItemStatus,
    DailyPlanStatus,
    GoalStatus,
    TaskStatus,
)
from app.models.goal import Goal
from app.models.reminder import Reminder
from app.models.reminder_delivery import ReminderDeliveryAttempt
from app.models.task import Task
from app.models.user import User, UserSettings
from app.providers.notifications import NotificationDeliveryRequest, notification_delivery_registry
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

    def reminder_summary(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        now: datetime | None = None,
    ) -> dict:
        self._ensure_user(db, user_id=user_id)
        resolved_now = self._normalize_datetime(now or datetime.now(UTC))
        stmt = (
            select(Reminder)
            .where(
                Reminder.user_id == user_id,
                Reminder.status == "scheduled",
            )
            .order_by(Reminder.scheduled_for, Reminder.created_at)
        )
        reminders = list(db.scalars(stmt).all())
        due_count = 0
        unseen_count = 0
        execution_count = 0
        deadline_count = 0
        for reminder in reminders:
            if reminder.seen_at is None:
                unseen_count += 1
            if self._normalize_datetime(reminder.scheduled_for) <= resolved_now:
                due_count += 1
            if reminder.reminder_type == "execution":
                execution_count += 1
            if reminder.reminder_type == "deadline":
                deadline_count += 1
        return {
            "pending_count": len(reminders),
            "unseen_count": unseen_count,
            "due_count": due_count,
            "execution_count": execution_count,
            "deadline_count": deadline_count,
            "next_reminder": reminders[0] if reminders else None,
        }

    def mark_reminder_seen(self, db: Session, *, reminder_id: uuid.UUID, user_id: uuid.UUID) -> Reminder:
        reminder = self._get_user_reminder(db, reminder_id=reminder_id, user_id=user_id)
        if reminder.seen_at is None:
            reminder.seen_at = datetime.now(UTC)
            db.commit()
            db.refresh(reminder)
        return reminder

    def mark_reminders_seen(
        self,
        db: Session,
        *,
        reminder_ids: list[uuid.UUID],
        user_id: uuid.UUID,
    ) -> dict:
        unique_ids = list(dict.fromkeys(reminder_ids))
        stmt = (
            select(Reminder)
            .where(
                Reminder.user_id == user_id,
                Reminder.id.in_(unique_ids),
            )
            .order_by(Reminder.scheduled_for, Reminder.created_at)
        )
        reminders = list(db.scalars(stmt).all())
        if len(reminders) != len(unique_ids):
            raise NotFoundError("Reminder not found")
        now = datetime.now(UTC)
        updated_count = 0
        already_seen_count = 0
        for reminder in reminders:
            if reminder.seen_at is None:
                reminder.seen_at = now
                updated_count += 1
            else:
                already_seen_count += 1
        db.commit()
        for reminder in reminders:
            db.refresh(reminder)
        return {
            "updated_count": updated_count,
            "already_seen_count": already_seen_count,
            "reminders": reminders,
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
        resolved_now = self._normalize_datetime(now or datetime.now(UTC))
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
        sent_reminders: list[Reminder] = []
        delivery_results: list[dict] = []
        skipped_count = 0
        cooldown_count = 0
        for reminder in due_reminders:
            cooldown_until = self._delivery_cooldown_until(db, reminder=reminder, now=resolved_now)
            if cooldown_until is not None:
                cooldown_count += 1
                delivery_results.append(
                    {
                        "reminder_id": reminder.id,
                        "channel": reminder.channel,
                        "status": "cooldown",
                        "provider": None,
                        "reason": "retry_cooldown",
                        "next_retry_at": cooldown_until,
                    }
                )
                continue
            delivery_result = notification_delivery_registry.deliver(self._delivery_request_for(reminder))
            next_retry_at = None
            if delivery_result.status != "sent":
                next_retry_at = resolved_now + timedelta(minutes=15)
            self._record_delivery_attempt(
                db,
                reminder=reminder,
                delivery_result=delivery_result,
                attempted_at=resolved_now,
                next_retry_at=next_retry_at,
            )
            delivery_results.append(self._delivery_result_to_dict(delivery_result, next_retry_at=next_retry_at))
            if delivery_result.status != "sent":
                skipped_count += 1
                continue
            reminder.status = "sent"
            reminder.sent_at = resolved_now
            sent_reminders.append(reminder)
        db.commit()
        for reminder in sent_reminders:
            db.refresh(reminder)
        return {
            "status": "dispatched",
            "sent_count": len(sent_reminders),
            "skipped_count": skipped_count,
            "cooldown_count": cooldown_count,
            "channel": channel,
            "sent_at": resolved_now,
            "reminders": sent_reminders,
            "delivery_results": delivery_results,
        }

    def generate_deadline_reminders(
        self,
        db: Session,
        *,
        user_id: uuid.UUID | None = None,
        target_date: date | None = None,
        window_days: int = 1,
        reminder_hour: int | None = None,
    ) -> dict:
        resolved_date = target_date or date.today()
        window_days = min(max(window_days, 1), 14)
        users = [self._ensure_user(db, user_id=user_id)] if user_id is not None else self._active_users(db)
        created: list[Reminder] = []
        skipped_existing_count = 0
        skipped_disabled_count = 0
        for user in users:
            settings = self._settings_for_user(db, user_id=user.id)
            if not self._reminder_type_enabled(settings=settings, reminder_type="deadline"):
                skipped_disabled_count += 1
                continue
            resolved_reminder_hour = min(
                max(
                    reminder_hour if reminder_hour is not None else settings.deadline_reminder_hour,
                    0,
                ),
                23,
            )
            channel = self._preferred_channel(settings)
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
                    reminder_hour=resolved_reminder_hour,
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
                    channel=channel,
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
            "skipped_disabled_count": skipped_disabled_count,
            "target_date": resolved_date,
            "window_days": window_days,
            "reminders": created,
        }

    def generate_execution_reminders(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plan_date: date,
        limit: int | None = None,
        start_hour: int | None = None,
        spacing_minutes: int | None = None,
    ) -> dict:
        user = self._ensure_user(db, user_id=user_id)
        settings = self._settings_for_user(db, user_id=user_id)
        if not self._reminder_type_enabled(settings=settings, reminder_type="execution"):
            return {
                "status": "disabled",
                "created_count": 0,
                "skipped_existing_count": 0,
                "plan_date": plan_date,
                "reminders": [],
            }
        limit = min(max(limit if limit is not None else settings.execution_reminder_limit, 1), 10)
        start_hour = min(
            max(
                start_hour if start_hour is not None else settings.execution_reminder_start_hour,
                0,
            ),
            23,
        )
        spacing_minutes = min(
            max(
                spacing_minutes if spacing_minutes is not None else settings.execution_reminder_spacing_minutes,
                15,
            ),
            180,
        )
        channel = self._preferred_channel(settings)
        plan = self._active_plan_for_date(db, user_id=user_id, plan_date=plan_date)
        if plan is None:
            return {
                "status": "no_plan",
                "created_count": 0,
                "skipped_existing_count": 0,
                "plan_date": plan_date,
                "reminders": [],
            }

        items = self._execution_candidate_items(db, plan=plan, limit=limit)
        created: list[Reminder] = []
        skipped_existing_count = 0
        for index, item in enumerate(items):
            scheduled_for = self._execution_scheduled_for(
                user_timezone=user.timezone,
                plan_date=plan_date,
                start_hour=start_hour,
                spacing_minutes=spacing_minutes,
                index=index,
            )
            if self._execution_reminder_exists(
                db,
                user_id=user_id,
                task_id=item.task_id,
                scheduled_for=scheduled_for,
            ):
                skipped_existing_count += 1
                continue
            reminder = Reminder(
                user_id=user_id,
                task_id=item.task_id,
                goal_id=None,
                title=f"Start: {item.task.title}",
                message="A gentle execution reminder from today's sequence.",
                reminder_type="execution",
                status="scheduled",
                scheduled_for=scheduled_for,
                channel=channel,
                source="worker",
                reminder_metadata={
                    "generator": "execution_v1",
                    "daily_plan_id": str(plan.id),
                    "daily_plan_item_id": str(item.id),
                    "plan_date": plan_date.isoformat(),
                    "section": item.section.value,
                    "sort_order": item.sort_order,
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
            "plan_date": plan_date,
            "daily_plan_id": plan.id,
            "reminders": created,
        }

    def generate_execution_reminders_for_active_users(
        self,
        db: Session,
        *,
        plan_date: date,
        max_users: int = 100,
        limit: int | None = None,
        start_hour: int | None = None,
        spacing_minutes: int | None = None,
    ) -> dict:
        max_users = min(max(max_users, 1), 1000)
        users = self._active_users(db)[:max_users]
        user_results = []
        created_count = 0
        skipped_existing_count = 0
        no_plan_count = 0
        disabled_count = 0
        for user in users:
            if self._active_plan_for_date(db, user_id=user.id, plan_date=plan_date) is None:
                no_plan_count += 1
                user_results.append(
                    {
                        "user_id": user.id,
                        "status": "no_plan",
                        "created_count": 0,
                        "skipped_existing_count": 0,
                    }
                )
                continue
            result = self.generate_execution_reminders(
                db,
                user_id=user.id,
                plan_date=plan_date,
                limit=limit,
                start_hour=start_hour,
                spacing_minutes=spacing_minutes,
            )
            created_count += result["created_count"]
            skipped_existing_count += result["skipped_existing_count"]
            if result["status"] == "disabled":
                disabled_count += 1
            user_results.append(
                {
                    "user_id": user.id,
                    "status": result["status"],
                    "created_count": result["created_count"],
                    "skipped_existing_count": result["skipped_existing_count"],
                }
            )
        return {
            "status": "generated",
            "plan_date": plan_date,
            "processed_user_count": len(users),
            "created_count": created_count,
            "skipped_existing_count": skipped_existing_count,
            "no_plan_count": no_plan_count,
            "disabled_count": disabled_count,
            "user_results": user_results,
        }

    def cleanup_delivery_attempts(
        self,
        db: Session,
        *,
        retention_days: int = 30,
        now: datetime | None = None,
        limit: int = 500,
    ) -> dict:
        resolved_now = self._normalize_datetime(now or datetime.now(UTC))
        retention_days = min(max(retention_days, 1), 365)
        limit = min(max(limit, 1), 1000)
        cutoff = resolved_now - timedelta(days=retention_days)
        stmt = (
            select(ReminderDeliveryAttempt)
            .where(ReminderDeliveryAttempt.attempted_at < cutoff)
            .order_by(ReminderDeliveryAttempt.attempted_at)
            .limit(limit)
        )
        attempts = list(db.scalars(stmt).all())
        for attempt in attempts:
            db.delete(attempt)
        db.commit()
        return {
            "status": "cleaned",
            "deleted_count": len(attempts),
            "retention_days": retention_days,
            "cutoff": cutoff,
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
            "seen_at": reminder.seen_at,
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

    def _delivery_request_for(self, reminder: Reminder) -> NotificationDeliveryRequest:
        return NotificationDeliveryRequest(
            reminder_id=reminder.id,
            user_id=reminder.user_id,
            channel=reminder.channel,
            title=reminder.title,
            message=reminder.message,
            scheduled_for=reminder.scheduled_for,
            metadata=reminder.reminder_metadata,
        )

    def _delivery_result_to_dict(self, result, *, next_retry_at: datetime | None = None) -> dict:
        return {
            "reminder_id": result.reminder_id,
            "channel": result.channel,
            "status": result.status,
            "provider": result.provider,
            "reason": result.reason,
            "next_retry_at": next_retry_at,
        }

    def _record_delivery_attempt(
        self,
        db: Session,
        *,
        reminder: Reminder,
        delivery_result,
        attempted_at: datetime,
        next_retry_at: datetime | None,
    ) -> None:
        db.add(
            ReminderDeliveryAttempt(
                user_id=reminder.user_id,
                reminder_id=reminder.id,
                channel=reminder.channel,
                provider=delivery_result.provider,
                status=delivery_result.status,
                reason=delivery_result.reason,
                attempted_at=attempted_at,
                next_retry_at=next_retry_at,
                attempt_metadata={
                    "title": reminder.title,
                    "reminder_type": reminder.reminder_type,
                },
            )
        )

    def _delivery_cooldown_until(
        self,
        db: Session,
        *,
        reminder: Reminder,
        now: datetime,
    ) -> datetime | None:
        stmt = (
            select(ReminderDeliveryAttempt)
            .where(ReminderDeliveryAttempt.reminder_id == reminder.id)
            .order_by(ReminderDeliveryAttempt.attempted_at.desc())
            .limit(1)
        )
        latest = db.scalars(stmt).first()
        if latest is None or latest.status == "sent" or latest.next_retry_at is None:
            return None
        next_retry_at = latest.next_retry_at
        if next_retry_at.tzinfo is None:
            next_retry_at = next_retry_at.replace(tzinfo=UTC)
        return next_retry_at if next_retry_at > now else None

    def _settings_for_user(self, db: Session, *, user_id: uuid.UUID) -> UserSettings:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings = db.scalars(stmt).first()
        if settings is not None:
            return settings
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.flush()
        return settings

    def _reminder_type_enabled(self, *, settings: UserSettings, reminder_type: str) -> bool:
        if not settings.notification_enabled:
            return False
        if reminder_type == "execution":
            return settings.reminder_execution_enabled
        if reminder_type == "deadline":
            return settings.reminder_deadline_enabled
        return True

    def _preferred_channel(self, settings: UserSettings) -> str:
        if settings.reminder_channel_in_app_enabled:
            return "in_app"
        if settings.reminder_channel_push_enabled:
            return "push"
        return "email"

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

    def _active_plan_for_date(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plan_date: date,
    ) -> DailyPlan | None:
        stmt = select(DailyPlan).where(
            DailyPlan.user_id == user_id,
            DailyPlan.plan_date == plan_date,
            DailyPlan.status == DailyPlanStatus.ACTIVE,
        )
        return db.scalars(stmt).first()

    def _execution_candidate_items(
        self,
        db: Session,
        *,
        plan: DailyPlan,
        limit: int,
    ) -> list[DailyPlanItem]:
        stmt = (
            select(DailyPlanItem)
            .where(
                DailyPlanItem.daily_plan_id == plan.id,
                DailyPlanItem.plan_revision_id == plan.current_revision_id,
                DailyPlanItem.status == DailyPlanItemStatus.PLANNED,
                DailyPlanItem.section.in_([DailyPlanItemSection.PINNED, DailyPlanItemSection.RECOMMENDED]),
            )
            .order_by(DailyPlanItem.sort_order)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    def _execution_scheduled_for(
        self,
        *,
        user_timezone: str,
        plan_date: date,
        start_hour: int,
        spacing_minutes: int,
        index: int,
    ) -> datetime:
        try:
            timezone = ZoneInfo(user_timezone)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        local_start = datetime.combine(plan_date, time(hour=start_hour), tzinfo=timezone)
        return (local_start + timedelta(minutes=spacing_minutes * index)).astimezone(UTC)

    def _execution_reminder_exists(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        scheduled_for: datetime,
    ) -> bool:
        stmt = select(Reminder.id).where(
            Reminder.user_id == user_id,
            Reminder.task_id == task_id,
            Reminder.reminder_type == "execution",
            Reminder.source == "worker",
            Reminder.scheduled_for == scheduled_for,
        )
        return db.scalars(stmt).first() is not None


reminder_service = ReminderService()
