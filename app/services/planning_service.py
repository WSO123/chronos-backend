from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.daily_plan import DailyPlan, DailyPlanItem, PlanRevision, StrategySnapshot
from app.models.enums import (
    ActorType,
    DailyPlanItemSection,
    DailyPlanItemStatus,
    DailyPlanStatus,
    EntityType,
    PlanningPreference,
    PlanRevisionTrigger,
    TaskStatus,
    ValueLevel,
)
from app.models.task import Task
from app.models.user import User
from app.services.activity_event_service import activity_event_service
from app.services.errors import InvalidStateError, NotFoundError
from app.services.task_service import task_service


@dataclass(frozen=True)
class PlannedTask:
    task: Task
    section: DailyPlanItemSection
    recommendation_reason: str
    estimated_duration_min: int
    status: DailyPlanItemStatus | None = None
    contributes_to_strategy: bool = True


class PlanningService:
    def get_today(self, db: Session, *, user_id: uuid.UUID, plan_date: date | None = None) -> dict:
        resolved_date = self._resolve_plan_date(db, user_id=user_id, plan_date=plan_date)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=resolved_date)
        if plan is None:
            plan = self._create_plan(
                db,
                user_id=user_id,
                plan_date=resolved_date,
                trigger=PlanRevisionTrigger.INITIAL,
                reason="Initial Today plan",
            )
        else:
            self._sync_current_items(db, plan=plan)
            db.commit()
        return self._build_today_response(db, plan=plan)

    def replan_today(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plan_date: date | None = None,
        reason: str | None = None,
    ) -> dict:
        resolved_date = self._resolve_plan_date(db, user_id=user_id, plan_date=plan_date)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=resolved_date)
        if plan is None:
            plan = self._create_plan(
                db,
                user_id=user_id,
                plan_date=resolved_date,
                trigger=PlanRevisionTrigger.INITIAL,
                reason=reason or "Initial Today plan",
            )
        else:
            self._create_revision(
                db,
                plan=plan,
                trigger=PlanRevisionTrigger.REPLAN,
                reason=reason or "User requested Today replan",
            )
            activity_event_service.add_event(
                db,
                user_id=user_id,
                entity_type=EntityType.DAILY_PLAN,
                entity_id=plan.id,
                event_type="DAILY_PLAN_REPLANNED",
                actor_type=ActorType.USER,
                related_daily_plan_id=plan.id,
                payload={"version": plan.current_version},
            )
            db.commit()
        return self._build_today_response(db, plan=plan)

    def update_item_status(
        self,
        db: Session,
        *,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        status: DailyPlanItemStatus,
    ) -> dict:
        item = self._get_current_item_for_update(db, item_id=item_id, user_id=user_id)
        plan = db.get(DailyPlan, item.daily_plan_id)
        if plan is None or plan.user_id != user_id:
            raise NotFoundError("Daily plan item not found")

        if item.status == status:
            return self._item_response(item)

        self._apply_item_status(db, item=item, plan=plan, status=status, user_id=user_id)
        self._refresh_plan_stats(db, plan=plan, revision_id=plan.current_revision_id)
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DAILY_PLAN,
            entity_id=plan.id,
            event_type="DAILY_PLAN_ITEM_UPDATED",
            actor_type=ActorType.USER,
            related_task_id=item.task_id,
            related_daily_plan_id=plan.id,
            payload={"item_id": str(item.id), "status": item.status.value},
        )
        db.commit()
        db.refresh(item)
        return self._item_response(item)

    def apply_focus_result(
        self,
        db: Session,
        *,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        status: DailyPlanItemStatus | None,
        focus_minutes: int,
    ) -> DailyPlanItem:
        item = self._get_current_item_for_update(db, item_id=item_id, user_id=user_id)
        plan = db.get(DailyPlan, item.daily_plan_id)
        if plan is None or plan.user_id != user_id:
            raise NotFoundError("Daily plan item not found")

        if status is not None:
            item.status = status
        if focus_minutes:
            plan.focus_minutes += focus_minutes
        self._refresh_plan_stats(db, plan=plan, revision_id=plan.current_revision_id)
        db.flush()
        return item

    def _create_plan(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plan_date: date,
        trigger: PlanRevisionTrigger,
        reason: str,
    ) -> DailyPlan:
        plan = DailyPlan(
            user_id=user_id,
            plan_date=plan_date,
            status=DailyPlanStatus.ACTIVE,
            current_version=1,
            total_estimated_minutes=0,
            completed_count=0,
            focus_minutes=0,
            created_by=ActorType.SYSTEM,
        )
        db.add(plan)
        db.flush()
        self._create_revision(db, plan=plan, trigger=trigger, reason=reason)
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DAILY_PLAN,
            entity_id=plan.id,
            event_type="DAILY_PLAN_CREATED",
            actor_type=ActorType.SYSTEM,
            related_daily_plan_id=plan.id,
            payload={"plan_date": plan_date.isoformat(), "version": plan.current_version},
        )
        db.commit()
        db.refresh(plan)
        return plan

    def _create_revision(
        self,
        db: Session,
        *,
        plan: DailyPlan,
        trigger: PlanRevisionTrigger,
        reason: str,
    ) -> PlanRevision:
        version = 1 if trigger == PlanRevisionTrigger.INITIAL else plan.current_version + 1
        remaining_tasks = self._planned_tasks(db, user_id=plan.user_id, plan_date=plan.plan_date)
        completed_carryovers = self._completed_carryover_tasks(db, plan=plan)
        remaining_task_ids = {planned.task.id for planned in remaining_tasks}
        planned_tasks = remaining_tasks + [
            planned for planned in completed_carryovers if planned.task.id not in remaining_task_ids
        ]
        revision = PlanRevision(
            daily_plan_id=plan.id,
            version=version,
            trigger=trigger,
            created_by=ActorType.SYSTEM,
            reason=reason,
            diff_payload={
                "task_ids": [str(planned.task.id) for planned in planned_tasks],
                "completed_carryover_task_ids": [str(planned.task.id) for planned in completed_carryovers],
            },
        )
        db.add(revision)
        db.flush()

        for sort_order, planned in enumerate(planned_tasks, start=1):
            status = planned.status or (
                DailyPlanItemStatus.POSTPONED
                if planned.section == DailyPlanItemSection.ROLLED_OVER
                else DailyPlanItemStatus.PLANNED
            )
            db.add(
                DailyPlanItem(
                    daily_plan_id=plan.id,
                    plan_revision_id=revision.id,
                    task_id=planned.task.id,
                    sort_order=sort_order,
                    section=planned.section,
                    recommendation_reason=planned.recommendation_reason,
                    estimated_duration_min=planned.estimated_duration_min,
                    status=status,
                )
            )

        strategy_tasks = [planned for planned in planned_tasks if planned.contributes_to_strategy]
        strategy_payload = self._strategy_for(strategy_tasks)
        db.add(
            StrategySnapshot(
                daily_plan_id=plan.id,
                plan_revision_id=revision.id,
                summary=strategy_payload["summary"],
                mode=strategy_payload["mode"],
                primary_reason=strategy_payload["primary_reason"],
                score_factors=strategy_payload["score_factors"],
                model_name="rule-planner",
                prompt_version="p1-rule-v1",
            )
        )
        db.flush()
        plan.current_version = version
        plan.current_revision_id = revision.id
        self._refresh_plan_stats(db, plan=plan, revision_id=revision.id)
        db.flush()
        return revision

    def _planned_tasks(self, db: Session, *, user_id: uuid.UUID, plan_date: date) -> list[PlannedTask]:
        stmt = select(Task).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.ACTIVE, TaskStatus.POSTPONED]),
        )
        tasks = list(db.scalars(stmt).all())
        planned_tasks = [
            PlannedTask(
                task=task,
                section=self._section_for(task, plan_date=plan_date),
                recommendation_reason=self._reason_for(task, plan_date=plan_date),
                estimated_duration_min=task.estimated_duration_min or 25,
            )
            for task in tasks
        ]
        return sorted(planned_tasks, key=self._planned_sort_key)

    def _completed_carryover_tasks(self, db: Session, *, plan: DailyPlan) -> list[PlannedTask]:
        carryovers: list[PlannedTask] = []
        seen_task_ids: set[uuid.UUID] = set()
        for item in self._current_items(db, plan=plan):
            if item.task_id in seen_task_ids:
                continue
            if item.status != DailyPlanItemStatus.COMPLETED and item.task.status != TaskStatus.COMPLETED:
                continue
            seen_task_ids.add(item.task_id)
            carryovers.append(
                PlannedTask(
                    task=item.task,
                    section=item.section,
                    recommendation_reason=item.recommendation_reason,
                    estimated_duration_min=item.estimated_duration_min or item.task.estimated_duration_min or 25,
                    status=DailyPlanItemStatus.COMPLETED,
                    contributes_to_strategy=False,
                )
            )
        return carryovers

    def _section_for(self, task: Task, *, plan_date: date) -> DailyPlanItemSection:
        if task.status == TaskStatus.POSTPONED:
            return DailyPlanItemSection.ROLLED_OVER
        if task.deadline is not None and task.deadline <= plan_date:
            return DailyPlanItemSection.PINNED
        if task.value_level == ValueLevel.HIGH or task.priority <= 2:
            return DailyPlanItemSection.PINNED
        if task.priority >= 4 and task.value_level != ValueLevel.HIGH:
            return DailyPlanItemSection.LOW_PRIORITY
        return DailyPlanItemSection.RECOMMENDED

    def _reason_for(self, task: Task, *, plan_date: date) -> str:
        if task.status == TaskStatus.POSTPONED:
            return "Postponed item kept visible without pushing it back into the main sequence."
        if task.deadline is not None and task.deadline < plan_date:
            return "Overdue task protected at the top of today's sequence."
        if task.deadline == plan_date:
            return "Due today, so it is protected in the priority section."
        if task.value_level == ValueLevel.HIGH:
            return "High-value task protected from being crowded out by lighter work."
        if task.priority <= 2:
            return "High-priority task placed early for a clearer start."
        if task.priority >= 4:
            return "Lower-priority task kept available after the main sequence."
        return "Balanced task placed in the recommended execution order."

    def _planned_sort_key(self, planned: PlannedTask) -> tuple[int, date, int, int, datetime]:
        section_rank = {
            DailyPlanItemSection.PINNED: 0,
            DailyPlanItemSection.RECOMMENDED: 1,
            DailyPlanItemSection.LOW_PRIORITY: 2,
            DailyPlanItemSection.ROLLED_OVER: 3,
        }
        value_rank = {ValueLevel.HIGH: 0, ValueLevel.MEDIUM: 1, ValueLevel.LOW: 2}
        return (
            section_rank[planned.section],
            planned.task.deadline or date.max,
            planned.task.priority,
            value_rank[planned.task.value_level],
            planned.task.created_at,
        )

    def _strategy_for(self, planned_tasks: list[PlannedTask]) -> dict:
        active_tasks = [planned for planned in planned_tasks if planned.section != DailyPlanItemSection.ROLLED_OVER]
        pinned_count = len([planned for planned in active_tasks if planned.section == DailyPlanItemSection.PINNED])
        total_minutes = sum(planned.estimated_duration_min for planned in active_tasks)

        if not active_tasks:
            return {
                "summary": "No planned tasks yet. Capture one clear next action when you are ready.",
                "mode": PlanningPreference.LIGHT,
                "primary_reason": "No active tasks need sequencing today.",
                "score_factors": {"task_count": 0, "pinned_count": 0, "total_minutes": 0},
            }
        if total_minutes >= 180 or pinned_count >= 3:
            mode = PlanningPreference.SPRINT
            summary = "Start with protected high-value work, then move through the remaining sequence."
            primary_reason = "The day has enough important work to benefit from a focused order."
        elif total_minutes <= 75 and pinned_count <= 1:
            mode = PlanningPreference.LIGHT
            summary = "Keep today light and start with the clearest next action."
            primary_reason = "The plan is small enough to stay simple."
        else:
            mode = PlanningPreference.NORMAL
            summary = "Use a steady order: protect important tasks first, then continue with lighter work."
            primary_reason = "The sequence balances value, priority, and deadlines."

        return {
            "summary": summary,
            "mode": mode,
            "primary_reason": primary_reason,
            "score_factors": {
                "task_count": len(active_tasks),
                "pinned_count": pinned_count,
                "total_minutes": total_minutes,
            },
        }

    def _build_today_response(self, db: Session, *, plan: DailyPlan) -> dict:
        items = self._current_items(db, plan=plan)
        strategy = self._current_strategy(db, plan=plan)
        progress = self._progress_for(plan=plan, items=items)
        return {
            "date": plan.plan_date,
            "greeting": "Ready when you are.",
            "daily_plan_id": plan.id,
            "plan_version": plan.current_version,
            "strategy": {
                "strategy_snapshot_id": strategy.id,
                "summary": strategy.summary,
                "mode": strategy.mode,
                "primary_reason": strategy.primary_reason,
            },
            "progress": progress,
            "sections": self._sections_for(items),
            "quick_actions": {
                "can_replan": True,
                "can_capture": True,
                "can_view_report": True,
            },
        }

    def _sections_for(self, items: list[DailyPlanItem]) -> dict:
        sections = {
            "pinned_tasks": [],
            "recommended_tasks": [],
            "low_priority_tasks": [],
            "rolled_over_tasks": [],
        }
        section_keys = {
            DailyPlanItemSection.PINNED: "pinned_tasks",
            DailyPlanItemSection.RECOMMENDED: "recommended_tasks",
            DailyPlanItemSection.LOW_PRIORITY: "low_priority_tasks",
            DailyPlanItemSection.ROLLED_OVER: "rolled_over_tasks",
        }
        for item in items:
            sections[section_keys[item.section]].append(self._item_response(item))
        return sections

    def _item_response(self, item: DailyPlanItem) -> dict:
        return {
            "daily_plan_item_id": item.id,
            "task_id": item.task_id,
            "title": item.task.title,
            "goal_id": item.task.goal_id,
            "sort_order": item.sort_order,
            "section": item.section,
            "recommendation_reason": item.recommendation_reason,
            "estimated_duration_min": item.estimated_duration_min,
            "item_status": item.status,
            "task_status": item.task.status,
            "priority": item.task.priority,
            "value_level": item.task.value_level,
            "deadline": item.task.deadline,
        }

    def _progress_for(self, *, plan: DailyPlan, items: list[DailyPlanItem]) -> dict:
        counted_items = [item for item in items if item.section != DailyPlanItemSection.ROLLED_OVER]
        total_count = len(counted_items)
        completed_count = len([item for item in counted_items if item.status == DailyPlanItemStatus.COMPLETED])
        completion_rate = round(completed_count / total_count, 2) if total_count else 0.0
        return {
            "completed_count": completed_count,
            "total_count": total_count,
            "focus_minutes": plan.focus_minutes,
            "completion_rate": completion_rate,
        }

    def _refresh_plan_stats(self, db: Session, *, plan: DailyPlan, revision_id: uuid.UUID | None) -> None:
        if revision_id is None:
            return
        items = self._current_items(db, plan=plan)
        counted_items = [item for item in items if item.section != DailyPlanItemSection.ROLLED_OVER]
        plan.total_estimated_minutes = sum(item.estimated_duration_min or 0 for item in counted_items)
        plan.completed_count = len([item for item in counted_items if item.status == DailyPlanItemStatus.COMPLETED])

    def _sync_current_items(self, db: Session, *, plan: DailyPlan) -> None:
        for item in self._current_items(db, plan=plan):
            if item.task.status == TaskStatus.COMPLETED:
                item.status = DailyPlanItemStatus.COMPLETED
            elif item.task.status == TaskStatus.POSTPONED and item.status != DailyPlanItemStatus.SKIPPED:
                item.status = DailyPlanItemStatus.POSTPONED
        self._refresh_plan_stats(db, plan=plan, revision_id=plan.current_revision_id)

    def _apply_item_status(
        self,
        db: Session,
        *,
        item: DailyPlanItem,
        plan: DailyPlan,
        status: DailyPlanItemStatus,
        user_id: uuid.UUID,
    ) -> None:
        if status == DailyPlanItemStatus.COMPLETED:
            if item.task.status != TaskStatus.COMPLETED:
                task_service.complete_task(
                    db,
                    task_id=item.task_id,
                    user_id=user_id,
                    related_daily_plan_id=plan.id,
                    commit=False,
                )
            item.status = DailyPlanItemStatus.COMPLETED
            return

        if status == DailyPlanItemStatus.POSTPONED:
            if item.task.status == TaskStatus.COMPLETED:
                raise InvalidStateError("completed task cannot be postponed from Today")
            if item.task.status != TaskStatus.POSTPONED:
                task_service.postpone_task(
                    db,
                    task_id=item.task_id,
                    user_id=user_id,
                    related_daily_plan_id=plan.id,
                    commit=False,
                )
            item.status = DailyPlanItemStatus.POSTPONED
            return

        if status == DailyPlanItemStatus.PLANNED:
            if item.task.status == TaskStatus.COMPLETED:
                raise InvalidStateError("completed task cannot be marked planned")
            if item.task.status == TaskStatus.POSTPONED:
                task_service.activate_task(
                    db,
                    task_id=item.task_id,
                    user_id=user_id,
                    related_daily_plan_id=plan.id,
                    commit=False,
                )
            item.status = DailyPlanItemStatus.PLANNED
            return

        item.status = DailyPlanItemStatus.SKIPPED

    def _get_active_plan(self, db: Session, *, user_id: uuid.UUID, plan_date: date) -> DailyPlan | None:
        stmt = select(DailyPlan).where(
            DailyPlan.user_id == user_id,
            DailyPlan.plan_date == plan_date,
            DailyPlan.status == DailyPlanStatus.ACTIVE,
        )
        return db.scalars(stmt).first()

    def _current_items(self, db: Session, *, plan: DailyPlan) -> list[DailyPlanItem]:
        if plan.current_revision_id is None:
            return []
        stmt = (
            select(DailyPlanItem)
            .options(selectinload(DailyPlanItem.task))
            .where(
                DailyPlanItem.daily_plan_id == plan.id,
                DailyPlanItem.plan_revision_id == plan.current_revision_id,
            )
            .order_by(DailyPlanItem.sort_order)
        )
        return list(db.scalars(stmt).all())

    def _current_strategy(self, db: Session, *, plan: DailyPlan) -> StrategySnapshot:
        stmt = select(StrategySnapshot).where(
            StrategySnapshot.daily_plan_id == plan.id,
            StrategySnapshot.plan_revision_id == plan.current_revision_id,
        )
        strategy = db.scalars(stmt).first()
        if strategy is None:
            raise InvalidStateError("Daily plan is missing strategy snapshot")
        return strategy

    def _get_current_item_for_update(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID) -> DailyPlanItem:
        stmt = (
            select(DailyPlanItem)
            .join(DailyPlan)
            .options(selectinload(DailyPlanItem.task))
            .where(
                DailyPlanItem.id == item_id,
                DailyPlan.user_id == user_id,
                DailyPlan.current_revision_id == DailyPlanItem.plan_revision_id,
            )
            .with_for_update()
        )
        item = db.scalars(stmt).first()
        if item is None:
            raise NotFoundError("Daily plan item not found")
        return item

    def _resolve_plan_date(self, db: Session, *, user_id: uuid.UUID, plan_date: date | None) -> date:
        if plan_date is not None:
            return plan_date
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        try:
            timezone = ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo("UTC")
        return datetime.now(timezone).date()


planning_service = PlanningService()
