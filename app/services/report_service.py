from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.activity_event import ActivityEvent
from app.models.daily_plan import DailyPlan, DailyPlanItem
from app.models.enums import (
    ActorType,
    DailyPlanItemSection,
    DailyPlanItemStatus,
    DailyPlanStatus,
    EntityType,
    FocusSessionStatus,
    GoalStatus,
    TaskStatus,
    ValueLevel,
)
from app.models.focus_session import FocusSession
from app.models.goal import Goal
from app.models.report import DailyReport
from app.models.task import Task
from app.models.user import User
from app.services.activity_event_service import activity_event_service
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class DailyReportMetrics:
    report_date: date
    daily_plan_id: uuid.UUID | None
    generated_from_plan_version: int | None
    completed_task_count: int
    postponed_task_count: int
    interrupted_count: int
    focus_minutes: int
    completion_rate: float
    planned_task_count: int


class ReportService:
    def resolve_report_date(self, db: Session, *, user_id: uuid.UUID, report_date: date | None) -> date:
        return self._resolve_report_date(db, user_id=user_id, report_date=report_date)

    def date_bounds(self, db: Session, *, user_id: uuid.UUID, target_date: date) -> tuple[datetime, datetime]:
        return self._date_bounds(db, user_id=user_id, target_date=target_date)

    def focus_minutes_between(self, db: Session, *, user_id: uuid.UUID, start_at: datetime, end_at: datetime) -> int:
        return self._focus_minutes(db, user_id=user_id, start_at=start_at, end_at=end_at)

    def user_timezone(self, db: Session, *, user_id: uuid.UUID) -> ZoneInfo:
        return self._timezone_for(self._get_user(db, user_id=user_id))

    def get_weekly_report(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        week_start: date | None = None,
    ) -> dict:
        resolved_week_start = self._resolve_week_start(db, user_id=user_id, week_start=week_start)
        week_end = resolved_week_start + timedelta(days=6)
        start_at, _ = self._date_bounds(db, user_id=user_id, target_date=resolved_week_start)
        _, end_at = self._date_bounds(db, user_id=user_id, target_date=week_end)
        daily_trends = [
            self._weekly_day_trend(db, user_id=user_id, report_date=resolved_week_start + timedelta(days=offset))
            for offset in range(7)
        ]
        summary = self._weekly_summary(
            db,
            user_id=user_id,
            week_end=week_end,
            start_at=start_at,
            end_at=end_at,
            daily_trends=daily_trends,
        )
        return {
            "week_start": resolved_week_start,
            "week_end": week_end,
            "summary": summary,
            "daily_trends": daily_trends,
            "focus": self._weekly_focus(daily_trends),
            "lagging_tasks": self._lagging_tasks(
                db,
                user_id=user_id,
                as_of_date=self._weekly_as_of_date(db, user_id=user_id, week_end=week_end),
                limit=5,
            ),
            "ai_suggestions": self._weekly_suggestions(summary),
        }

    def get_or_generate_daily_report(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        report_date: date | None = None,
    ) -> DailyReport:
        resolved_date = self._resolve_report_date(db, user_id=user_id, report_date=report_date)
        report = self._get_daily_report(db, user_id=user_id, report_date=resolved_date)
        if report is not None:
            return report
        return self.generate_daily_report(db, user_id=user_id, report_date=resolved_date)

    def generate_daily_report(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        report_date: date | None = None,
    ) -> DailyReport:
        metrics = self.daily_metrics(db, user_id=user_id, report_date=report_date)
        summary, suggestions = self._report_copy(metrics)
        report = self._get_daily_report(db, user_id=user_id, report_date=metrics.report_date)
        if report is None:
            report = DailyReport(
                user_id=user_id,
                report_date=metrics.report_date,
                ai_summary=summary,
                ai_suggestions=suggestions,
            )
            db.add(report)
            db.flush()
        report.daily_plan_id = metrics.daily_plan_id
        report.completed_task_count = metrics.completed_task_count
        report.postponed_task_count = metrics.postponed_task_count
        report.interrupted_count = metrics.interrupted_count
        report.focus_minutes = metrics.focus_minutes
        report.completion_rate = metrics.completion_rate
        report.ai_summary = summary
        report.ai_suggestions = suggestions
        report.generated_from_plan_version = metrics.generated_from_plan_version
        report.refreshed_at = datetime.now(UTC)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.REPORT,
            entity_id=report.id,
            event_type="DAILY_REPORT_GENERATED",
            actor_type=ActorType.SYSTEM,
            related_daily_plan_id=metrics.daily_plan_id,
            payload={
                "report_date": metrics.report_date.isoformat(),
                "completed_task_count": metrics.completed_task_count,
                "focus_minutes": metrics.focus_minutes,
                "generated_from_plan_version": metrics.generated_from_plan_version,
            },
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if self._is_daily_report_unique_violation(exc):
                existing_report = self._get_daily_report(db, user_id=user_id, report_date=metrics.report_date)
                if existing_report is not None:
                    return existing_report
            raise
        db.refresh(report)
        return report

    def daily_metrics(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        report_date: date | None = None,
    ) -> DailyReportMetrics:
        resolved_date = self._resolve_report_date(db, user_id=user_id, report_date=report_date)
        start_at, end_at = self._date_bounds(db, user_id=user_id, target_date=resolved_date)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=resolved_date)
        planned_task_count, plan_completed_count, completion_rate = self._plan_progress(db, plan=plan)
        completed_task_count = self._distinct_task_event_count(
            db,
            user_id=user_id,
            event_type="TASK_COMPLETED",
            start_at=start_at,
            end_at=end_at,
        )
        if completed_task_count == 0 and plan_completed_count:
            completed_task_count = plan_completed_count

        return DailyReportMetrics(
            report_date=resolved_date,
            daily_plan_id=plan.id if plan else None,
            generated_from_plan_version=plan.current_version if plan else None,
            completed_task_count=completed_task_count,
            postponed_task_count=self._distinct_task_event_count(
                db,
                user_id=user_id,
                event_type="TASK_POSTPONED",
                start_at=start_at,
                end_at=end_at,
            ),
            interrupted_count=self._focus_session_count(
                db,
                user_id=user_id,
                status=FocusSessionStatus.INTERRUPTED,
                start_at=start_at,
                end_at=end_at,
            ),
            focus_minutes=self._focus_minutes(db, user_id=user_id, start_at=start_at, end_at=end_at),
            completion_rate=completion_rate,
            planned_task_count=planned_task_count,
        )

    def _get_daily_report(self, db: Session, *, user_id: uuid.UUID, report_date: date) -> DailyReport | None:
        stmt = select(DailyReport).where(
            DailyReport.user_id == user_id,
            DailyReport.report_date == report_date,
        )
        return db.scalars(stmt).first()

    def _is_daily_report_unique_violation(self, exc: IntegrityError) -> bool:
        diag = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        if constraint_name == "uq_daily_reports_user_date":
            return True
        message = str(exc.orig)
        return "uq_daily_reports_user_date" in message or "UNIQUE constraint failed: daily_reports.user_id, daily_reports.report_date" in message

    def _get_active_plan(self, db: Session, *, user_id: uuid.UUID, plan_date: date) -> DailyPlan | None:
        stmt = select(DailyPlan).where(
            DailyPlan.user_id == user_id,
            DailyPlan.plan_date == plan_date,
            DailyPlan.status == DailyPlanStatus.ACTIVE,
        )
        return db.scalars(stmt).first()

    def _plan_progress(self, db: Session, *, plan: DailyPlan | None) -> tuple[int, int, float]:
        if plan is None or plan.current_revision_id is None:
            return 0, 0, 0.0
        stmt = select(DailyPlanItem).where(
            DailyPlanItem.daily_plan_id == plan.id,
            DailyPlanItem.plan_revision_id == plan.current_revision_id,
            DailyPlanItem.section != DailyPlanItemSection.ROLLED_OVER,
        )
        items = list(db.scalars(stmt).all())
        total_count = len(items)
        completed_count = len([item for item in items if item.status == DailyPlanItemStatus.COMPLETED])
        completion_rate = round(completed_count / total_count, 2) if total_count else 0.0
        return total_count, completed_count, completion_rate

    def _distinct_task_event_count(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        event_type: str,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        stmt = select(func.count(distinct(ActivityEvent.related_task_id))).where(
            ActivityEvent.user_id == user_id,
            ActivityEvent.event_type == event_type,
            ActivityEvent.related_task_id.is_not(None),
            ActivityEvent.occurred_at >= start_at,
            ActivityEvent.occurred_at < end_at,
        )
        return int(db.scalar(stmt) or 0)

    def _focus_session_count(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        status: FocusSessionStatus,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        stmt = select(func.count(FocusSession.id)).where(
            FocusSession.user_id == user_id,
            FocusSession.status == status,
            FocusSession.ended_at >= start_at,
            FocusSession.ended_at < end_at,
        )
        return int(db.scalar(stmt) or 0)

    def _focus_minutes(self, db: Session, *, user_id: uuid.UUID, start_at: datetime, end_at: datetime) -> int:
        stmt = select(func.coalesce(func.sum(FocusSession.actual_duration_min), 0)).where(
            FocusSession.user_id == user_id,
            FocusSession.status.in_(
                [
                    FocusSessionStatus.COMPLETED,
                    FocusSessionStatus.INTERRUPTED,
                    FocusSessionStatus.POSTPONED,
                ]
            ),
            FocusSession.ended_at >= start_at,
            FocusSession.ended_at < end_at,
        )
        return int(db.scalar(stmt) or 0)

    def _weekly_day_trend(self, db: Session, *, user_id: uuid.UUID, report_date: date) -> dict:
        metrics = self.daily_metrics(db, user_id=user_id, report_date=report_date)
        start_at, end_at = self._date_bounds(db, user_id=user_id, target_date=report_date)
        return {
            "report_date": report_date,
            "planned_task_count": metrics.planned_task_count,
            "completed_task_count": metrics.completed_task_count,
            "postponed_task_count": metrics.postponed_task_count,
            "interrupted_count": metrics.interrupted_count,
            "focus_minutes": metrics.focus_minutes,
            "completion_rate": metrics.completion_rate,
            "high_value_completed_task_count": self._completed_task_count_by_value(
                db,
                user_id=user_id,
                value_level=ValueLevel.HIGH,
                start_at=start_at,
                end_at=end_at,
            ),
        }

    def _weekly_summary(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        week_end: date,
        start_at: datetime,
        end_at: datetime,
        daily_trends: list[dict],
    ) -> dict:
        planned_rates = [day["completion_rate"] for day in daily_trends if day["planned_task_count"] > 0]
        as_of_date = self._weekly_as_of_date(db, user_id=user_id, week_end=week_end)
        return {
            "total_planned_task_count": sum(day["planned_task_count"] for day in daily_trends),
            "total_completed_task_count": sum(day["completed_task_count"] for day in daily_trends),
            "total_postponed_task_count": sum(day["postponed_task_count"] for day in daily_trends),
            "total_interrupted_count": sum(day["interrupted_count"] for day in daily_trends),
            "total_focus_minutes": sum(day["focus_minutes"] for day in daily_trends),
            "average_completion_rate": round(sum(planned_rates) / len(planned_rates), 2) if planned_rates else 0.0,
            "high_value_completed_task_count": self._completed_task_count_by_value(
                db,
                user_id=user_id,
                value_level=ValueLevel.HIGH,
                start_at=start_at,
                end_at=end_at,
            ),
            "active_goal_count": self._active_goal_count(db, user_id=user_id),
            "at_risk_goal_count": self._at_risk_goal_count(db, user_id=user_id, week_end=week_end),
            "overdue_task_count": self._overdue_task_count(db, user_id=user_id, as_of_date=as_of_date),
        }

    def _weekly_focus(self, daily_trends: list[dict]) -> dict:
        total_minutes = sum(day["focus_minutes"] for day in daily_trends)
        active_days = [day for day in daily_trends if day["focus_minutes"] > 0]
        best_day = max(daily_trends, key=lambda day: day["focus_minutes"], default=None)
        return {
            "total_minutes": total_minutes,
            "average_minutes_per_active_day": round(total_minutes / len(active_days)) if active_days else 0,
            "best_focus_date": best_day["report_date"] if best_day and best_day["focus_minutes"] > 0 else None,
            "best_focus_minutes": best_day["focus_minutes"] if best_day else 0,
        }

    def _completed_task_count_by_value(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        value_level: ValueLevel,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        stmt = (
            select(func.count(distinct(ActivityEvent.related_task_id)))
            .join(Task, Task.id == ActivityEvent.related_task_id)
            .where(
                ActivityEvent.user_id == user_id,
                ActivityEvent.event_type == "TASK_COMPLETED",
                ActivityEvent.related_task_id.is_not(None),
                ActivityEvent.occurred_at >= start_at,
                ActivityEvent.occurred_at < end_at,
                Task.user_id == user_id,
                Task.value_level == value_level,
            )
        )
        return int(db.scalar(stmt) or 0)

    def _active_goal_count(self, db: Session, *, user_id: uuid.UUID) -> int:
        stmt = select(func.count(Goal.id)).where(
            Goal.user_id == user_id,
            Goal.status == GoalStatus.ACTIVE,
        )
        return int(db.scalar(stmt) or 0)

    def _at_risk_goal_count(self, db: Session, *, user_id: uuid.UUID, week_end: date) -> int:
        active_goals = self._active_goals_with_tasks(db, user_id=user_id)
        at_risk_count = 0
        for goal in active_goals:
            unfinished_tasks = [
                task for task in goal.tasks if task.status not in {TaskStatus.COMPLETED, TaskStatus.ARCHIVED}
            ]
            if goal.deadline is not None and goal.deadline <= week_end and unfinished_tasks:
                at_risk_count += 1
        return at_risk_count

    def _active_goals_with_tasks(self, db: Session, *, user_id: uuid.UUID) -> list[Goal]:
        stmt = (
            select(Goal)
            .options(selectinload(Goal.tasks))
            .where(
                Goal.user_id == user_id,
                Goal.status == GoalStatus.ACTIVE,
            )
            .order_by(Goal.deadline.is_(None), Goal.deadline, Goal.created_at)
        )
        return list(db.scalars(stmt).all())

    def _overdue_task_count(self, db: Session, *, user_id: uuid.UUID, as_of_date: date) -> int:
        stmt = select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.deadline.is_not(None),
            Task.deadline < as_of_date,
            Task.status.in_([TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED]),
        )
        return int(db.scalar(stmt) or 0)

    def _lagging_tasks(self, db: Session, *, user_id: uuid.UUID, as_of_date: date, limit: int) -> list[dict]:
        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.deadline.is_not(None),
                Task.deadline < as_of_date,
                Task.status.in_([TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED]),
            )
            .order_by(
                case(
                    (Task.value_level == ValueLevel.HIGH, 0),
                    (Task.value_level == ValueLevel.MEDIUM, 1),
                    else_=2,
                ),
                Task.deadline,
                Task.priority,
                Task.created_at,
            )
            .limit(limit)
        )
        tasks = list(db.scalars(stmt).all())
        return [
            {
                "id": task.id,
                "title": task.title,
                "goal_id": task.goal_id,
                "deadline": task.deadline,
                "days_overdue": (as_of_date - task.deadline).days if task.deadline else 0,
                "value_level": task.value_level,
                "priority": task.priority,
                "reason": self._lagging_task_reason(task, as_of_date=as_of_date),
            }
            for task in tasks
        ]

    def _lagging_task_reason(self, task: Task, *, as_of_date: date) -> str:
        days_overdue = (as_of_date - task.deadline).days if task.deadline else 0
        if task.value_level == ValueLevel.HIGH:
            return f"高价值任务已滞后 {days_overdue} 天，下次安排时需要优先保护。"
        return f"任务已滞后 {days_overdue} 天，需要重新判断是否继续推进。"

    def _weekly_suggestions(self, summary: dict) -> list[str]:
        suggestions: list[str] = []
        if summary["high_value_completed_task_count"] == 0 and summary["total_completed_task_count"] > 0:
            suggestions.append("下周先保护一个高价值任务，避免只完成轻任务。")
        if summary["overdue_task_count"]:
            suggestions.append("先重新判断滞后任务是否仍重要，重要的保留，不重要的后移或归档。")
        if summary["total_interrupted_count"]:
            suggestions.append("把容易中断的任务拆成更短的 Focus 步骤。")
        if not suggestions:
            suggestions.append("保持轻量节奏，下周仍然从 Today 推荐序列的第一项开始。")
        return suggestions[:3]

    def _weekly_as_of_date(self, db: Session, *, user_id: uuid.UUID, week_end: date) -> date:
        today = self._resolve_report_date(db, user_id=user_id, report_date=None)
        return min(today, week_end + timedelta(days=1))

    def _resolve_week_start(self, db: Session, *, user_id: uuid.UUID, week_start: date | None) -> date:
        anchor_date = week_start or self._resolve_report_date(db, user_id=user_id, report_date=None)
        return anchor_date - timedelta(days=anchor_date.weekday())

    def _report_copy(self, metrics: DailyReportMetrics) -> tuple[str, list[str]]:
        if metrics.planned_task_count == 0 and metrics.focus_minutes == 0:
            return (
                "今天还没有形成可复盘的执行数据。",
                ["明天先从一个清晰的小任务开始，让 Today 有一个稳定入口。"],
            )
        if metrics.completion_rate >= 1:
            return (
                "今天的执行闭环很完整，高价值行动得到了保护。",
                ["保持这个节奏，明天仍然先从最重要的一件事开始。"],
            )
        if metrics.interrupted_count:
            return (
                "今天有专注记录，也出现了中断，节奏需要更轻一点。",
                ["把容易中断的任务拆成 25 分钟以内的小步骤。"],
            )
        if metrics.postponed_task_count:
            return (
                "今天有任务被延后，明天需要重新确认它们是否仍然重要。",
                ["先处理仍有价值的延后任务，低价值任务可以继续后移。"],
            )
        return (
            "今天已经有清晰进展，下一步是让节奏更稳定。",
            ["明天继续从 Today 推荐序列里的第一个任务开始。"],
        )

    def _resolve_report_date(self, db: Session, *, user_id: uuid.UUID, report_date: date | None) -> date:
        if report_date is not None:
            return report_date
        user = self._get_user(db, user_id=user_id)
        return datetime.now(self._timezone_for(user)).date()

    def _date_bounds(self, db: Session, *, user_id: uuid.UUID, target_date: date) -> tuple[datetime, datetime]:
        user = self._get_user(db, user_id=user_id)
        timezone = self._timezone_for(user)
        start_at = datetime.combine(target_date, time.min, tzinfo=timezone).astimezone(UTC)
        end_at = (datetime.combine(target_date, time.min, tzinfo=timezone) + timedelta(days=1)).astimezone(UTC)
        return start_at, end_at

    def _get_user(self, db: Session, *, user_id: uuid.UUID) -> User:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _timezone_for(self, user: User) -> ZoneInfo:
        try:
            return ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")


report_service = ReportService()
