from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.enums import GoalStatus, TaskStatus, ValueLevel
from app.models.goal import Goal
from app.models.report import DailyReport
from app.models.task import Task
from app.models.user import User, UserSettings
from app.services.data_source_service import data_source_service
from app.services.errors import NotFoundError
from app.services.reminder_service import reminder_service
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
        week_focus_minutes = report_service.focus_minutes_between(
            db,
            user_id=user_id,
            start_at=week_start_at,
            end_at=week_end_exclusive,
        )
        active_goal_count = self._goal_count(db, user_id=user_id, status=GoalStatus.ACTIVE)
        completed_goal_count = self._goal_count(db, user_id=user_id, status=GoalStatus.COMPLETED)
        active_task_count = self._task_count(db, user_id=user_id, statuses={TaskStatus.ACTIVE, TaskStatus.IN_FOCUS})
        postponed_task_count = self._task_count(db, user_id=user_id, statuses={TaskStatus.POSTPONED})
        completed_task_count = self._task_count(db, user_id=user_id, statuses={TaskStatus.COMPLETED})
        data_source_summary = data_source_service.sync_summary(db, user_id=user_id)
        reminder_summary = reminder_service.reminder_summary(db, user_id=user_id, now=datetime.now(UTC))

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
                "focus_minutes": week_focus_minutes,
            },
            "goals": {
                "active_goal_count": active_goal_count,
                "completed_goal_count": completed_goal_count,
            },
            "tasks": {
                "active_task_count": active_task_count,
                "postponed_task_count": postponed_task_count,
                "completed_task_count": completed_task_count,
            },
            "reports": {
                "daily_report_available": daily_report is not None,
                "daily_report_id": daily_report.id if daily_report else None,
            },
            "data_sources": {
                "connected_count": data_source_summary["connected_count"],
                "sync_enabled_count": data_source_summary["sync_enabled_count"],
                "attention_count": data_source_summary["attention_count"],
            },
            "reminders": {
                "pending_count": reminder_summary["pending_count"],
                "unseen_count": reminder_summary["unseen_count"],
                "due_count": reminder_summary["due_count"],
            },
            "insights": self._insights_overview(
                completion_rate=metrics.completion_rate,
                planned_task_count=metrics.planned_task_count,
                week_focus_minutes=week_focus_minutes,
                active_goal_count=active_goal_count,
                postponed_task_count=postponed_task_count,
                overdue_task_count=self._overdue_task_count(db, user_id=user_id, today=resolved_today),
                high_value_active_task_count=self._high_value_active_task_count(db, user_id=user_id),
            ),
            "settings": {
                "notification_enabled": settings.notification_enabled if settings else True,
                "focus_mode_default_minutes": settings.focus_mode_default_minutes if settings else 25,
                "reminder_execution_enabled": settings.reminder_execution_enabled if settings else True,
                "reminder_deadline_enabled": settings.reminder_deadline_enabled if settings else True,
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

    def _overdue_task_count(self, db: Session, *, user_id: uuid.UUID, today: date) -> int:
        stmt = select(Task.id).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED]),
            Task.deadline < today,
        )
        return len(list(db.scalars(stmt).all()))

    def _high_value_active_task_count(self, db: Session, *, user_id: uuid.UUID) -> int:
        stmt = select(Task.id).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED]),
            Task.value_level == ValueLevel.HIGH,
        )
        return len(list(db.scalars(stmt).all()))

    def _insights_overview(
        self,
        *,
        completion_rate: float,
        planned_task_count: int,
        week_focus_minutes: int,
        active_goal_count: int,
        postponed_task_count: int,
        overdue_task_count: int,
        high_value_active_task_count: int,
    ) -> dict:
        highlights: list[dict] = []
        if planned_task_count == 0:
            highlights.append(
                {
                    "key": "no_plan_yet",
                    "title": "No plan yet",
                    "message": "Capture one clear task to let Today build a starting sequence.",
                    "signal": "neutral",
                }
            )
        elif completion_rate >= 0.8:
            highlights.append(
                {
                    "key": "strong_today",
                    "title": "Strong execution today",
                    "message": "Most planned work is complete. A short report can help close the loop.",
                    "signal": "positive",
                }
            )
        elif completion_rate == 0:
            highlights.append(
                {
                    "key": "start_needed",
                    "title": "Start signal",
                    "message": "Today has a plan, but no completed task yet. Start with the first protected item.",
                    "signal": "neutral",
                }
            )

        if overdue_task_count:
            highlights.append(
                {
                    "key": "overdue_tasks",
                    "title": "Overdue work exists",
                    "message": f"{overdue_task_count} tasks are overdue. Re-check whether they still matter.",
                    "signal": "risk",
                }
            )
        if postponed_task_count:
            highlights.append(
                {
                    "key": "postponed_tasks",
                    "title": "Postponed tasks are building up",
                    "message": f"{postponed_task_count} tasks are postponed. Keep only the ones that still support a goal.",
                    "signal": "risk",
                }
            )
        if week_focus_minutes:
            highlights.append(
                {
                    "key": "weekly_focus",
                    "title": "Focus is accumulating",
                    "message": f"{week_focus_minutes} minutes of Focus are recorded this week.",
                    "signal": "positive",
                }
            )
        if high_value_active_task_count and active_goal_count:
            highlights.append(
                {
                    "key": "high_value_backlog",
                    "title": "High-value work remains",
                    "message": f"{high_value_active_task_count} high-value tasks are still active across goals.",
                    "signal": "neutral",
                }
            )

        suggested_next_view = "insights_detail" if highlights else "today"
        return {
            "highlights": highlights[:4],
            "suggested_next_view": suggested_next_view,
            "detail_available": True,
        }

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
