from __future__ import annotations

from datetime import date, datetime
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import EntityType, GoalStatus, TaskStatus, ValueLevel
from app.models.goal import Goal
from app.models.task import Task
from app.models.user import User
from app.services.activity_event_service import activity_event_service
from app.services.errors import NotFoundError


class GoalService:
    def create_goal(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        title: str,
        description: str | None = None,
        deadline: date | None = None,
        value_level: ValueLevel = ValueLevel.MEDIUM,
        commit: bool = True,
    ) -> Goal:
        goal = Goal(
            user_id=user_id,
            title=title,
            description=description,
            deadline=deadline,
            value_level=value_level,
            status=GoalStatus.ACTIVE,
        )
        db.add(goal)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.GOAL,
            entity_id=goal.id,
            event_type="GOAL_CREATED",
            payload={"title": title, "value_level": value_level.value},
        )
        if commit:
            db.commit()
            db.refresh(goal)
        return goal

    def list_goals(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Goal]:
        stmt = (
            select(Goal)
            .where(Goal.user_id == user_id)
            .order_by(Goal.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(stmt).all())

    def get_goal(self, db: Session, *, goal_id: uuid.UUID, user_id: uuid.UUID) -> Goal:
        goal = db.get(Goal, goal_id)
        if goal is None or goal.user_id != user_id:
            raise NotFoundError("Goal not found")
        return goal

    def get_goal_detail(self, db: Session, *, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        goal = self.get_goal(db, goal_id=goal_id, user_id=user_id)
        today = self._current_user_date(db, user_id=user_id)
        tasks = self._goal_tasks(db, goal=goal, user_id=user_id)
        visible_tasks = [task for task in tasks if task.status != TaskStatus.ARCHIVED]
        sorted_tasks = sorted(visible_tasks, key=lambda task: self._task_sort_key(task, today=today))
        unfinished_tasks = [task for task in sorted_tasks if task.status != TaskStatus.COMPLETED]
        completed_tasks = [task for task in sorted_tasks if task.status == TaskStatus.COMPLETED]
        recommended_next_task = unfinished_tasks[0] if goal.status == GoalStatus.ACTIVE and unfinished_tasks else None
        task_summaries = {task.id: self._task_summary(task) for task in visible_tasks}

        return {
            "overview": goal,
            "progress": self._progress(goal=goal, tasks=visible_tasks, today=today),
            "task_list": {
                "unfinished_tasks": [task_summaries[task.id] for task in unfinished_tasks],
                "completed_tasks": [task_summaries[task.id] for task in completed_tasks],
                "recommended_next_task": task_summaries[recommended_next_task.id] if recommended_next_task else None,
            },
            "dependency_map": self._dependency_map(sorted_tasks),
            "ai_suggestion": self._ai_suggestion(
                goal=goal,
                tasks=visible_tasks,
                recommended_next_task=recommended_next_task,
                today=today,
            ),
            "actions": {
                "can_add_task": goal.status == GoalStatus.ACTIVE,
                "can_edit_goal": goal.status != GoalStatus.ARCHIVED,
                "can_mark_complete": (
                    goal.status == GoalStatus.ACTIVE
                    and bool(visible_tasks)
                    and len(completed_tasks) == len(visible_tasks)
                ),
            },
        }

    def update_goal(
        self,
        db: Session,
        *,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        updates: dict,
    ) -> Goal:
        goal = self.get_goal(db, goal_id=goal_id, user_id=user_id)
        changed_fields: list[str] = []

        for field in ("title", "description", "deadline", "value_level", "status"):
            if field in updates:
                setattr(goal, field, updates[field])
                changed_fields.append(field)

        if changed_fields:
            activity_event_service.add_event(
                db,
                user_id=user_id,
                entity_type=EntityType.GOAL,
                entity_id=goal.id,
                event_type="GOAL_UPDATED",
                payload={"changed_fields": changed_fields},
            )

        db.commit()
        db.refresh(goal)
        return goal

    def _goal_tasks(self, db: Session, *, goal: Goal, user_id: uuid.UUID) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.steps))
            .where(Task.goal_id == goal.id, Task.user_id == user_id)
        )
        return list(db.scalars(stmt).all())

    def _progress(self, *, goal: Goal, tasks: list[Task], today: date) -> dict:
        total_task_count = len(tasks)
        completed_task_count = len([task for task in tasks if task.status == TaskStatus.COMPLETED])
        unfinished_task_count = total_task_count - completed_task_count
        postponed_task_count = len([task for task in tasks if task.status == TaskStatus.POSTPONED])
        completion_rate = round(completed_task_count / total_task_count, 2) if total_task_count else 0.0
        total_estimated_duration_min = sum(task.estimated_duration_min or 0 for task in tasks)
        total_actual_duration_min = sum(task.actual_duration_min for task in tasks)
        risk_level, risk_reason = self._risk_for(
            goal=goal,
            today=today,
            total_task_count=total_task_count,
            unfinished_task_count=unfinished_task_count,
            completion_rate=completion_rate,
        )
        return {
            "total_task_count": total_task_count,
            "unfinished_task_count": unfinished_task_count,
            "completed_task_count": completed_task_count,
            "postponed_task_count": postponed_task_count,
            "completion_rate": completion_rate,
            "total_estimated_duration_min": total_estimated_duration_min,
            "total_actual_duration_min": total_actual_duration_min,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
        }

    def _risk_for(
        self,
        *,
        goal: Goal,
        today: date,
        total_task_count: int,
        unfinished_task_count: int,
        completion_rate: float,
    ) -> tuple[str, str]:
        if goal.status == GoalStatus.COMPLETED:
            return "completed", "Goal is already completed."
        if total_task_count == 0:
            return "needs_breakdown", "No tasks are linked to this goal yet."
        if unfinished_task_count == 0:
            return "on_track", "All linked tasks are completed."
        if goal.deadline is None:
            return "on_track", "No deadline pressure is detected."
        days_left = (goal.deadline - today).days
        if days_left < 0:
            return "behind", "Goal deadline has passed while tasks remain unfinished."
        if days_left <= 3 and completion_rate < 0.8:
            return "at_risk", "Goal is close to its deadline and still has unfinished tasks."
        return "on_track", "Goal has a clear next task and no urgent deadline risk."

    def _task_summary(self, task: Task) -> dict:
        return {
            "id": task.id,
            "title": task.title,
            "deadline": task.deadline,
            "estimated_duration_min": task.estimated_duration_min,
            "actual_duration_min": task.actual_duration_min,
            "priority": task.priority,
            "value_level": task.value_level,
            "progress": task.progress,
            "status": task.status,
            "step_count": len(task.steps),
            "completed_step_count": len([step for step in task.steps if step.is_completed]),
        }

    def _dependency_map(self, tasks: list[Task]) -> dict:
        return {
            "nodes": [
                {
                    "task_id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "sort_order": index,
                }
                for index, task in enumerate(tasks, start=1)
            ],
            "edges": [],
            "note": "Task dependency edges are not modeled yet; nodes follow the current recommended stage order.",
        }

    def _ai_suggestion(
        self,
        *,
        goal: Goal,
        tasks: list[Task],
        recommended_next_task: Task | None,
        today: date,
    ) -> dict:
        risk_level, risk_reason = self._risk_for(
            goal=goal,
            today=today,
            total_task_count=len(tasks),
            unfinished_task_count=len([task for task in tasks if task.status != TaskStatus.COMPLETED]),
            completion_rate=round(
                len([task for task in tasks if task.status == TaskStatus.COMPLETED]) / len(tasks),
                2,
            )
            if tasks
            else 0.0,
        )
        if goal.status == GoalStatus.COMPLETED:
            return {
                "source": "rule",
                "summary": "This goal is already complete.",
                "next_action_task_id": None,
                "risk_warning": None,
                "suggestions": ["Review the completed outcome or start a new goal when ready."],
            }
        if goal.status == GoalStatus.ARCHIVED:
            return {
                "source": "rule",
                "summary": "This goal is archived.",
                "next_action_task_id": None,
                "risk_warning": None,
                "suggestions": [],
            }
        if not tasks:
            suggestions = ["Add one concrete task so this goal can enter the execution loop."]
            summary = "This goal needs a first executable task."
        elif recommended_next_task is None:
            suggestions = ["Review the goal and mark it complete if the outcome is truly finished."]
            summary = "All linked tasks are complete."
        else:
            suggestions = [f"Start with: {recommended_next_task.title}"]
            if risk_level in {"behind", "at_risk"}:
                suggestions.append("Keep the next task protected in Today before adding lighter work.")
            summary = "A clear next task is available."

        return {
            "source": "rule",
            "summary": summary,
            "next_action_task_id": recommended_next_task.id if recommended_next_task else None,
            "risk_warning": risk_reason if risk_level in {"behind", "at_risk", "needs_breakdown"} else None,
            "suggestions": suggestions,
        }

    def _task_sort_key(self, task: Task, *, today: date) -> tuple[int, date, int, int, int]:
        status_rank = {
            TaskStatus.IN_FOCUS: 0,
            TaskStatus.ACTIVE: 1,
            TaskStatus.POSTPONED: 2,
            TaskStatus.COMPLETED: 3,
            TaskStatus.ARCHIVED: 4,
        }
        value_rank = {ValueLevel.HIGH: 0, ValueLevel.MEDIUM: 1, ValueLevel.LOW: 2}
        deadline = task.deadline or date.max
        overdue_rank = 0 if task.deadline is not None and task.deadline <= today else 1
        return (
            status_rank[task.status],
            deadline,
            overdue_rank,
            task.priority,
            value_rank[task.value_level],
        )

    def _current_user_date(self, db: Session, *, user_id: uuid.UUID) -> date:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        try:
            timezone = ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        return datetime.now(timezone).date()


goal_service = GoalService()
