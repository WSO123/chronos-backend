from __future__ import annotations

from datetime import date, datetime, timedelta
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.activity_event import ActivityEvent
from app.models.enums import EntityType, GoalHomeFilter, GoalStatus, TaskStatus, ValueLevel
from app.models.goal import Goal
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.mixins import utc_now
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

    def get_goals_home(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        selected_filter: GoalHomeFilter = GoalHomeFilter.ACTIVE,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        today = self._current_user_date(db, user_id=user_id)
        goals = self._goals_with_tasks(db, user_id=user_id)
        visible_goals = [goal for goal in goals if goal.status != GoalStatus.ARCHIVED]
        home_items = [self._goal_home_item(db, goal, today=today) for goal in visible_goals]
        filtered_items = self._filter_home_items(home_items, selected_filter=selected_filter, today=today)
        paginated_items = filtered_items[offset : offset + limit]

        return {
            "selected_filter": selected_filter,
            "summary": self._home_summary(visible_goals, home_items, today=today),
            "filters": self._home_filter_counts(home_items, today=today),
            "goals": paginated_items,
        }

    def get_goal_detail(self, db: Session, *, goal_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        goal = self.get_goal(db, goal_id=goal_id, user_id=user_id)
        today = self._current_user_date(db, user_id=user_id)
        tasks = self._goal_tasks(db, goal=goal, user_id=user_id)
        visible_tasks = [task for task in tasks if task.status != TaskStatus.ARCHIVED]
        sorted_tasks = sorted(visible_tasks, key=lambda task: self._task_sort_key(task, today=today))
        unfinished_tasks = [task for task in sorted_tasks if task.status != TaskStatus.COMPLETED]
        completed_tasks = [task for task in sorted_tasks if task.status == TaskStatus.COMPLETED]
        recommended_next_task = self._recommended_next_task(db, goal=goal, sorted_tasks=sorted_tasks)
        task_summaries = {task.id: self._task_summary(task) for task in visible_tasks}

        return {
            "overview": goal,
            "progress": self._progress(goal=goal, tasks=visible_tasks, today=today),
            "task_list": {
                "unfinished_tasks": [task_summaries[task.id] for task in unfinished_tasks],
                "completed_tasks": [task_summaries[task.id] for task in completed_tasks],
                "recommended_next_task": task_summaries[recommended_next_task.id] if recommended_next_task else None,
            },
            "dependency_map": self._dependency_map(db, sorted_tasks),
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

    def get_goal_progress_timeline(
        self,
        db: Session,
        *,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 30,
    ) -> dict:
        goal = self.get_goal(db, goal_id=goal_id, user_id=user_id)
        today = self._current_user_date(db, user_id=user_id)
        tasks = self._goal_tasks(db, goal=goal, user_id=user_id)
        visible_tasks = [task for task in tasks if task.status != TaskStatus.ARCHIVED]
        progress = self._progress(goal=goal, tasks=visible_tasks, today=today)
        events = self._goal_timeline_events(db, goal=goal, tasks=visible_tasks, user_id=user_id)
        milestones = self._goal_timeline_milestones(goal=goal, tasks=visible_tasks, events=events, today=today)

        return {
            "goal_id": goal.id,
            "generated_at": utc_now(),
            "summary": {
                "goal_id": goal.id,
                "goal_status": goal.status,
                "deadline": goal.deadline,
                "total_task_count": progress["total_task_count"],
                "completed_task_count": progress["completed_task_count"],
                "completion_rate": progress["completion_rate"],
                "risk_level": progress["risk_level"],
                "risk_reason": progress["risk_reason"],
            },
            "milestones": milestones[:limit],
            "note": "Timeline is derived from goal and task activity events; it does not change Today ordering.",
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

    def _goals_with_tasks(self, db: Session, *, user_id: uuid.UUID) -> list[Goal]:
        stmt = (
            select(Goal)
            .options(selectinload(Goal.tasks).selectinload(Task.steps))
            .where(Goal.user_id == user_id)
            .order_by(Goal.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    def _goal_home_item(self, db: Session, goal: Goal, *, today: date) -> dict:
        visible_tasks = [task for task in goal.tasks if task.status != TaskStatus.ARCHIVED]
        sorted_tasks = sorted(visible_tasks, key=lambda task: self._task_sort_key(task, today=today))
        unfinished_tasks = [task for task in sorted_tasks if task.status != TaskStatus.COMPLETED]
        completed_tasks = [task for task in sorted_tasks if task.status == TaskStatus.COMPLETED]
        recommended_next_task = self._recommended_next_task(db, goal=goal, sorted_tasks=sorted_tasks)
        progress = self._progress(goal=goal, tasks=visible_tasks, today=today)
        return {
            "id": goal.id,
            "title": goal.title,
            "deadline": goal.deadline,
            "value_level": goal.value_level,
            "status": goal.status,
            "progress": progress["completion_rate"],
            "risk_level": progress["risk_level"],
            "risk_reason": progress["risk_reason"],
            "associated_task_count": len(visible_tasks),
            "unfinished_task_count": len(unfinished_tasks),
            "completed_task_count": len(completed_tasks),
            "recommended_next_task_id": recommended_next_task.id if recommended_next_task else None,
        }

    def _recommended_next_task(self, db: Session, *, goal: Goal, sorted_tasks: list[Task]) -> Task | None:
        if goal.status != GoalStatus.ACTIVE:
            return None
        unfinished_tasks = [task for task in sorted_tasks if task.status != TaskStatus.COMPLETED]
        if not unfinished_tasks:
            return None

        blocked_task_ids = self._blocked_task_ids(db, tasks=sorted_tasks)
        for task in unfinished_tasks:
            if task.id not in blocked_task_ids:
                return task
        return unfinished_tasks[0]

    def _blocked_task_ids(self, db: Session, *, tasks: list[Task]) -> set[uuid.UUID]:
        task_by_id = {task.id: task for task in tasks}
        if not task_by_id:
            return set()
        stmt = select(TaskDependency).where(
            TaskDependency.dependent_task_id.in_(task_by_id.keys()),
            TaskDependency.prerequisite_task_id.in_(task_by_id.keys()),
        )
        edges = list(db.scalars(stmt).all())
        return {
            edge.dependent_task_id
            for edge in edges
            if task_by_id[edge.prerequisite_task_id].status != TaskStatus.COMPLETED
        }

    def _filter_home_items(self, items: list[dict], *, selected_filter: GoalHomeFilter, today: date) -> list[dict]:
        if selected_filter == GoalHomeFilter.ALL:
            return items
        if selected_filter == GoalHomeFilter.ACTIVE:
            return [item for item in items if item["status"] == GoalStatus.ACTIVE]
        if selected_filter == GoalHomeFilter.DUE_SOON:
            return [item for item in items if self._is_due_soon_home_item(item, today=today)]
        if selected_filter == GoalHomeFilter.COMPLETED:
            return [item for item in items if item["status"] == GoalStatus.COMPLETED]
        if selected_filter == GoalHomeFilter.HIGH_VALUE:
            return [item for item in items if item["value_level"] == ValueLevel.HIGH]
        return items

    def _home_summary(self, goals: list[Goal], items: list[dict], *, today: date) -> dict:
        weekly_completed_task_goal_ids: set[uuid.UUID] = set()
        weekly_completed_task_count = 0
        week_start = today - timedelta(days=today.weekday())
        for goal in goals:
            for task in goal.tasks:
                if task.status != TaskStatus.COMPLETED or task.updated_at.date() < week_start:
                    continue
                weekly_completed_task_count += 1
                weekly_completed_task_goal_ids.add(goal.id)

        return {
            "total_goal_count": len(items),
            "active_goal_count": len([item for item in items if item["status"] == GoalStatus.ACTIVE]),
            "completed_goal_count": len([item for item in items if item["status"] == GoalStatus.COMPLETED]),
            "due_soon_goal_count": len([item for item in items if self._is_due_soon_home_item(item, today=today)]),
            "high_value_goal_count": len([item for item in items if item["value_level"] == ValueLevel.HIGH]),
            "at_risk_goal_count": len(
                [item for item in items if item["risk_level"] in {"behind", "at_risk", "needs_breakdown"}]
            ),
            "weekly_completed_task_count": weekly_completed_task_count,
            "weekly_touched_goal_count": len(weekly_completed_task_goal_ids),
        }

    def _home_filter_counts(self, items: list[dict], *, today: date) -> dict:
        return {
            "all": len(items),
            "active": len([item for item in items if item["status"] == GoalStatus.ACTIVE]),
            "due_soon": len([item for item in items if self._is_due_soon_home_item(item, today=today)]),
            "completed": len([item for item in items if item["status"] == GoalStatus.COMPLETED]),
            "high_value": len([item for item in items if item["value_level"] == ValueLevel.HIGH]),
        }

    def _is_due_soon_home_item(self, item: dict, *, today: date) -> bool:
        deadline = item["deadline"]
        return item["status"] == GoalStatus.ACTIVE and deadline is not None and deadline <= today + timedelta(days=7)

    def _progress(self, *, goal: Goal, tasks: list[Task], today: date) -> dict:
        total_task_count = len(tasks)
        completed_task_count = len([task for task in tasks if task.status == TaskStatus.COMPLETED])
        unfinished_task_count = total_task_count - completed_task_count
        postponed_task_count = len([task for task in tasks if task.status == TaskStatus.POSTPONED])
        progress_sum = sum(float(task.progress or 0) for task in tasks)
        completion_rate = round(progress_sum / total_task_count, 2) if total_task_count else 0.0
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

    def _dependency_map(self, db: Session, tasks: list[Task]) -> dict:
        task_ids = {task.id for task in tasks}
        stmt = select(TaskDependency).where(
            TaskDependency.dependent_task_id.in_(task_ids),
            TaskDependency.prerequisite_task_id.in_(task_ids),
        ).order_by(TaskDependency.created_at)
        edges = list(db.scalars(stmt).all())
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
            "edges": [
                {
                    "from_task_id": edge.prerequisite_task_id,
                    "to_task_id": edge.dependent_task_id,
                    "reason": edge.reason,
                }
                for edge in edges
            ],
            "note": (
                "Task dependency edges are modeled from prerequisite task to dependent task."
                if edges
                else "No dependency edges are linked inside this goal yet."
            ),
        }

    def _goal_timeline_events(
        self,
        db: Session,
        *,
        goal: Goal,
        tasks: list[Task],
        user_id: uuid.UUID,
    ) -> list[ActivityEvent]:
        task_ids = [task.id for task in tasks]
        conditions = [
            (ActivityEvent.entity_type == EntityType.GOAL) & (ActivityEvent.entity_id == goal.id),
        ]
        if task_ids:
            conditions.append(ActivityEvent.related_task_id.in_(task_ids))

        stmt = (
            select(ActivityEvent)
            .where(ActivityEvent.user_id == user_id, or_(*conditions))
            .order_by(ActivityEvent.occurred_at.asc())
            .limit(200)
        )
        return list(db.scalars(stmt).all())

    def _goal_timeline_milestones(
        self,
        *,
        goal: Goal,
        tasks: list[Task],
        events: list[ActivityEvent],
        today: date,
    ) -> list[dict]:
        task_title_by_id = {task.id: task.title for task in tasks}
        milestones: list[dict] = []
        for event in events:
            milestone = self._event_milestone(event, task_title_by_id=task_title_by_id)
            if milestone is not None:
                milestones.append(milestone)

        if goal.deadline is not None:
            milestones.append(self._deadline_milestone(goal=goal, today=today))
        milestones.sort(key=lambda item: (item["milestone_date"] or date.max, item["occurred_at"] is None))
        return milestones

    def _event_milestone(self, event: ActivityEvent, *, task_title_by_id: dict[uuid.UUID, str]) -> dict | None:
        task_title = task_title_by_id.get(event.related_task_id) if event.related_task_id else None
        task_title = task_title or event.payload.get("title")
        milestone_map = {
            "GOAL_CREATED": ("goal_created", "Goal created", "Goal entered Chronos.", "neutral"),
            "GOAL_UPDATED": ("goal_updated", "Goal updated", "Goal metadata changed.", "neutral"),
            "TASK_CREATED": ("task_added", "Task added", "A task was linked to this goal.", "neutral"),
            "TASK_COMPLETED": ("task_completed", "Task completed", "A linked task was completed.", "positive"),
            "TASK_POSTPONED": ("task_postponed", "Task postponed", "A linked task was postponed.", "risk"),
            "TASK_ACTIVATED": ("task_activated", "Task reactivated", "A postponed task returned to active work.", "neutral"),
            "TASK_PRIORITY_ADJUSTED": (
                "priority_adjusted",
                "Priority adjusted",
                "User corrected the task priority or value level.",
                "neutral",
            ),
            "TASK_DEPENDENCY_CREATED": (
                "dependency_added",
                "Dependency added",
                "A prerequisite relationship was added.",
                "neutral",
            ),
            "TASK_DEPENDENCY_DELETED": (
                "dependency_removed",
                "Dependency removed",
                "A prerequisite relationship was removed.",
                "neutral",
            ),
        }
        metadata = milestone_map.get(event.event_type)
        if metadata is None:
            return None
        milestone_type, title, description, signal = metadata
        if task_title:
            description = f"{description} Task: {task_title}."
        return {
            "milestone_type": milestone_type,
            "event_type": event.event_type,
            "title": title,
            "description": description,
            "signal": signal,
            "task_id": event.related_task_id,
            "occurred_at": event.occurred_at,
            "milestone_date": event.occurred_at.date(),
        }

    def _deadline_milestone(self, *, goal: Goal, today: date) -> dict:
        if goal.status == GoalStatus.COMPLETED:
            signal = "positive"
            description = "The goal has been marked completed."
        elif goal.deadline is not None and goal.deadline < today:
            signal = "risk"
            description = "The deadline has passed while the goal is not completed."
        else:
            signal = "neutral"
            description = "The goal deadline is still ahead."
        return {
            "milestone_type": "deadline",
            "event_type": None,
            "title": "Goal deadline",
            "description": description,
            "signal": signal,
            "task_id": None,
            "occurred_at": None,
            "milestone_date": goal.deadline,
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
