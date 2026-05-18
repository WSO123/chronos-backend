from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.activity_event import ActivityEvent
from app.models.enums import TaskStatus, ValueLevel
from app.models.goal import Goal
from app.models.task import Task
from app.models.user import User


class GoalProgressFeedbackService:
    progress_event_types = {
        "TASK_COMPLETED",
        "TASK_PARTIAL_PROGRESS_RECORDED",
        "TASK_POSTPONED",
    }

    def build_task_feedback(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        impact_type: str,
        task_progress_delta: Decimal | float,
        focus_minutes: int = 0,
    ) -> dict | None:
        task = self._task_with_goal(db, user_id=user_id, task_id=task_id)
        if task is None or task.goal_id is None or task.goal is None:
            return None
        goal_tasks = self._goal_tasks(db, user_id=user_id, goal_id=task.goal_id)
        return self._task_feedback(
            task=task,
            goal=task.goal,
            goal_tasks=goal_tasks,
            impact_type=impact_type,
            task_progress_delta=float(task_progress_delta or 0),
            focus_minutes=focus_minutes,
        )

    def event_payload(self, feedback: dict | None) -> dict:
        if feedback is None:
            return {}
        return {
            "goal_id": str(feedback["goal_id"]),
            "goal_title": feedback["goal_title"],
            "goal_value_level": feedback["goal_value_level"],
            "goal_progress_before": feedback["progress_before"],
            "goal_progress_after": feedback["progress_after"],
            "goal_progress_delta": feedback["progress_delta"],
            "task_progress_delta": feedback["task_progress_delta"],
            "goal_progress_feedback_source": feedback["source"],
        }

    def daily_feedback(self, db: Session, *, user_id: uuid.UUID, report_date: date) -> dict:
        start_at, end_at = self._date_bounds(db, user_id=user_id, target_date=report_date)
        events = list(
            db.scalars(
                select(ActivityEvent)
                .where(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.event_type.in_(self.progress_event_types),
                    ActivityEvent.related_task_id.is_not(None),
                    ActivityEvent.occurred_at >= start_at,
                    ActivityEvent.occurred_at < end_at,
                )
                .order_by(ActivityEvent.occurred_at.asc())
            ).all()
        )
        task_ids = {event.related_task_id for event in events if event.related_task_id is not None}
        task_by_id = self._tasks_by_id(db, user_id=user_id, task_ids=task_ids)
        items_by_goal_id: dict[uuid.UUID, dict] = {}

        for event in events:
            if event.related_task_id is None:
                continue
            task = task_by_id.get(event.related_task_id)
            if task is None or task.goal_id is None or task.goal is None:
                continue
            item = items_by_goal_id.setdefault(
                task.goal_id,
                self._empty_daily_item(goal=task.goal, report_date=report_date),
            )
            payload = event.payload or {}
            progress_delta = float(payload.get("goal_progress_delta") or 0.0)
            focus_minutes = int(payload.get("actual_duration_min_delta") or 0)

            if item["progress_before"] is None:
                item["progress_before"] = float(payload.get("goal_progress_before") or 0.0)
            if "goal_progress_after" in payload:
                item["progress_after"] = float(payload["goal_progress_after"])
            item["progress_delta"] = round(item["progress_delta"] + progress_delta, 2)
            item["focus_minutes"] += focus_minutes
            item["touched_task_ids"].add(task.id)
            if event.event_type == "TASK_COMPLETED":
                item["completed_task_count"] += 1
            elif event.event_type == "TASK_PARTIAL_PROGRESS_RECORDED":
                item["partial_progress_count"] += 1
            elif event.event_type == "TASK_POSTPONED":
                item["postponed_task_count"] += 1

        if not items_by_goal_id:
            return self._empty_daily_feedback(report_date=report_date)

        goal_tasks_by_id = {
            goal_id: self._goal_tasks(db, user_id=user_id, goal_id=goal_id)
            for goal_id in items_by_goal_id
        }
        items = [
            self._daily_item_response(item, goal_tasks=goal_tasks_by_id[item["goal_id"]])
            for item in items_by_goal_id.values()
        ]
        items.sort(
            key=lambda item: (
                0 if item["goal_value_level"] == ValueLevel.HIGH.value else 1,
                -item["progress_delta"],
                item["goal_title"],
            )
        )
        return {
            "report_date": report_date,
            "touched_goal_count": len(items),
            "advanced_goal_count": len([item for item in items if item["progress_delta"] > 0]),
            "high_value_goal_count": len([item for item in items if item["goal_value_level"] == ValueLevel.HIGH.value]),
            "total_progress_delta": round(sum(item["progress_delta"] for item in items), 2),
            "items": items,
            "source": "goal-progress-feedback-v1",
        }

    def goal_feedback_for_date(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        target_date: date,
    ) -> dict | None:
        feedback = self.daily_feedback(db, user_id=user_id, report_date=target_date)
        for item in feedback["items"]:
            if item["goal_id"] == goal_id:
                return item
        return None

    def _task_feedback(
        self,
        *,
        task: Task,
        goal: Goal,
        goal_tasks: list[Task],
        impact_type: str,
        task_progress_delta: float,
        focus_minutes: int,
    ) -> dict:
        total_task_count = len(goal_tasks)
        current_sum = sum(float(goal_task.progress or 0) for goal_task in goal_tasks)
        previous_sum = max(0.0, current_sum - max(0.0, task_progress_delta))
        progress_before = round(previous_sum / total_task_count, 2) if total_task_count else 0.0
        progress_after = round(current_sum / total_task_count, 2) if total_task_count else 0.0
        progress_delta = round(max(0.0, progress_after - progress_before), 2)
        completed_task_count = len([goal_task for goal_task in goal_tasks if goal_task.status == TaskStatus.COMPLETED])
        unfinished_task_count = len(
            [goal_task for goal_task in goal_tasks if goal_task.status not in {TaskStatus.COMPLETED, TaskStatus.ARCHIVED}]
        )
        return {
            "goal_id": goal.id,
            "goal_title": goal.title,
            "goal_value_level": goal.value_level.value,
            "task_id": task.id,
            "task_title": task.title,
            "impact_type": impact_type,
            "progress_before": progress_before,
            "progress_after": progress_after,
            "progress_delta": progress_delta,
            "task_progress_delta": round(max(0.0, task_progress_delta), 2),
            "completed_task_count": completed_task_count,
            "total_task_count": total_task_count,
            "unfinished_task_count": unfinished_task_count,
            "focus_minutes": focus_minutes,
            "message": self._task_feedback_message(
                goal_title=goal.title,
                task_title=task.title,
                impact_type=impact_type,
                progress_delta=progress_delta,
                progress_after=progress_after,
            ),
            "signal": "positive" if progress_delta > 0 else "info",
            "source": "goal-progress-feedback-v1",
        }

    def _empty_daily_item(self, *, goal: Goal, report_date: date) -> dict:
        return {
            "goal_id": goal.id,
            "goal_title": goal.title,
            "goal_value_level": goal.value_level.value,
            "task_id": None,
            "task_title": None,
            "impact_type": "daily_goal_progress",
            "progress_before": None,
            "progress_after": 0.0,
            "progress_delta": 0.0,
            "task_progress_delta": 0.0,
            "completed_task_count": 0,
            "partial_progress_count": 0,
            "postponed_task_count": 0,
            "total_task_count": 0,
            "unfinished_task_count": 0,
            "focus_minutes": 0,
            "message": "",
            "signal": "neutral",
            "source": "goal-progress-feedback-v1",
            "report_date": report_date,
            "touched_task_ids": set(),
        }

    def _daily_item_response(self, item: dict, *, goal_tasks: list[Task]) -> dict:
        total_task_count = len(goal_tasks)
        completed_task_count = len([task for task in goal_tasks if task.status == TaskStatus.COMPLETED])
        unfinished_task_count = len(
            [task for task in goal_tasks if task.status not in {TaskStatus.COMPLETED, TaskStatus.ARCHIVED}]
        )
        progress_after = item["progress_after"]
        if not progress_after and total_task_count:
            progress_after = round(sum(float(task.progress or 0) for task in goal_tasks) / total_task_count, 2)
        progress_before = item["progress_before"]
        if progress_before is None:
            progress_before = max(0.0, progress_after - item["progress_delta"])
        signal = "positive" if item["progress_delta"] > 0 else "watch" if item["postponed_task_count"] else "neutral"
        return {
            "goal_id": item["goal_id"],
            "goal_title": item["goal_title"],
            "goal_value_level": item["goal_value_level"],
            "task_id": None,
            "task_title": None,
            "impact_type": "daily_goal_progress",
            "progress_before": round(progress_before, 2),
            "progress_after": round(progress_after, 2),
            "progress_delta": round(item["progress_delta"], 2),
            "task_progress_delta": round(item["progress_delta"], 2),
            "completed_task_count": completed_task_count,
            "total_task_count": total_task_count,
            "unfinished_task_count": unfinished_task_count,
            "focus_minutes": item["focus_minutes"],
            "message": self._daily_feedback_message(item),
            "signal": signal,
            "source": "goal-progress-feedback-v1",
        }

    def _daily_feedback_message(self, item: dict) -> str:
        if item["progress_delta"] > 0:
            return (
                f"今天让「{item['goal_title']}」前进约 {int(item['progress_delta'] * 100)}%，"
                f"当前完成度约 {int(float(item['progress_after']) * 100)}%。"
            )
        if item["postponed_task_count"]:
            return f"今天触碰了「{item['goal_title']}」，但还没有形成目标进度增长。"
        return f"今天记录了「{item['goal_title']}」的执行反馈。"

    def _task_feedback_message(
        self,
        *,
        goal_title: str,
        task_title: str,
        impact_type: str,
        progress_delta: float,
        progress_after: float,
    ) -> str:
        action = "完成"
        if impact_type == "partial_progress":
            action = "推进"
        if progress_delta <= 0:
            return f"{action}「{task_title}」，但「{goal_title}」的整体完成度暂未变化。"
        return (
            f"{action}「{task_title}」，让「{goal_title}」前进约 {int(progress_delta * 100)}%，"
            f"当前完成度约 {int(progress_after * 100)}%。"
        )

    def _empty_daily_feedback(self, *, report_date: date) -> dict:
        return {
            "report_date": report_date,
            "touched_goal_count": 0,
            "advanced_goal_count": 0,
            "high_value_goal_count": 0,
            "total_progress_delta": 0.0,
            "items": [],
            "source": "goal-progress-feedback-v1",
        }

    def _task_with_goal(self, db: Session, *, user_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        return db.scalars(
            select(Task)
            .options(selectinload(Task.goal))
            .where(Task.user_id == user_id, Task.id == task_id)
        ).first()

    def _tasks_by_id(self, db: Session, *, user_id: uuid.UUID, task_ids: set[uuid.UUID]) -> dict[uuid.UUID, Task]:
        if not task_ids:
            return {}
        tasks = list(
            db.scalars(
                select(Task)
                .options(selectinload(Task.goal))
                .where(Task.user_id == user_id, Task.id.in_(task_ids))
            ).all()
        )
        return {task.id: task for task in tasks}

    def _goal_tasks(self, db: Session, *, user_id: uuid.UUID, goal_id: uuid.UUID) -> list[Task]:
        return list(
            db.scalars(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.goal_id == goal_id,
                    Task.status != TaskStatus.ARCHIVED,
                )
            ).all()
        )

    def _date_bounds(self, db: Session, *, user_id: uuid.UUID, target_date: date) -> tuple[datetime, datetime]:
        timezone = self._timezone_for_user(db, user_id=user_id)
        start = datetime.combine(target_date, time.min, tzinfo=timezone).astimezone(UTC)
        end = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=timezone).astimezone(UTC)
        return start, end

    def _timezone_for_user(self, db: Session, *, user_id: uuid.UUID) -> ZoneInfo:
        user = db.get(User, user_id)
        timezone_name = user.timezone if user is not None else "UTC"
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")


goal_progress_feedback_service = GoalProgressFeedbackService()
