from __future__ import annotations

from datetime import UTC, date, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.enums import GoalStatus, TaskStatus
from app.models.goal import Goal
from app.models.report import DailyReport
from app.models.task import Task
from app.models.user import User, UserSettings
from app.services.errors import NotFoundError
from app.services.report_service import report_service


class MeService:
    def get_overview(self, db: Session, *, user_id: uuid.UUID, today: date | None = None) -> dict:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        resolved_today = report_service.resolve_report_date(db, user_id=user_id, report_date=today)
        metrics = report_service.daily_metrics(db, user_id=user_id, report_date=resolved_today)
        week_start = resolved_today - timedelta(days=resolved_today.weekday())
        week_end = week_start + timedelta(days=6)
        week_start_at, _ = report_service.date_bounds(db, user_id=user_id, target_date=week_start)
        _, week_end_exclusive = report_service.date_bounds(db, user_id=user_id, target_date=week_end)
        daily_report = self._daily_report(db, user_id=user_id, report_date=resolved_today)
        settings = self._settings_for(db, user_id=user_id)
        timezone = report_service.user_timezone(db, user_id=user_id)

        return {
            "profile": {
                "user_id": user.id,
                "name": user.name,
                "timezone": user.timezone,
                "current_streak_days": self._current_streak_days(
                    db,
                    user_id=user_id,
                    today=resolved_today,
                    timezone=timezone,
                ),
            },
            "today": {
                "date": resolved_today,
                "completed_task_count": metrics.completed_task_count,
                "planned_task_count": metrics.planned_task_count,
                "completion_rate": metrics.completion_rate,
                "focus_minutes": metrics.focus_minutes,
            },
            "week": {
                "week_start": week_start,
                "week_end": week_end,
                "focus_minutes": report_service.focus_minutes_between(
                    db,
                    user_id=user_id,
                    start_at=week_start_at,
                    end_at=week_end_exclusive,
                ),
            },
            "goals": {
                "active_goal_count": self._goal_count(db, user_id=user_id, status=GoalStatus.ACTIVE),
                "completed_goal_count": self._goal_count(db, user_id=user_id, status=GoalStatus.COMPLETED),
            },
            "tasks": {
                "active_task_count": self._task_count(db, user_id=user_id, statuses={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS}),
                "postponed_task_count": self._task_count(db, user_id=user_id, statuses={TaskStatus.POSTPONED}),
                "completed_task_count": self._task_count(db, user_id=user_id, statuses={TaskStatus.COMPLETED}),
            },
            "reports": {
                "daily_report_available": daily_report is not None,
                "daily_report_id": daily_report.id if daily_report else None,
            },
            "settings": {
                "notification_enabled": settings.notification_enabled if settings else True,
                "focus_mode_default_minutes": settings.focus_mode_default_minutes if settings else 25,
            },
        }

    def _daily_report(self, db: Session, *, user_id: uuid.UUID, report_date: date) -> DailyReport | None:
        stmt = select(DailyReport).where(
            DailyReport.user_id == user_id,
            DailyReport.report_date == report_date,
        )
        return db.scalars(stmt).first()

    def _settings_for(self, db: Session, *, user_id: uuid.UUID) -> UserSettings | None:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        return db.scalars(stmt).first()

    def _goal_count(self, db: Session, *, user_id: uuid.UUID, status: GoalStatus) -> int:
        stmt = select(Goal.id).where(Goal.user_id == user_id, Goal.status == status)
        return len(list(db.scalars(stmt).all()))

    def _task_count(self, db: Session, *, user_id: uuid.UUID, statuses: set[TaskStatus]) -> int:
        stmt = select(Task.id).where(Task.user_id == user_id, Task.status.in_(statuses))
        return len(list(db.scalars(stmt).all()))

    def _current_streak_days(self, db: Session, *, user_id: uuid.UUID, today: date, timezone) -> int:
        stmt = (
            select(ActivityEvent.occurred_at)
            .where(ActivityEvent.user_id == user_id)
            .order_by(ActivityEvent.occurred_at.desc())
            .limit(200)
        )
        active_dates = set()
        for occurred_at in db.scalars(stmt).all():
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            active_dates.add(occurred_at.astimezone(timezone).date())
        streak = 0
        cursor = today
        while cursor in active_dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak


me_service = MeService()
