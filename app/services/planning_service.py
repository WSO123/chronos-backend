from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import ceil
from time import perf_counter
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.agents.daily_planner import DailyPlannerAgent, daily_planner_agent
from app.ai.agents.strategy_explanation import (
    StrategyExplanationAgent,
    strategy_explanation_agent as default_strategy_explanation_agent,
)
from app.ai.providers.base import LLMProviderError, empty_llm_usage
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.planning import DailyPlannerOutput
from app.ai.schemas.strategy_explanation import StrategyExplanationOutput
from app.models.activity_event import ActivityEvent
from app.models.ai_job import AIJob
from app.models.daily_plan import DailyPlan, DailyPlanItem, PlanRevision, StrategySnapshot
from app.models.enums import (
    ActorType,
    AIJobStatus,
    AIJobType,
    AIStrategyPreference,
    DailyPlanItemSection,
    DailyPlanItemStatus,
    DailyPlanStatus,
    EntityType,
    GoalStatus,
    PlanningPreference,
    PlanRevisionTrigger,
    TaskStatus,
    ValueLevel,
)
from app.models.mixins import utc_now
from app.models.task_dependency import TaskDependency
from app.models.task import Task
from app.models.task_planning_signal import TaskPlanningSignal
from app.models.user import User, UserSettings
from app.services.activity_event_service import activity_event_service
from app.services.ai_job_service import ai_job_service
from app.services.energy_service import energy_service
from app.services.errors import InvalidStateError, NotFoundError
from app.services.task_service import task_service
from app.services.task_planning_signal_service import task_planning_signal_service


@dataclass(frozen=True)
class PlannedTask:
    task: Task
    section: DailyPlanItemSection
    recommendation_reason: str
    estimated_duration_min: int
    score: int
    score_breakdown: dict
    status: DailyPlanItemStatus | None = None
    contributes_to_strategy: bool = True
    dependency_depth: int = 0
    unlocks_task: bool = False
    blocked_by_dependency: bool = False
    priority_adjusted: bool = False


@dataclass(frozen=True)
class PlanningContext:
    plan_date: date
    planning_preference: PlanningPreference
    ai_strategy_preference: AIStrategyPreference
    base_capacity_minutes: int
    daily_capacity_minutes: int
    energy_has_data: bool
    energy_score: int | None
    energy_level: str
    energy_recommended_mode: str


class PlanningService:
    def __init__(
        self,
        *,
        planner_agent: DailyPlannerAgent | None = None,
        strategy_explanation_agent: StrategyExplanationAgent | None = None,
    ) -> None:
        self.planner_agent = planner_agent or daily_planner_agent
        self.strategy_explanation_agent = strategy_explanation_agent or default_strategy_explanation_agent

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

    def get_strategy_detail(self, db: Session, *, user_id: uuid.UUID, plan_date: date | None = None) -> dict:
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
        return self._build_strategy_detail_response(db, plan=plan)

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

    def prepare_today_planning_signals(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        plan_date: date | None = None,
        limit: int = 10,
        replan: bool = True,
    ) -> dict:
        resolved_date = self._resolve_plan_date(db, user_id=user_id, plan_date=plan_date)
        today = self.get_today(db, user_id=user_id, plan_date=resolved_date)
        task_ids = self._task_ids_for_signal_preparation(today=today, limit=limit)
        generated_results: list[dict] = []
        existing_count = 0
        stale_count = 0

        for task_id in task_ids:
            freshness = task_planning_signal_service.latest_signal_freshness(db, task_id=task_id, user_id=user_id)
            if freshness["signal"] is not None and freshness["is_fresh"]:
                existing_count += 1
                continue
            if freshness["signal"] is not None:
                stale_count += 1
            generated_results.append(
                task_planning_signal_service.generate_signal(db, task_id=task_id, user_id=user_id)
            )

        replanned = False
        if generated_results and replan:
            today = self.replan_today(
                db,
                user_id=user_id,
                plan_date=resolved_date,
                reason="AI semantic planning signals refreshed",
            )
            replanned = True
        else:
            today = self.get_today(db, user_id=user_id, plan_date=resolved_date)

        return {
            "plan_date": resolved_date,
            "task_count": len(task_ids),
            "generated_count": len(generated_results),
            "existing_count": existing_count,
            "stale_count": stale_count,
            "skipped_count": max(0, len(task_ids) - existing_count - len(generated_results)),
            "replanned": replanned,
            "planning_signal_ids": [
                result["planning_signal"]["id"]
                for result in generated_results
                if result.get("planning_signal")
            ],
            "ai_job_ids": [
                result["ai_job"]["id"]
                for result in generated_results
                if result.get("ai_job")
            ],
            "today": today,
        }

    def describe_task_today_impact(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> dict:
        plan_date = self._resolve_plan_date(db, user_id=user_id, plan_date=None)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=plan_date)
        if plan is None:
            return self._no_active_today_impact(plan_date=plan_date)

        current_item = self._current_item_for_task(db, plan=plan, task_id=task_id)
        return self._today_impact_response(
            plan=plan,
            item=current_item,
            plan_date=plan_date,
            replanned=False,
            reason="already_in_today_plan" if current_item else "not_in_today_plan",
        )

    def _task_ids_for_signal_preparation(self, *, today: dict, limit: int) -> list[uuid.UUID]:
        task_ids: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        for section_key in ("pinned_tasks", "recommended_tasks", "low_priority_tasks"):
            for item in today["sections"][section_key]:
                if item["item_status"] in {DailyPlanItemStatus.COMPLETED, DailyPlanItemStatus.SKIPPED}:
                    continue
                task_id = item["task_id"]
                if task_id in seen:
                    continue
                task_ids.append(task_id)
                seen.add(task_id)
                if len(task_ids) >= limit:
                    return task_ids
        return task_ids

    def get_current_today_item_for_task(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> DailyPlanItem | None:
        plan_date = self._resolve_plan_date(db, user_id=user_id, plan_date=None)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=plan_date)
        if plan is None:
            return None
        return self._current_item_for_task(db, plan=plan, task_id=task_id)

    def refresh_current_today_for_dependency_change(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_ids: set[uuid.UUID],
    ) -> dict | None:
        plan_date = self._resolve_plan_date(db, user_id=user_id, plan_date=None)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=plan_date)
        if plan is None:
            return None

        current_task_ids = {item.task_id for item in self._current_items(db, plan=plan)}
        impacted_task_ids = current_task_ids.intersection(task_ids)
        if not impacted_task_ids:
            return None

        previous_version = plan.current_version
        self._create_revision(
            db,
            plan=plan,
            trigger=PlanRevisionTrigger.SYSTEM_REFRESH,
            reason="Task dependency changed",
        )
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DAILY_PLAN,
            entity_id=plan.id,
            event_type="DAILY_PLAN_SYSTEM_REFRESHED",
            actor_type=ActorType.SYSTEM,
            related_daily_plan_id=plan.id,
            payload={
                "source": "task_dependency",
                "task_ids": [str(task_id) for task_id in sorted(task_ids, key=str)],
                "impacted_task_ids": [str(task_id) for task_id in sorted(impacted_task_ids, key=str)],
                "previous_version": previous_version,
                "version": plan.current_version,
            },
        )
        return {
            "plan_date": plan_date,
            "daily_plan_id": plan.id,
            "previous_version": previous_version,
            "plan_version": plan.current_version,
            "impacted_task_ids": [task_id for task_id in sorted(impacted_task_ids, key=str)],
        }

    def refresh_current_today_for_priority_adjustment(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> dict:
        plan_date = self._resolve_plan_date(db, user_id=user_id, plan_date=None)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=plan_date)
        if plan is None:
            return self._no_active_today_impact(plan_date=plan_date)

        current_item = self._current_item_for_task(db, plan=plan, task_id=task_id)
        if current_item is None:
            return self._today_impact_response(
                plan=plan,
                item=None,
                plan_date=plan_date,
                replanned=False,
                reason="not_in_today_plan",
            )

        previous_version = plan.current_version
        self._create_revision(
            db,
            plan=plan,
            trigger=PlanRevisionTrigger.MANUAL_ADJUST,
            reason="Task priority adjusted",
        )
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DAILY_PLAN,
            entity_id=plan.id,
            event_type="DAILY_PLAN_MANUAL_ADJUSTED",
            actor_type=ActorType.USER,
            related_task_id=task_id,
            related_daily_plan_id=plan.id,
            payload={
                "source": "task_priority_adjustment",
                "task_id": str(task_id),
                "previous_version": previous_version,
                "version": plan.current_version,
            },
        )
        current_item = self._current_item_for_task(db, plan=plan, task_id=task_id)
        return self._today_impact_response(
            plan=plan,
            item=current_item,
            plan_date=plan_date,
            replanned=True,
            reason="manual_priority_adjustment",
        )

    def include_confirmed_task_from_inbox(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> dict:
        plan_date = self._resolve_plan_date(db, user_id=user_id, plan_date=None)
        plan = self._get_active_plan(db, user_id=user_id, plan_date=plan_date)
        if plan is None:
            return self._no_active_today_impact(plan_date=plan_date)

        current_item = self._current_item_for_task(db, plan=plan, task_id=task_id)
        if current_item is None:
            previous_version = plan.current_version
            self._create_revision(
                db,
                plan=plan,
                trigger=PlanRevisionTrigger.SYSTEM_REFRESH,
                reason="Inbox confirmed task added to Today",
            )
            activity_event_service.add_event(
                db,
                user_id=user_id,
                entity_type=EntityType.DAILY_PLAN,
                entity_id=plan.id,
                event_type="DAILY_PLAN_SYSTEM_REFRESHED",
                actor_type=ActorType.SYSTEM,
                related_task_id=task_id,
                related_daily_plan_id=plan.id,
                payload={
                    "source": "inbox_confirm",
                    "task_id": str(task_id),
                    "previous_version": previous_version,
                    "version": plan.current_version,
                },
            )
            current_item = self._current_item_for_task(db, plan=plan, task_id=task_id)
            replanned = True
            reason = "replanned_existing_today_plan"
        else:
            self._sync_current_items(db, plan=plan)
            replanned = False
            reason = "already_in_today_plan"

        return self._today_impact_response(
            plan=plan,
            item=current_item,
            plan_date=plan_date,
            replanned=replanned,
            reason=reason,
        )

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

    def minimum_viable_progress_delta_for_item(self, item: DailyPlanItem) -> Decimal | None:
        score_breakdown = item.score_breakdown or {}
        if not score_breakdown.get("minimum_viable_progress_applied"):
            return None

        planned_duration = int(
            score_breakdown.get("planned_duration_min")
            or item.estimated_duration_min
            or 0
        )
        original_duration = int(
            score_breakdown.get("original_estimated_duration_min")
            or score_breakdown.get("base_estimated_duration_min")
            or item.task.estimated_duration_min
            or 0
        )
        if planned_duration <= 0 or original_duration <= 0:
            return Decimal("0.10")
        if planned_duration >= original_duration:
            return None
        ratio = Decimal(planned_duration) / Decimal(original_duration)
        return max(Decimal("0.01"), min(Decimal("0.99"), ratio)).quantize(Decimal("0.01"))

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
        completed_task_ids = {planned.task.id for planned in completed_carryovers}
        planned_tasks = [
            planned for planned in remaining_tasks if planned.task.id not in completed_task_ids
        ] + completed_carryovers
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

        strategy_tasks = [planned for planned in planned_tasks if planned.contributes_to_strategy]
        strategy_payload = self._strategy_for(strategy_tasks)
        planner_result = self._run_daily_planner_agent(
            db,
            plan=plan,
            revision=revision,
            planned_tasks=planned_tasks,
            strategy_payload=strategy_payload,
        )
        planned_tasks = planner_result["planned_tasks"]
        strategy_payload = planner_result["strategy_payload"]
        planner_job = planner_result["ai_job"]

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
                    score_breakdown=planned.score_breakdown,
                    status=status,
                )
            )

        db.add(
            StrategySnapshot(
                daily_plan_id=plan.id,
                plan_revision_id=revision.id,
                summary=strategy_payload["summary"],
                mode=strategy_payload["mode"],
                primary_reason=strategy_payload["primary_reason"],
                score_factors=strategy_payload["score_factors"],
                model_name="planning-engine-v1",
                prompt_version="p2-planning-engine-v1",
            )
        )
        planner_job.result_entity_type = EntityType.DAILY_PLAN.value
        planner_job.result_entity_id = plan.id
        db.flush()
        plan.current_version = version
        plan.current_revision_id = revision.id
        self._refresh_plan_stats(db, plan=plan, revision_id=revision.id)
        db.flush()
        return revision

    def _planned_tasks(self, db: Session, *, user_id: uuid.UUID, plan_date: date) -> list[PlannedTask]:
        stmt = (
            select(Task)
            .options(selectinload(Task.goal))
            .where(
                Task.user_id == user_id,
                Task.status.in_([TaskStatus.ACTIVE, TaskStatus.POSTPONED]),
            )
        )
        tasks = list(db.scalars(stmt).all())
        context = self._planning_context(db, user_id=user_id, plan_date=plan_date)
        signals = self._planning_signals(db, user_id=user_id, tasks=tasks, plan_date=plan_date)
        scored_tasks: list[PlannedTask] = []
        for task in tasks:
            score_breakdown = self._score_breakdown_for(task, context=context, signals=signals)
            planned_duration_min, score_breakdown = self._planned_duration_for_today(
                task,
                score_breakdown=score_breakdown,
                context=context,
            )
            base_section = self._section_for(
                task,
                plan_date=plan_date,
                unlocking_task_ids=signals["unlocking_task_ids"],
                goal_next_action_task_ids=signals["goal_next_action_task_ids"],
                semantic_by_task_id=signals["semantic_by_task_id"],
            )
            scored_tasks.append(
                PlannedTask(
                    task=task,
                    section=base_section,
                    recommendation_reason=self._reason_for(
                        task,
                        plan_date=plan_date,
                        unlocking_task_ids=signals["unlocking_task_ids"],
                        blocked_task_ids=signals["blocked_task_ids"],
                        adjusted_task_ids=signals["adjusted_task_ids"],
                        goal_next_action_task_ids=signals["goal_next_action_task_ids"],
                        semantic_by_task_id=signals["semantic_by_task_id"],
                        score_breakdown=score_breakdown,
                    ),
                    estimated_duration_min=planned_duration_min,
                    score=int(score_breakdown["total_score"]),
                    score_breakdown=score_breakdown,
                    dependency_depth=signals["dependency_depth_by_task_id"].get(task.id, 0),
                    unlocks_task=task.id in signals["unlocking_task_ids"],
                    blocked_by_dependency=task.id in signals["blocked_task_ids"],
                    priority_adjusted=task.id in signals["adjusted_task_ids"],
                )
            )
        return self._apply_capacity(sorted(scored_tasks, key=self._planned_sort_key), context=context)

    def _run_daily_planner_agent(
        self,
        db: Session,
        *,
        plan: DailyPlan,
        revision: PlanRevision,
        planned_tasks: list[PlannedTask],
        strategy_payload: dict,
    ) -> dict:
        planner_provider = llm_provider_registry.current_provider()
        job = ai_job_service.create_job(
            db,
            user_id=plan.user_id,
            job_type=AIJobType.DAILY_PLANNER,
            input_entity_type=EntityType.DAILY_PLAN.value,
            input_entity_id=plan.id,
            provider=planner_provider.provider_name,
            model=planner_provider.model_name,
            prompt_version=self.planner_agent.prompt_version,
            metadata={
                "mode": "sync_structured_shell",
                "plan_revision_id": str(revision.id),
                "candidate_count": len(planned_tasks),
                "planner_core": "planning-engine-v1",
                "prompt_checksum": getattr(self.planner_agent, "prompt_checksum", None),
            },
            commit=False,
        )
        job.status = AIJobStatus.RUNNING
        job.started_at = utc_now()
        provider_call_started = perf_counter()

        try:
            agent_result = self.planner_agent.run(
                plan_context={
                    "plan_date": plan.plan_date.isoformat(),
                    "daily_plan_id": str(plan.id),
                    "plan_revision_id": str(revision.id),
                },
                candidates=self._planner_candidates(planned_tasks),
                strategy_seed={
                    "mode": strategy_payload["mode"].value,
                    "summary": strategy_payload["summary"],
                    "primary_reason": strategy_payload["primary_reason"],
                    "score_factors": strategy_payload["score_factors"],
                },
                provider=planner_provider,
            )
            job.provider = agent_result.provider
            job.model = agent_result.model
            job.prompt_version = agent_result.prompt_version
            planned_tasks, strategy_payload = self._apply_daily_planner_output(
                planned_tasks=planned_tasks,
                strategy_payload=strategy_payload,
                output=agent_result.output,
            )
            job.status = AIJobStatus.SUCCEEDED
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": True,
                "confidence": agent_result.output.confidence,
                "item_count": len(agent_result.output.items),
                "review_summary": strategy_payload["score_factors"].get("planner_agent_review_summary"),
                "suggestions": strategy_payload["score_factors"].get("planner_agent_suggestions", []),
                "suggestion_count": len(strategy_payload["score_factors"].get("planner_agent_suggestions", [])),
                "prompt_checksum": agent_result.prompt_checksum,
                "provider_response_id": getattr(agent_result, "response_id", None),
                "usage": getattr(agent_result, "usage", empty_llm_usage()),
            }
        except Exception as exc:  # noqa: BLE001 - fallback is the product boundary here.
            job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
            job.error_message = str(exc)
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": False,
                "fallback_reason": self._planner_fallback_reason(exc),
                "fallback_error_type": exc.__class__.__name__,
                "fallback_root_error_type": self._root_error_type(exc),
                "failure_type": self._planner_failure_type(exc),
            }

        job.finished_at = utc_now()
        job.latency_ms = max(0, int((perf_counter() - provider_call_started) * 1000))
        job.job_metadata = {
            **job.job_metadata,
            "provider_latency_ms": job.latency_ms,
            "provider_observability_version": "v1",
            "usage": self._planner_usage_metadata(job.job_metadata.get("usage")),
        }
        strategy_payload["score_factors"] = {
            **strategy_payload["score_factors"],
            "ai_job_id": str(job.id),
            "planner_agent_status": job.status.value,
            "planner_agent_provider": job.provider,
            "planner_agent_model": job.model,
            "planner_agent_prompt_version": job.prompt_version,
            "planner_agent_prompt_checksum": job.job_metadata.get("prompt_checksum"),
            "planner_agent_latency_ms": job.latency_ms,
            "planner_agent_failure_type": job.job_metadata.get("failure_type"),
            "planner_agent_output_applied": job.job_metadata.get("output_applied", False),
            "planner_agent_review_summary": job.job_metadata.get("review_summary"),
            "planner_agent_suggestions": job.job_metadata.get("suggestions", []),
        }
        return {"planned_tasks": planned_tasks, "strategy_payload": strategy_payload, "ai_job": job}

    def _planner_usage_metadata(self, usage: object) -> dict:
        if not isinstance(usage, dict):
            return empty_llm_usage()
        return {**empty_llm_usage(), **usage}

    def _planner_fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return "daily_planner_agent_invalid_output"
        return "daily_planner_agent_failed"

    def _planner_failure_type(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return "invalid_output"
        if isinstance(exc, LLMProviderError):
            return "provider_error"
        return "agent_error"

    def _root_error_type(self, exc: Exception) -> str:
        root = exc
        while root.__cause__ is not None:
            root = root.__cause__
        return root.__class__.__name__

    def _planner_candidates(self, planned_tasks: list[PlannedTask]) -> list[dict]:
        return [
            {
                "task_id": str(planned.task.id),
                "title": planned.task.title,
                "section": planned.section.value,
                "sort_order": index,
                "recommendation_reason": planned.recommendation_reason,
                "estimated_duration_min": planned.estimated_duration_min,
                "score_breakdown": planned.score_breakdown,
            }
            for index, planned in enumerate(planned_tasks, start=1)
        ]

    def _apply_daily_planner_output(
        self,
        *,
        planned_tasks: list[PlannedTask],
        strategy_payload: dict,
        output: DailyPlannerOutput,
    ) -> tuple[list[PlannedTask], dict]:
        item_by_task_id = {item.task_id: item for item in output.items}
        expected_task_ids = [str(planned.task.id) for planned in planned_tasks]
        if (
            len(output.items) != len(expected_task_ids)
            or len(item_by_task_id) != len(expected_task_ids)
            or set(item_by_task_id) != set(expected_task_ids)
        ):
            raise ValueError("Daily planner output task ids do not match deterministic plan")

        applied_tasks: list[PlannedTask] = []
        for index, planned in enumerate(planned_tasks, start=1):
            output_item = item_by_task_id[str(planned.task.id)]
            if output_item.sort_order != index:
                raise ValueError("Daily planner output cannot reorder tasks in v1")
            if output_item.section != planned.section.value:
                raise ValueError("Daily planner output cannot move tasks across sections in v1")
            applied_tasks.append(
                PlannedTask(
                    task=planned.task,
                    section=planned.section,
                    recommendation_reason=output_item.recommendation_reason,
                    estimated_duration_min=planned.estimated_duration_min,
                    score=planned.score,
                    score_breakdown=planned.score_breakdown,
                    status=planned.status,
                    contributes_to_strategy=planned.contributes_to_strategy,
                    dependency_depth=planned.dependency_depth,
                    unlocks_task=planned.unlocks_task,
                    blocked_by_dependency=planned.blocked_by_dependency,
                    priority_adjusted=planned.priority_adjusted,
                )
            )

        strategy_payload = {
            **strategy_payload,
            "summary": output.strategy_summary,
            "mode": PlanningPreference(output.mode),
            "primary_reason": output.primary_reason,
            "score_factors": {
                **strategy_payload["score_factors"],
                "planner_agent_review_summary": self._clean_optional_planner_text(output.review_summary),
                "planner_agent_suggestions": self._clean_planner_suggestions(output.suggestions),
            },
        }
        return applied_tasks, strategy_payload

    def _clean_optional_planner_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None

    def _clean_planner_suggestions(self, suggestions: list) -> list[dict]:
        cleaned_suggestions: list[dict] = []
        for suggestion in suggestions[:3]:
            item = {
                "key": self._clean_optional_planner_text(suggestion.key),
                "title": self._clean_optional_planner_text(suggestion.title),
                "message": self._clean_optional_planner_text(suggestion.message),
                "signal": suggestion.signal,
            }
            if item["key"] and item["title"] and item["message"]:
                cleaned_suggestions.append(item)
        return cleaned_suggestions

    def _planning_context(self, db: Session, *, user_id: uuid.UUID, plan_date: date) -> PlanningContext:
        settings = self._settings_for(db, user_id=user_id)
        planning_preference = settings.planning_preference if settings else PlanningPreference.NORMAL
        ai_strategy_preference = settings.ai_strategy_preference if settings else AIStrategyPreference.BALANCED
        base_capacity = {
            PlanningPreference.LIGHT: 90,
            PlanningPreference.NORMAL: 150,
            PlanningPreference.SPRINT: 210,
        }[planning_preference]

        dashboard = energy_service.get_dashboard(db, user_id=user_id, end_date=plan_date, days=1)
        summary = dashboard["summary"]
        task_match = dashboard["task_match"]
        energy_has_data = bool(dashboard["trends"][0]["has_data"])
        energy_level = summary["energy_level"]
        daily_capacity = base_capacity
        if energy_has_data and energy_level == "low":
            daily_capacity = min(base_capacity, 90)

        return PlanningContext(
            plan_date=plan_date,
            planning_preference=planning_preference,
            ai_strategy_preference=ai_strategy_preference,
            base_capacity_minutes=base_capacity,
            daily_capacity_minutes=daily_capacity,
            energy_has_data=energy_has_data,
            energy_score=summary["energy_score"],
            energy_level=energy_level,
            energy_recommended_mode=task_match["recommended_mode"],
        )

    def _settings_for(self, db: Session, *, user_id: uuid.UUID) -> UserSettings | None:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        return db.scalars(stmt).first()

    def _score_breakdown_for(self, task: Task, *, context: PlanningContext, signals: dict) -> dict:
        semantic_signal = signals["semantic_by_task_id"].get(task.id)
        personalization = signals["personalization_by_task_id"].get(
            task.id,
            self._empty_personalization_profile(task_type=semantic_signal.task_type if semantic_signal else None),
        )
        duration_estimate = self._duration_estimate_for(
            task,
            semantic_signal=semantic_signal,
            personalization=personalization,
        )
        estimated_minutes = int(duration_estimate["estimated_duration_min"])
        behavior = signals["behavior_by_task_id"].get(
            task.id,
            {"completed": 0, "postponed": 0, "interrupted": 0},
        )
        goal_progress = signals["goal_progress_by_task_id"].get(
            task.id,
            self._empty_goal_progress_profile(
                goal_id=task.goal_id,
                value_level=task.goal.value_level if task.goal else None,
            ),
        )
        value_score = {ValueLevel.HIGH: 30, ValueLevel.MEDIUM: 18, ValueLevel.LOW: 8}[task.value_level]
        goal_value_score = self._goal_value_score(task)
        urgency_score = self._urgency_score(task=task, plan_date=context.plan_date)
        goal_urgency_score = self._goal_urgency_score(task=task, plan_date=context.plan_date)
        dependency_score = 0
        if task.id in signals["unlocking_task_ids"]:
            dependency_score += 18
        if task.id in signals["blocked_task_ids"]:
            dependency_score -= 10
        goal_next_action_score = 10 if task.id in signals["goal_next_action_task_ids"] else 0
        goal_progress_score = int(goal_progress.get("score") or 0)
        duration_fit_score = self._duration_fit_score(estimated_minutes, capacity=context.daily_capacity_minutes)
        energy_fit_score = self._energy_fit_score(
            estimated_minutes,
            value_level=task.value_level,
            context=context,
        )
        behavior_feedback_score = min(behavior["completed"], 3) * 2
        behavior_feedback_score -= min(behavior["postponed"], 3) * 6
        behavior_feedback_score -= min(behavior["interrupted"], 3) * 4
        personalization_score = int(personalization.get("score") or 0)
        user_preference_score = 10 if task.id in signals["adjusted_task_ids"] else 0
        if context.ai_strategy_preference == AIStrategyPreference.HIGH_VALUE_FIRST and task.value_level == ValueLevel.HIGH:
            user_preference_score += 8
        if context.ai_strategy_preference == AIStrategyPreference.ENERGY_AWARE and context.energy_has_data:
            user_preference_score += max(energy_fit_score, 0) // 2
        postponement_penalty = -12 if task.status == TaskStatus.POSTPONED else 0
        priority_score = max(0, 6 - task.priority) * 4
        semantic_scores = self._semantic_signal_scores(
            task=task,
            semantic_signal=semantic_signal,
            context=context,
        )
        total_score = (
            value_score
            + goal_value_score
            + urgency_score
            + goal_urgency_score
            + dependency_score
            + goal_next_action_score
            + goal_progress_score
            + duration_fit_score
            + energy_fit_score
            + behavior_feedback_score
            + personalization_score
            + user_preference_score
            + postponement_penalty
            + priority_score
            + semantic_scores["semantic_total_score"]
        )
        total_score = int(total_score)
        return {
            "score_version": "planning-engine-v1",
            "semantic_planning_version": "task-semantic-signals-v1",
            "total_score": total_score,
            "score_band": self._score_band(total_score),
            "value_score": int(value_score),
            "goal_value_score": int(goal_value_score),
            "urgency_score": int(urgency_score),
            "goal_urgency_score": int(goal_urgency_score),
            "dependency_score": int(dependency_score),
            "goal_next_action_score": int(goal_next_action_score),
            "goal_progress_score": int(goal_progress_score),
            "duration_fit_score": int(duration_fit_score),
            "energy_fit_score": int(energy_fit_score),
            "behavior_feedback_score": int(behavior_feedback_score),
            "personalization_score": personalization_score,
            "user_preference_score": int(user_preference_score),
            "postponement_penalty": int(postponement_penalty),
            "priority_score": int(priority_score),
            **semantic_scores,
            **duration_estimate,
            "user_estimated_duration_min": task.estimated_duration_min,
            "daily_capacity_minutes": int(context.daily_capacity_minutes),
            "energy_level": context.energy_level,
            "energy_applied": context.energy_has_data,
            "behavior": behavior,
            **self._goal_progress_score_breakdown(goal_progress),
            **self._personalization_score_breakdown(personalization),
        }

    def _estimated_minutes_for(self, task: Task, *, semantic_signal: TaskPlanningSignal | None) -> int:
        if task.estimated_duration_min:
            return task.estimated_duration_min
        if semantic_signal is not None and semantic_signal.estimated_duration_min:
            return semantic_signal.estimated_duration_min
        return 25

    def _duration_estimate_for(
        self,
        task: Task,
        *,
        semantic_signal: TaskPlanningSignal | None,
        personalization: dict,
    ) -> dict:
        base_estimate = self._estimated_minutes_for(task, semantic_signal=semantic_signal)
        personalized_estimate = self._personalized_estimated_minutes(
            base_estimate=base_estimate,
            personalization=personalization,
        )
        actual_minutes = max(0, int(task.actual_duration_min or 0))
        progress_ratio = max(0.0, min(1.0, float(task.progress or 0)))
        remaining_estimate = personalized_estimate
        feedback_reason = None

        if 0 < progress_ratio < 1:
            remaining_estimate = max(15, ceil(personalized_estimate * (1 - progress_ratio)))
            feedback_reason = "task_progress_remaining"
        elif actual_minutes > 0:
            if actual_minutes < personalized_estimate:
                remaining_estimate = max(15, personalized_estimate - actual_minutes)
                feedback_reason = "actual_duration_remaining"
            else:
                remaining_estimate = max(25, min(45, personalized_estimate))
                feedback_reason = "actual_duration_overrun"

        return {
            "estimated_duration_min": int(remaining_estimate),
            "base_estimated_duration_min": int(base_estimate),
            "personalized_estimated_duration_min": int(personalized_estimate),
            "personalized_duration_adjustment_min": int(personalized_estimate - base_estimate),
            "remaining_estimated_duration_min": int(remaining_estimate),
            "actual_duration_min": actual_minutes,
            "progress_ratio": round(progress_ratio, 2),
            "execution_feedback_applied": remaining_estimate != personalized_estimate,
            "execution_feedback_reason": feedback_reason if remaining_estimate != personalized_estimate else None,
        }

    def _semantic_signal_scores(
        self,
        *,
        task: Task,
        semantic_signal: TaskPlanningSignal | None,
        context: PlanningContext,
    ) -> dict:
        if semantic_signal is None:
            return {
                "semantic_signal_applied": False,
                "semantic_signal_id": None,
                "semantic_task_type": None,
                "semantic_complexity": None,
                "semantic_cognitive_load": None,
                "semantic_energy_fit": None,
                "semantic_blocking_risk": None,
                "semantic_estimated_duration_min": None,
                "semantic_minimum_viable_step": None,
                "goal_alignment_signal_score": 0,
                "semantic_priority_signal_score": 0,
                "semantic_complexity_score": 0,
                "semantic_energy_fit_score": 0,
                "blocking_risk_score": 0,
                "semantic_total_score": 0,
            }

        goal_alignment_signal_score = int(round(semantic_signal.goal_alignment_score * 14))
        semantic_priority_signal_score = int(round(semantic_signal.semantic_priority_score * 18))
        blocking_risk_score = {"low": 0, "medium": 4, "high": 10}.get(semantic_signal.blocking_risk, 0)
        semantic_complexity_score = self._semantic_complexity_score(task=task, semantic_signal=semantic_signal)
        semantic_energy_fit_score = self._semantic_energy_fit_score(
            semantic_signal=semantic_signal,
            context=context,
        )
        semantic_total_score = (
            goal_alignment_signal_score
            + semantic_priority_signal_score
            + semantic_complexity_score
            + semantic_energy_fit_score
            + blocking_risk_score
        )
        return {
            "semantic_signal_applied": True,
            "semantic_signal_id": str(semantic_signal.id),
            "semantic_task_type": semantic_signal.task_type,
            "semantic_complexity": semantic_signal.complexity,
            "semantic_cognitive_load": semantic_signal.cognitive_load,
            "semantic_energy_fit": semantic_signal.energy_fit,
            "semantic_blocking_risk": semantic_signal.blocking_risk,
            "semantic_estimated_duration_min": semantic_signal.estimated_duration_min,
            "semantic_minimum_viable_step": semantic_signal.minimum_viable_step,
            "goal_alignment_signal_score": goal_alignment_signal_score,
            "semantic_priority_signal_score": semantic_priority_signal_score,
            "semantic_complexity_score": semantic_complexity_score,
            "semantic_energy_fit_score": semantic_energy_fit_score,
            "blocking_risk_score": blocking_risk_score,
            "semantic_total_score": semantic_total_score,
        }

    def _semantic_complexity_score(self, *, task: Task, semantic_signal: TaskPlanningSignal) -> int:
        if semantic_signal.complexity == "high":
            if task.value_level == ValueLevel.HIGH or semantic_signal.goal_alignment_score >= 0.75:
                return 6
            return -3
        if semantic_signal.complexity == "low":
            return 2
        return 0

    def _semantic_energy_fit_score(
        self,
        *,
        semantic_signal: TaskPlanningSignal,
        context: PlanningContext,
    ) -> int:
        if not context.energy_has_data:
            return 0
        if context.energy_level == "low":
            if semantic_signal.energy_fit == "low_energy" or semantic_signal.cognitive_load == "low":
                return 8
            if semantic_signal.energy_fit == "high_energy" or semantic_signal.cognitive_load == "high":
                return -10
            return 2
        if context.energy_level == "high":
            if semantic_signal.energy_fit == "high_energy" or semantic_signal.cognitive_load == "high":
                return 8
            return 3
        return 2

    def _planned_duration_for_today(
        self,
        task: Task,
        *,
        score_breakdown: dict,
        context: PlanningContext,
    ) -> tuple[int, dict]:
        original_duration = int(score_breakdown["estimated_duration_min"])
        planned_duration = original_duration
        minimum_viable_applied = False
        minimum_viable_reason = None

        has_minimum_step = bool(score_breakdown.get("semantic_minimum_viable_step"))
        semantic_protected = int(score_breakdown.get("semantic_total_score") or 0) >= 28
        high_value_goal = task.goal is not None and task.goal.value_level == ValueLevel.HIGH
        high_value_task = task.value_level == ValueLevel.HIGH
        heavy_for_today = original_duration > max(60, int(context.daily_capacity_minutes * 0.6))

        if (
            score_breakdown.get("semantic_signal_applied")
            and has_minimum_step
            and heavy_for_today
            and (semantic_protected or high_value_goal or high_value_task)
        ):
            planned_duration = min(
                original_duration,
                max(25, min(45, context.daily_capacity_minutes // 2)),
            )
            minimum_viable_applied = planned_duration < original_duration
            minimum_viable_reason = "semantic_minimum_viable_progress" if minimum_viable_applied else None

        updated_breakdown = {
            **score_breakdown,
            "original_estimated_duration_min": original_duration,
            "planned_duration_min": planned_duration,
            "minimum_viable_progress_applied": minimum_viable_applied,
            "minimum_viable_progress_reason": minimum_viable_reason,
        }
        return planned_duration, updated_breakdown

    def _score_band(self, total_score: int) -> str:
        if total_score >= 70:
            return "high"
        if total_score >= 40:
            return "medium"
        return "low"

    def _urgency_score(self, *, task: Task, plan_date: date) -> int:
        if task.deadline is None:
            return 0
        days_until_deadline = (task.deadline - plan_date).days
        if days_until_deadline < 0:
            return 30
        if days_until_deadline == 0:
            return 24
        if days_until_deadline <= 3:
            return 16
        if days_until_deadline <= 7:
            return 8
        return 0

    def _goal_value_score(self, task: Task) -> int:
        if task.goal is None:
            return 0
        return {ValueLevel.HIGH: 12, ValueLevel.MEDIUM: 4, ValueLevel.LOW: 0}[task.goal.value_level]

    def _goal_urgency_score(self, *, task: Task, plan_date: date) -> int:
        if task.goal is None or task.goal.deadline is None:
            return 0
        days_until_deadline = (task.goal.deadline - plan_date).days
        if days_until_deadline < 0:
            return 18
        if days_until_deadline == 0:
            return 14
        if days_until_deadline <= 3:
            return 8
        if days_until_deadline <= 7:
            return 4
        return 0

    def _duration_fit_score(self, estimated_minutes: int, *, capacity: int) -> int:
        if estimated_minutes <= 30:
            return 8
        if estimated_minutes <= max(45, capacity // 3):
            return 5
        if estimated_minutes > max(75, int(capacity * 0.6)):
            return -8
        return 2

    def _energy_fit_score(
        self,
        estimated_minutes: int,
        *,
        value_level: ValueLevel,
        context: PlanningContext,
    ) -> int:
        if not context.energy_has_data:
            return 0
        if context.energy_level == "low":
            if estimated_minutes <= 30:
                return 14
            if estimated_minutes >= 60:
                return -14
            return 4
        if context.energy_level == "high":
            if estimated_minutes >= 45 or value_level == ValueLevel.HIGH:
                return 12
            return 4
        return 4

    def _apply_capacity(self, planned_tasks: list[PlannedTask], *, context: PlanningContext) -> list[PlannedTask]:
        selected_minutes = 0
        result: list[PlannedTask] = []
        for planned in planned_tasks:
            if planned.task.status == TaskStatus.POSTPONED:
                result.append(self._roll_over(planned, reason="postponed"))
                continue

            protected = planned.section == DailyPlanItemSection.PINNED
            fits_capacity = selected_minutes + planned.estimated_duration_min <= context.daily_capacity_minutes
            if protected or fits_capacity:
                selected_minutes += planned.estimated_duration_min
                score_breakdown = dict(planned.score_breakdown)
                score_breakdown["selected_for_today"] = True
                score_breakdown["capacity_remaining_after_minutes"] = max(
                    context.daily_capacity_minutes - selected_minutes,
                    0,
                )
                result.append(
                    PlannedTask(
                        task=planned.task,
                        section=planned.section,
                        recommendation_reason=planned.recommendation_reason,
                        estimated_duration_min=planned.estimated_duration_min,
                        score=planned.score,
                        score_breakdown=score_breakdown,
                        dependency_depth=planned.dependency_depth,
                        unlocks_task=planned.unlocks_task,
                        blocked_by_dependency=planned.blocked_by_dependency,
                        priority_adjusted=planned.priority_adjusted,
                    )
                )
                continue
            result.append(self._roll_over(planned, reason="capacity"))
        return result

    def _roll_over(self, planned: PlannedTask, *, reason: str) -> PlannedTask:
        score_breakdown = dict(planned.score_breakdown)
        score_breakdown["selected_for_today"] = False
        score_breakdown["rollover_reason"] = reason
        if reason == "capacity":
            recommendation_reason = "Rolled forward because today's capacity is already protected for higher-value work."
        else:
            recommendation_reason = planned.recommendation_reason
        return PlannedTask(
            task=planned.task,
            section=DailyPlanItemSection.ROLLED_OVER,
            recommendation_reason=recommendation_reason,
            estimated_duration_min=planned.estimated_duration_min,
            score=planned.score,
            score_breakdown=score_breakdown,
            status=DailyPlanItemStatus.POSTPONED if reason == "postponed" else DailyPlanItemStatus.PLANNED,
            dependency_depth=planned.dependency_depth,
            unlocks_task=planned.unlocks_task,
            blocked_by_dependency=planned.blocked_by_dependency,
            priority_adjusted=planned.priority_adjusted,
        )

    def _planning_signals(self, db: Session, *, user_id: uuid.UUID, tasks: list[Task], plan_date: date) -> dict:
        task_by_id = {task.id: task for task in tasks}
        if not task_by_id:
            return {
                "dependency_depth_by_task_id": {},
                "unlocking_task_ids": set(),
                "blocked_task_ids": set(),
                "goal_next_action_task_ids": set(),
                "goal_progress_by_task_id": {},
                "adjusted_task_ids": set(),
                "behavior_by_task_id": {},
                "semantic_by_task_id": {},
                "personalization_by_task_id": {},
            }

        task_ids = set(task_by_id)
        dependency_edges = list(
            db.scalars(
                select(TaskDependency).where(
                    TaskDependency.user_id == user_id,
                    TaskDependency.dependent_task_id.in_(task_ids),
                    TaskDependency.prerequisite_task_id.in_(task_ids),
                )
            ).all()
        )
        prerequisites_by_dependent: dict[uuid.UUID, list[uuid.UUID]] = {}
        unlocking_task_ids: set[uuid.UUID] = set()
        blocked_task_ids: set[uuid.UUID] = set()
        for edge in dependency_edges:
            prerequisites_by_dependent.setdefault(edge.dependent_task_id, []).append(edge.prerequisite_task_id)
            unlocking_task_ids.add(edge.prerequisite_task_id)
            blocked_task_ids.add(edge.dependent_task_id)

        depth_by_task_id: dict[uuid.UUID, int] = {}
        visiting: set[uuid.UUID] = set()

        def dependency_depth(task_id: uuid.UUID) -> int:
            if task_id in depth_by_task_id:
                return depth_by_task_id[task_id]
            if task_id in visiting:
                return 0
            visiting.add(task_id)
            prerequisites = prerequisites_by_dependent.get(task_id, [])
            depth = 0
            if prerequisites:
                depth = max(dependency_depth(prerequisite_id) + 1 for prerequisite_id in prerequisites)
            visiting.remove(task_id)
            depth_by_task_id[task_id] = depth
            return depth

        for task_id in task_ids:
            dependency_depth(task_id)

        goal_next_action_task_ids = self._goal_next_action_task_ids(
            tasks=tasks,
            blocked_task_ids=blocked_task_ids,
            depth_by_task_id=depth_by_task_id,
            plan_date=plan_date,
        )
        goal_progress_by_task_id = self._goal_progress_by_task_id(
            db,
            user_id=user_id,
            tasks=tasks,
            goal_next_action_task_ids=goal_next_action_task_ids,
            plan_date=plan_date,
        )

        adjusted_task_ids = set(
            db.scalars(
                select(ActivityEvent.related_task_id).where(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.event_type == "TASK_PRIORITY_ADJUSTED",
                    ActivityEvent.related_task_id.in_(task_ids),
                )
            ).all()
        )
        behavior_by_task_id = {
            task_id: {"completed": 0, "postponed": 0, "interrupted": 0}
            for task_id in task_ids
        }
        behavior_events = list(
            db.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.related_task_id.in_(task_ids),
                    ActivityEvent.event_type.in_(
                        [
                            "TASK_COMPLETED",
                            "TASK_POSTPONED",
                            "FOCUS_SESSION_INTERRUPTED",
                            "FOCUS_SESSION_POSTPONED",
                        ]
                    ),
                )
            ).all()
        )
        for event in behavior_events:
            if event.related_task_id is None:
                continue
            behavior = behavior_by_task_id.setdefault(
                event.related_task_id,
                {"completed": 0, "postponed": 0, "interrupted": 0},
            )
            if event.event_type == "TASK_COMPLETED":
                behavior["completed"] += 1
            elif event.event_type in {"TASK_POSTPONED", "FOCUS_SESSION_POSTPONED"}:
                behavior["postponed"] += 1
            elif event.event_type == "FOCUS_SESSION_INTERRUPTED":
                behavior["interrupted"] += 1

        semantic_by_task_id: dict[uuid.UUID, TaskPlanningSignal] = {}
        semantic_signals = list(
            db.scalars(
                select(TaskPlanningSignal)
                .where(
                    TaskPlanningSignal.user_id == user_id,
                    TaskPlanningSignal.task_id.in_(task_ids),
                )
                .order_by(TaskPlanningSignal.created_at.desc(), TaskPlanningSignal.id.desc())
            ).all()
        )
        for signal in semantic_signals:
            task = task_by_id.get(signal.task_id)
            if task is None or signal.task_id in semantic_by_task_id:
                continue
            freshness = task_planning_signal_service.signal_freshness(db, task=task, signal=signal)
            if freshness["is_fresh"]:
                semantic_by_task_id[signal.task_id] = signal

        personalization_by_task_id = self._personalization_by_task_id(
            db,
            user_id=user_id,
            candidate_task_ids=task_ids,
            semantic_by_task_id=semantic_by_task_id,
        )

        return {
            "dependency_depth_by_task_id": depth_by_task_id,
            "unlocking_task_ids": unlocking_task_ids,
            "blocked_task_ids": blocked_task_ids,
            "goal_next_action_task_ids": goal_next_action_task_ids,
            "goal_progress_by_task_id": goal_progress_by_task_id,
            "adjusted_task_ids": adjusted_task_ids,
            "behavior_by_task_id": behavior_by_task_id,
            "semantic_by_task_id": semantic_by_task_id,
            "personalization_by_task_id": personalization_by_task_id,
        }

    def _goal_progress_by_task_id(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        tasks: list[Task],
        goal_next_action_task_ids: set[uuid.UUID],
        plan_date: date,
    ) -> dict[uuid.UUID, dict]:
        if not goal_next_action_task_ids:
            return {}

        goal_by_id = {
            task.goal_id: task.goal
            for task in tasks
            if task.goal_id is not None
            and task.goal is not None
            and task.goal.status == GoalStatus.ACTIVE
            and task.id in goal_next_action_task_ids
        }
        goal_ids = {goal_id for goal_id in goal_by_id if goal_id is not None}
        if not goal_ids:
            return {}

        goal_tasks = list(
            db.scalars(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.goal_id.in_(goal_ids),
                    Task.status != TaskStatus.ARCHIVED,
                )
            ).all()
        )
        tasks_by_goal_id: dict[uuid.UUID, list[Task]] = {}
        for goal_task in goal_tasks:
            if goal_task.goal_id is None:
                continue
            tasks_by_goal_id.setdefault(goal_task.goal_id, []).append(goal_task)

        profile_by_goal_id = {
            goal_id: self._goal_progress_profile(
                goal=goal,
                tasks=tasks_by_goal_id.get(goal_id, []),
                plan_date=plan_date,
            )
            for goal_id, goal in goal_by_id.items()
            if goal_id is not None and goal is not None
        }

        return {
            task.id: profile_by_goal_id.get(
                task.goal_id,
                self._empty_goal_progress_profile(
                    goal_id=task.goal_id,
                    value_level=task.goal.value_level if task.goal else None,
                ),
            )
            for task in tasks
            if task.goal_id is not None and task.id in goal_next_action_task_ids
        }

    def _goal_progress_profile(self, *, goal, tasks: list[Task], plan_date: date) -> dict:
        if not tasks:
            return self._empty_goal_progress_profile(goal_id=goal.id, value_level=goal.value_level)

        total_task_count = len(tasks)
        completed_task_count = 0
        progress_sum = 0.0
        remaining_estimated_minutes = 0

        for task in tasks:
            if task.status == TaskStatus.COMPLETED:
                completed_task_count += 1
                progress_sum += 1.0
                continue
            task_progress = max(0.0, min(1.0, float(task.progress or 0)))
            progress_sum += task_progress
            base_estimate = int(task.estimated_duration_min or 25)
            remaining_estimated_minutes += max(15, ceil(base_estimate * (1 - task_progress)))

        completion_rate = round(progress_sum / total_task_count, 2) if total_task_count else 0.0
        unfinished_task_count = max(0, total_task_count - completed_task_count)
        days_until_deadline = (goal.deadline - plan_date).days if goal.deadline is not None else None
        score = 0
        reason_key = "steady_goal_progress"
        pressure_level = "steady"

        if days_until_deadline is not None:
            if days_until_deadline < 0:
                score += 18
                reason_key = "goal_progress_overdue"
                pressure_level = "risk"
            elif days_until_deadline <= 3 and completion_rate < 0.8:
                score += 14
                reason_key = "goal_progress_deadline_risk"
                pressure_level = "risk"
            elif days_until_deadline <= 7 and completion_rate < 0.65:
                score += 10
                reason_key = "goal_progress_deadline_watch"
                pressure_level = "watch"
            elif days_until_deadline <= 14 and completion_rate < 0.4:
                score += 5
                reason_key = "goal_progress_slow_start"
                pressure_level = "watch"

        if goal.value_level == ValueLevel.HIGH:
            if completion_rate < 0.35:
                score += 9
                if pressure_level != "risk":
                    reason_key = "high_value_goal_under_progress"
                    pressure_level = "watch"
            elif completion_rate < 0.7:
                score += 6
                if pressure_level != "risk":
                    reason_key = "high_value_goal_needs_progress"
                    pressure_level = "watch"
        elif goal.value_level == ValueLevel.MEDIUM and completion_rate < 0.45 and days_until_deadline is not None:
            score += 3
            if pressure_level == "steady":
                reason_key = "goal_needs_progress"
                pressure_level = "watch"

        if completion_rate >= 0.65 and unfinished_task_count <= 2:
            score += 8 if goal.value_level == ValueLevel.HIGH else 5
            if pressure_level != "risk":
                reason_key = "goal_completion_closure"
                pressure_level = "closure"
        elif goal.value_level == ValueLevel.HIGH and unfinished_task_count >= 3 and completion_rate < 0.8:
            score += 4

        score = min(24, int(score))
        if score <= 0:
            return self._empty_goal_progress_profile(goal_id=goal.id, value_level=goal.value_level)

        return {
            "applied": True,
            "goal_id": goal.id,
            "goal_value_level": goal.value_level,
            "total_task_count": total_task_count,
            "completed_task_count": completed_task_count,
            "unfinished_task_count": unfinished_task_count,
            "completion_rate": completion_rate,
            "remaining_estimated_minutes": remaining_estimated_minutes,
            "days_until_deadline": days_until_deadline,
            "pressure_level": pressure_level,
            "reason_key": reason_key,
            "score": score,
        }

    def _empty_goal_progress_profile(self, *, goal_id: uuid.UUID | None, value_level: ValueLevel | None) -> dict:
        return {
            "applied": False,
            "goal_id": goal_id,
            "goal_value_level": value_level,
            "total_task_count": 0,
            "completed_task_count": 0,
            "unfinished_task_count": 0,
            "completion_rate": 0.0,
            "remaining_estimated_minutes": 0,
            "days_until_deadline": None,
            "pressure_level": "none",
            "reason_key": None,
            "score": 0,
        }

    def _goal_progress_score_breakdown(self, goal_progress: dict) -> dict:
        goal_id = goal_progress.get("goal_id")
        value_level = goal_progress.get("goal_value_level")
        return {
            "goal_progress_applied": bool(goal_progress.get("applied")),
            "goal_progress_version": "goal-progress-strategy-v1",
            "goal_progress_goal_id": str(goal_id) if goal_id else None,
            "goal_progress_goal_value_level": value_level.value if hasattr(value_level, "value") else value_level,
            "goal_progress_total_task_count": int(goal_progress.get("total_task_count") or 0),
            "goal_progress_completed_task_count": int(goal_progress.get("completed_task_count") or 0),
            "goal_progress_unfinished_task_count": int(goal_progress.get("unfinished_task_count") or 0),
            "goal_progress_completion_rate": float(goal_progress.get("completion_rate") or 0.0),
            "goal_progress_remaining_estimated_minutes": int(goal_progress.get("remaining_estimated_minutes") or 0),
            "goal_progress_days_until_deadline": goal_progress.get("days_until_deadline"),
            "goal_progress_pressure_level": goal_progress.get("pressure_level") or "none",
            "goal_progress_reason_key": goal_progress.get("reason_key"),
        }

    def _personalization_by_task_id(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        candidate_task_ids: set[uuid.UUID],
        semantic_by_task_id: dict[uuid.UUID, TaskPlanningSignal],
    ) -> dict[uuid.UUID, dict]:
        task_types = {
            signal.task_type
            for signal in semantic_by_task_id.values()
            if signal.task_type and signal.task_type != "general"
        }
        if not task_types:
            return {}

        latest_signal_by_task_id: dict[uuid.UUID, TaskPlanningSignal] = {}
        signals = list(
            db.scalars(
                select(TaskPlanningSignal)
                .where(
                    TaskPlanningSignal.user_id == user_id,
                    TaskPlanningSignal.task_type.in_(task_types),
                )
                .order_by(TaskPlanningSignal.created_at.desc(), TaskPlanningSignal.id.desc())
            ).all()
        )
        for signal in signals:
            if signal.task_id in latest_signal_by_task_id:
                continue
            latest_signal_by_task_id[signal.task_id] = signal

        history_task_ids = set(latest_signal_by_task_id) - set(candidate_task_ids)
        if not history_task_ids:
            return {
                task_id: self._empty_personalization_profile(task_type=signal.task_type)
                for task_id, signal in semantic_by_task_id.items()
            }

        history_tasks = list(
            db.scalars(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.id.in_(history_task_ids),
                    Task.status != TaskStatus.ARCHIVED,
                )
            ).all()
        )
        history_events = list(
            db.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.related_task_id.in_(history_task_ids),
                    ActivityEvent.event_type.in_(
                        [
                            "TASK_COMPLETED",
                            "TASK_POSTPONED",
                            "FOCUS_SESSION_INTERRUPTED",
                            "FOCUS_SESSION_POSTPONED",
                        ]
                    ),
                )
            ).all()
        )
        events_by_task_id: dict[uuid.UUID, dict[str, int]] = {
            task_id: {"completed": 0, "postponed": 0, "interrupted": 0}
            for task_id in history_task_ids
        }
        for event in history_events:
            if event.related_task_id is None:
                continue
            counts = events_by_task_id.setdefault(
                event.related_task_id,
                {"completed": 0, "postponed": 0, "interrupted": 0},
            )
            if event.event_type == "TASK_COMPLETED":
                counts["completed"] += 1
            elif event.event_type in {"TASK_POSTPONED", "FOCUS_SESSION_POSTPONED"}:
                counts["postponed"] += 1
            elif event.event_type == "FOCUS_SESSION_INTERRUPTED":
                counts["interrupted"] += 1

        stats_by_type: dict[str, dict] = {}
        for task in history_tasks:
            signal = latest_signal_by_task_id.get(task.id)
            if signal is None:
                continue
            counts = events_by_task_id.get(
                task.id,
                {"completed": 0, "postponed": 0, "interrupted": 0},
            )
            actual_minutes = int(task.actual_duration_min or 0)
            if actual_minutes <= 0 and task.status != TaskStatus.COMPLETED and not any(counts.values()):
                continue
            stats = stats_by_type.setdefault(signal.task_type, self._empty_personalization_stats())
            base_estimate = int(task.estimated_duration_min or signal.estimated_duration_min or 25)
            stats["sample_count"] += 1
            stats["completed_count"] += 1 if task.status == TaskStatus.COMPLETED or counts["completed"] else 0
            stats["postponed_count"] += counts["postponed"]
            stats["interrupted_count"] += counts["interrupted"]
            if base_estimate > 0 and actual_minutes > 0:
                stats["duration_sample_count"] += 1
                stats["estimated_total_min"] += base_estimate
                stats["actual_total_min"] += actual_minutes
                if actual_minutes >= int(base_estimate * 1.25):
                    stats["overrun_count"] += 1

        return {
            task_id: self._personalization_profile_for_signal(
                signal=signal,
                stats=stats_by_type.get(signal.task_type),
            )
            for task_id, signal in semantic_by_task_id.items()
        }

    def _empty_personalization_stats(self) -> dict:
        return {
            "sample_count": 0,
            "duration_sample_count": 0,
            "completed_count": 0,
            "postponed_count": 0,
            "interrupted_count": 0,
            "overrun_count": 0,
            "estimated_total_min": 0,
            "actual_total_min": 0,
        }

    def _personalization_profile_for_signal(
        self,
        *,
        signal: TaskPlanningSignal,
        stats: dict | None,
    ) -> dict:
        if stats is None or stats["sample_count"] < 2:
            return self._empty_personalization_profile(task_type=signal.task_type)

        duration_multiplier = 1.0
        if stats["duration_sample_count"] >= 2 and stats["estimated_total_min"] > 0:
            duration_multiplier = stats["actual_total_min"] / stats["estimated_total_min"]
            duration_multiplier = max(0.70, min(1.80, duration_multiplier))

        completion_rate = stats["completed_count"] / stats["sample_count"] if stats["sample_count"] else 0.0
        friction_count = stats["postponed_count"] + stats["interrupted_count"]
        friction_rate = friction_count / stats["sample_count"] if stats["sample_count"] else 0.0
        overrun_risk = stats["overrun_count"] >= 2 or duration_multiplier >= 1.25
        interruption_risk = stats["interrupted_count"] >= 2 or friction_rate >= 0.5
        postponement_risk = stats["postponed_count"] >= 2
        completion_momentum = (
            completion_rate >= 0.75
            and not overrun_risk
            and not interruption_risk
            and not postponement_risk
        )
        score = 0
        if overrun_risk:
            score -= 4
        if interruption_risk:
            score -= 6
        if postponement_risk:
            score -= 4
        if completion_momentum:
            score += 4

        return {
            "applied": True,
            "task_type": signal.task_type,
            "sample_count": stats["sample_count"],
            "duration_sample_count": stats["duration_sample_count"],
            "completed_count": stats["completed_count"],
            "completion_rate": round(completion_rate, 2),
            "postponed_count": stats["postponed_count"],
            "interrupted_count": stats["interrupted_count"],
            "overrun_count": stats["overrun_count"],
            "duration_multiplier": round(duration_multiplier, 2),
            "overrun_risk": overrun_risk,
            "interruption_risk": interruption_risk,
            "postponement_risk": postponement_risk,
            "completion_momentum": completion_momentum,
            "score": int(score),
        }

    def _empty_personalization_profile(self, *, task_type: str | None) -> dict:
        return {
            "applied": False,
            "task_type": task_type,
            "sample_count": 0,
            "duration_sample_count": 0,
            "completed_count": 0,
            "completion_rate": 0.0,
            "postponed_count": 0,
            "interrupted_count": 0,
            "overrun_count": 0,
            "duration_multiplier": 1.0,
            "overrun_risk": False,
            "interruption_risk": False,
            "postponement_risk": False,
            "completion_momentum": False,
            "score": 0,
        }

    def _personalized_estimated_minutes(self, *, base_estimate: int, personalization: dict) -> int:
        if not personalization.get("applied") or personalization.get("duration_sample_count", 0) < 2:
            return int(base_estimate)
        multiplier = float(personalization.get("duration_multiplier") or 1.0)
        if 0.85 <= multiplier <= 1.15:
            return int(base_estimate)
        adjusted = ceil(base_estimate * multiplier)
        return max(15, min(240, int(adjusted)))

    def _personalization_score_breakdown(self, personalization: dict) -> dict:
        return {
            "personalization_applied": bool(personalization.get("applied")),
            "personalization_version": "planning-personalization-v1",
            "personalization_task_type": personalization.get("task_type"),
            "personalization_sample_count": int(personalization.get("sample_count") or 0),
            "personalization_duration_sample_count": int(personalization.get("duration_sample_count") or 0),
            "personalization_completed_count": int(personalization.get("completed_count") or 0),
            "personalization_completion_rate": float(personalization.get("completion_rate") or 0.0),
            "personalization_postponed_count": int(personalization.get("postponed_count") or 0),
            "personalization_interrupted_count": int(personalization.get("interrupted_count") or 0),
            "personalization_overrun_count": int(personalization.get("overrun_count") or 0),
            "personalization_duration_multiplier": float(personalization.get("duration_multiplier") or 1.0),
            "personalization_overrun_risk": bool(personalization.get("overrun_risk")),
            "personalization_interruption_risk": bool(personalization.get("interruption_risk")),
            "personalization_postponement_risk": bool(personalization.get("postponement_risk")),
            "personalization_completion_momentum": bool(personalization.get("completion_momentum")),
        }

    def _goal_next_action_task_ids(
        self,
        *,
        tasks: list[Task],
        blocked_task_ids: set[uuid.UUID],
        depth_by_task_id: dict[uuid.UUID, int],
        plan_date: date,
    ) -> set[uuid.UUID]:
        tasks_by_goal_id: dict[uuid.UUID, list[Task]] = {}
        for task in tasks:
            if task.goal_id is None or task.goal is None:
                continue
            if not self._goal_needs_next_action_protection(task=task, plan_date=plan_date):
                continue
            tasks_by_goal_id.setdefault(task.goal_id, []).append(task)

        protected_task_ids: set[uuid.UUID] = set()
        for goal_tasks in tasks_by_goal_id.values():
            next_action = sorted(
                goal_tasks,
                key=lambda task: (
                    task.id in blocked_task_ids,
                    task.status == TaskStatus.POSTPONED,
                    depth_by_task_id.get(task.id, 0),
                    task.deadline or date.max,
                    task.priority,
                    self._estimated_minutes_for(task, semantic_signal=None),
                    task.created_at,
                ),
            )[0]
            protected_task_ids.add(next_action.id)
        return protected_task_ids

    def _goal_needs_next_action_protection(self, *, task: Task, plan_date: date) -> bool:
        if task.goal is None:
            return False
        if task.goal.value_level == ValueLevel.HIGH:
            return True
        if task.goal.deadline is None:
            return False
        return (task.goal.deadline - plan_date).days <= 7

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
                    score=int((item.score_breakdown or {}).get("total_score") or 0),
                    score_breakdown=item.score_breakdown or {},
                    status=DailyPlanItemStatus.COMPLETED,
                    contributes_to_strategy=False,
                )
            )
        return carryovers

    def _section_for(
        self,
        task: Task,
        *,
        plan_date: date,
        unlocking_task_ids: set[uuid.UUID],
        goal_next_action_task_ids: set[uuid.UUID],
        semantic_by_task_id: dict[uuid.UUID, TaskPlanningSignal],
    ) -> DailyPlanItemSection:
        semantic_signal = semantic_by_task_id.get(task.id)
        if task.status == TaskStatus.POSTPONED:
            return DailyPlanItemSection.ROLLED_OVER
        if task.id in unlocking_task_ids:
            return DailyPlanItemSection.PINNED
        if task.id in goal_next_action_task_ids:
            return DailyPlanItemSection.PINNED
        if (
            semantic_signal is not None
            and (
                (
                    semantic_signal.semantic_priority_score >= 0.82
                    and semantic_signal.goal_alignment_score >= 0.75
                )
                or (
                    semantic_signal.goal_alignment_score >= 0.85
                    and semantic_signal.blocking_risk == "high"
                )
            )
        ):
            return DailyPlanItemSection.PINNED
        if task.deadline is not None and task.deadline <= plan_date:
            return DailyPlanItemSection.PINNED
        if task.goal is not None and task.goal.deadline is not None and task.goal.deadline <= plan_date:
            return DailyPlanItemSection.PINNED
        if task.goal is not None and task.goal.value_level == ValueLevel.HIGH and task.priority <= 3:
            return DailyPlanItemSection.PINNED
        if task.value_level == ValueLevel.HIGH or task.priority <= 2:
            return DailyPlanItemSection.PINNED
        if task.priority >= 4 and task.value_level != ValueLevel.HIGH:
            return DailyPlanItemSection.LOW_PRIORITY
        return DailyPlanItemSection.RECOMMENDED

    def _reason_for(
        self,
        task: Task,
        *,
        plan_date: date,
        unlocking_task_ids: set[uuid.UUID],
        blocked_task_ids: set[uuid.UUID],
        adjusted_task_ids: set[uuid.UUID],
        goal_next_action_task_ids: set[uuid.UUID],
        semantic_by_task_id: dict[uuid.UUID, TaskPlanningSignal],
        score_breakdown: dict,
    ) -> str:
        semantic_signal = semantic_by_task_id.get(task.id)
        if task.status == TaskStatus.POSTPONED:
            return "Postponed item kept visible without pushing it back into the main sequence."
        if task.deadline is not None and task.deadline < plan_date:
            return "Overdue task protected at the top of today's sequence."
        if task.deadline == plan_date:
            return "Due today, so it is protected in the priority section."
        if task.goal is not None and task.goal.deadline is not None and task.goal.deadline < plan_date:
            return "Goal is overdue, so this next task is pulled back into today's protected sequence."
        if task.goal is not None and task.goal.deadline == plan_date:
            return "Goal is due today, so this task is protected before lighter work."
        if task.id in unlocking_task_ids:
            return "Prerequisite task placed early because it unlocks another planned task."
        if task.id in blocked_task_ids:
            return "Dependent task kept after its prerequisite in today's sequence."
        if task.id in adjusted_task_ids:
            return "Adjusted by you, so the planner keeps that preference visible."
        if score_breakdown.get("minimum_viable_progress_applied"):
            return "任务较大，今天先保护最小可执行动作，避免高价值目标被整块任务压垮。"
        if (
            semantic_signal is not None
            and score_breakdown.get("semantic_signal_applied")
            and score_breakdown.get("semantic_total_score", 0) >= 28
        ):
            return "AI 语义信号判断它能有效推进目标，因此今天保护一个最小可执行动作。"
        if score_breakdown.get("goal_progress_applied"):
            return self._goal_progress_reason(score_breakdown=score_breakdown)
        if task.id in goal_next_action_task_ids:
            return "这是关联目标当前最适合推进的下一步，系统会保护它进入今日主序列。"
        if score_breakdown.get("personalization_applied") and score_breakdown.get("personalization_score", 0) < 0:
            return "系统读取了你过去同类任务的执行阻力，因此按更保守的节奏安排。"
        if score_breakdown.get("personalization_applied") and score_breakdown.get("personalization_score", 0) > 0:
            return "系统读取了你过去同类任务的完成势能，因此保留这个顺手推进的机会。"
        if task.value_level == ValueLevel.HIGH:
            return "High-value task protected from being crowded out by lighter work."
        if task.goal is not None and task.goal.value_level == ValueLevel.HIGH:
            return "High-value goal protected so its next action is not crowded out by lighter work."
        if task.priority <= 2:
            return "High-priority task placed early for a clearer start."
        if task.priority >= 4:
            return "Lower-priority task kept available after the main sequence."
        if score_breakdown.get("energy_applied") and score_breakdown.get("energy_fit_score", 0) > 0:
            return "Placed here because the task shape fits today's energy signal."
        return "Balanced task placed in the recommended execution order."

    def _goal_progress_reason(self, *, score_breakdown: dict) -> str:
        reason_key = score_breakdown.get("goal_progress_reason_key")
        if reason_key == "goal_completion_closure":
            return "这个目标已经接近完成，Today 会保护下一步来提高目标完成度。"
        if reason_key in {"goal_progress_overdue", "goal_progress_deadline_risk"}:
            return "关联目标进度落后且截止压力较高，系统会优先拉回它的下一步。"
        if reason_key == "goal_progress_deadline_watch":
            return "关联目标接近截止且完成率偏低，Today 会提前保护它的下一步。"
        if reason_key in {"high_value_goal_under_progress", "high_value_goal_needs_progress"}:
            return "高价值目标当前推进不足，系统会把下一步放进今天的主行动。"
        return "系统读取了目标完成率和剩余任务，把这个下一步作为今天的推进点。"

    def _planned_sort_key(self, planned: PlannedTask) -> tuple[int, int, int, int, int, int, int, int, date, int, int, datetime]:
        section_rank = {
            DailyPlanItemSection.PINNED: 0,
            DailyPlanItemSection.RECOMMENDED: 1,
            DailyPlanItemSection.LOW_PRIORITY: 2,
            DailyPlanItemSection.ROLLED_OVER: 3,
        }
        value_rank = {ValueLevel.HIGH: 0, ValueLevel.MEDIUM: 1, ValueLevel.LOW: 2}
        return (
            section_rank[planned.section],
            planned.dependency_depth,
            0 if planned.unlocks_task else 1,
            1 if planned.blocked_by_dependency else 0,
            0 if planned.priority_adjusted else 1,
            0 if planned.score_breakdown.get("goal_next_action_score", 0) > 0 else 1,
            0 if planned.score_breakdown.get("goal_progress_score", 0) > 0 else 1,
            -planned.score,
            planned.task.deadline or date.max,
            planned.task.priority,
            value_rank[planned.task.value_level],
            planned.task.created_at,
        )

    def _strategy_for(self, planned_tasks: list[PlannedTask]) -> dict:
        active_tasks = [planned for planned in planned_tasks if planned.section != DailyPlanItemSection.ROLLED_OVER]
        rolled_over_tasks = [planned for planned in planned_tasks if planned.section == DailyPlanItemSection.ROLLED_OVER]
        pinned_count = len([planned for planned in active_tasks if planned.section == DailyPlanItemSection.PINNED])
        total_minutes = sum(planned.estimated_duration_min for planned in active_tasks)
        rolled_over_minutes = sum(planned.estimated_duration_min for planned in rolled_over_tasks)
        dependency_protected_count = len([planned for planned in active_tasks if planned.unlocks_task])
        goal_next_action_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("goal_next_action_score", 0) > 0]
        )
        user_adjusted_count = len([planned for planned in active_tasks if planned.priority_adjusted])
        semantic_signal_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("semantic_signal_applied")]
        )
        semantic_protected_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("semantic_total_score", 0) >= 28]
        )
        minimum_viable_progress_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("minimum_viable_progress_applied")]
        )
        execution_feedback_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("execution_feedback_applied")]
        )
        personalization_signal_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("personalization_applied")]
        )
        goal_progress_signal_count = len(
            [planned for planned in active_tasks if planned.score_breakdown.get("goal_progress_applied")]
        )
        first_breakdown = planned_tasks[0].score_breakdown if planned_tasks else {}
        daily_capacity_minutes = int(first_breakdown.get("daily_capacity_minutes") or 0)
        energy_level = str(first_breakdown.get("energy_level") or "unknown")
        energy_applied = bool(first_breakdown.get("energy_applied") or False)
        over_capacity_minutes = self._over_capacity_minutes(
            selected_minutes=total_minutes,
            daily_capacity_minutes=daily_capacity_minutes,
        )
        capacity_status = "overloaded" if over_capacity_minutes else "within_capacity"

        if not active_tasks:
            return {
                "summary": "No planned tasks yet. Capture one clear next action when you are ready.",
                "mode": PlanningPreference.LIGHT,
                "primary_reason": "No active tasks need sequencing today.",
                "score_factors": {
                    "task_count": 0,
                    "pinned_count": 0,
                    "total_minutes": 0,
                    "daily_capacity_minutes": daily_capacity_minutes,
                    "selected_estimated_minutes": 0,
                    "rolled_over_estimated_minutes": rolled_over_minutes,
                    "over_capacity_minutes": 0,
                    "capacity_status": "within_capacity",
                    "dependency_protected_count": 0,
                    "goal_next_action_count": 0,
                    "user_adjusted_count": 0,
                    "semantic_signal_count": 0,
                    "semantic_protected_count": 0,
                    "minimum_viable_progress_count": 0,
                    "execution_feedback_count": 0,
                    "personalization_signal_count": 0,
                    "goal_progress_signal_count": 0,
                    "energy_level": energy_level,
                    "energy_applied": energy_applied,
                },
            }
        if total_minutes >= max(180, daily_capacity_minutes) or pinned_count >= 3:
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
                "daily_capacity_minutes": daily_capacity_minutes,
                "selected_estimated_minutes": total_minutes,
                "rolled_over_estimated_minutes": rolled_over_minutes,
                "over_capacity_minutes": over_capacity_minutes,
                "capacity_status": capacity_status,
                "dependency_protected_count": dependency_protected_count,
                "goal_next_action_count": goal_next_action_count,
                "user_adjusted_count": user_adjusted_count,
                "semantic_signal_count": semantic_signal_count,
                "semantic_protected_count": semantic_protected_count,
                "minimum_viable_progress_count": minimum_viable_progress_count,
                "execution_feedback_count": execution_feedback_count,
                "personalization_signal_count": personalization_signal_count,
                "goal_progress_signal_count": goal_progress_signal_count,
                "energy_level": energy_level,
                "energy_applied": energy_applied,
                "average_score": round(
                    sum(planned.score for planned in active_tasks) / len(active_tasks),
                    2,
                ),
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
            "insights_preview": self._insights_preview(plan=plan, items=items, progress=progress),
            "quick_actions": {
                "can_replan": True,
                "can_capture": True,
                "can_view_report": True,
            },
        }

    def _build_strategy_detail_response(self, db: Session, *, plan: DailyPlan) -> dict:
        items = self._current_items(db, plan=plan)
        strategy = self._current_strategy(db, plan=plan)
        revision = self._current_revision(db, plan=plan)
        factors = self._strategy_factors(plan=plan, items=items, score_factors=strategy.score_factors)
        task_rationales = [self._strategy_task_rationale_response(item) for item in items]
        score_explanation = self._strategy_score_explanation(
            strategy=strategy,
            factors=factors,
            task_rationales=task_rationales,
        )
        energy = self._strategy_energy_explanation(db, plan=plan)
        explanation_result = self._run_strategy_explanation_agent(
            db,
            plan=plan,
            strategy=strategy,
            factors=factors,
            score_explanation=score_explanation,
            task_rationales=task_rationales,
        )
        return {
            "date": plan.plan_date,
            "daily_plan_id": plan.id,
            "plan_version": plan.current_version,
            "summary": strategy.summary,
            "mode": strategy.mode,
            "primary_reason": strategy.primary_reason,
            "revision": {
                "plan_revision_id": revision.id,
                "version": revision.version,
                "trigger": revision.trigger,
                "reason": revision.reason,
                "created_at": revision.created_at,
            },
            "factors": factors,
            "explanation": explanation_result["explanation"],
            "energy": energy,
            "score_explanation": score_explanation,
            "planner_review": self._planner_review(score_factors=strategy.score_factors),
            "task_rationales": task_rationales,
            "source": {
                "strategy_snapshot_id": strategy.id,
                "ai_job_id": strategy.score_factors.get("ai_job_id"),
                "model_name": strategy.model_name,
                "prompt_version": strategy.prompt_version,
                "generated_at": strategy.created_at,
                "explanation_ai_job_id": explanation_result["ai_job_id"],
                "explanation_model_name": explanation_result["model_name"],
                "explanation_prompt_version": explanation_result["prompt_version"],
                "explanation_status": explanation_result["status"],
            },
        }

    def _planner_review(self, *, score_factors: dict) -> dict | None:
        suggestions = score_factors.get("planner_agent_suggestions") or []
        summary = score_factors.get("planner_agent_review_summary")
        if not summary and not suggestions:
            return None
        return {
            "summary": summary,
            "suggestions": suggestions[:3],
            "source": "daily_planner_agent_v1",
        }

    def _strategy_score_explanation(
        self,
        *,
        strategy: StrategySnapshot,
        factors: dict,
        task_rationales: list[dict],
    ) -> dict:
        if factors["task_count"] <= 0:
            return {
                "summary": "当前没有需要排序的主执行任务，Planning Engine 暂时只保留轻量入口。",
                "signals": [],
                "source": "planning-engine-score-breakdown-v1",
            }

        capacity = factors["daily_capacity_minutes"]
        selected_minutes = factors["selected_estimated_minutes"]
        if factors["over_capacity_minutes"]:
            summary = (
                f"Planning Engine 识别到受保护任务约 {selected_minutes} 分钟，"
                f"已超过今日容量参考 {capacity} 分钟，因此优先解释风险和高价值保护。"
            )
        elif capacity:
            summary = (
                f"Planning Engine 将 {factors['task_count']} 个主序列任务压在约 {selected_minutes} 分钟内，"
                f"容量参考为 {capacity} 分钟。"
            )
        else:
            summary = f"Planning Engine 用价值、截止时间、依赖和任务大小为 {factors['task_count']} 个任务生成执行顺序。"

        signals: list[dict] = []
        if factors["over_capacity_minutes"]:
            signals.append(
                {
                    "key": "capacity_overload",
                    "title": "受保护任务偏重",
                    "message": f"主执行序列超过容量约 {factors['over_capacity_minutes']} 分钟，建议先完成第一项再决定是否拉回其他任务。",
                    "signal": "risk",
                    "score": factors["over_capacity_minutes"],
                }
            )
        elif factors["rolled_over_count"]:
            signals.append(
                {
                    "key": "capacity_rollover",
                    "title": "容量保护生效",
                    "message": f"{factors['rolled_over_count']} 个任务被滚动到未来，避免今天的主序列变得不可执行。",
                    "signal": "watch",
                    "score": factors["rolled_over_count"],
                }
            )
        if factors["pinned_count"]:
            signals.append(
                {
                    "key": "high_value_protection",
                    "title": "高价值优先",
                    "message": f"{factors['pinned_count']} 个任务被放入保护区，优先处理重要或紧急事项。",
                    "signal": "positive",
                    "score": factors["pinned_count"],
                }
            )
        if factors["dependency_protected_count"]:
            signals.append(
                {
                    "key": "dependency_order",
                    "title": "依赖顺序保护",
                    "message": f"{factors['dependency_protected_count']} 个前置任务被提前，减少后续任务被卡住的风险。",
                    "signal": "info",
                    "score": factors["dependency_protected_count"],
                }
            )
        if factors["goal_next_action_count"]:
            signals.append(
                {
                    "key": "goal_next_action",
                    "title": "目标下一步保护",
                    "message": f"{factors['goal_next_action_count']} 个目标各自保留了一个最适合今天推进的下一步。",
                    "signal": "positive",
                    "score": factors["goal_next_action_count"],
                }
            )
        if factors.get("goal_progress_signal_count"):
            signals.append(
                {
                    "key": "goal_progress_strategy",
                    "title": "目标进度压力",
                    "message": f"{factors['goal_progress_signal_count']} 个目标下一步读取了目标完成率、剩余任务和截止压力。",
                    "signal": "watch",
                    "score": factors["goal_progress_signal_count"],
                }
            )
        if factors["user_adjusted_count"]:
            signals.append(
                {
                    "key": "user_adjustment",
                    "title": "用户修正已读取",
                    "message": f"{factors['user_adjusted_count']} 个任务使用了你的优先级修正，排序仍保留可校正性。",
                    "signal": "positive",
                    "score": factors["user_adjusted_count"],
                }
            )
        if factors["semantic_signal_count"]:
            signals.append(
                {
                    "key": "semantic_planning_signal",
                    "title": "语义信号已读取",
                    "message": f"{factors['semantic_signal_count']} 个任务带有语义规划信号，排序会参考目标对齐、复杂度和最小推进动作。",
                    "signal": "info",
                    "score": factors["semantic_signal_count"],
                }
            )
        if factors["minimum_viable_progress_count"]:
            signals.append(
                {
                    "key": "minimum_viable_progress",
                    "title": "最小推进动作",
                    "message": f"{factors['minimum_viable_progress_count']} 个高价值大任务只保护今天能完成的最小推进动作。",
                    "signal": "positive",
                    "score": factors["minimum_viable_progress_count"],
                }
            )
        if factors["execution_feedback_count"]:
            signals.append(
                {
                    "key": "execution_feedback",
                    "title": "执行反馈校准",
                    "message": f"{factors['execution_feedback_count']} 个任务根据实际投入时间校准了今日剩余估时。",
                    "signal": "info",
                    "score": factors["execution_feedback_count"],
                }
            )
        if factors.get("personalization_signal_count"):
            signals.append(
                {
                    "key": "personalization_signal",
                    "title": "个人执行画像",
                    "message": f"{factors['personalization_signal_count']} 个任务读取了同类任务的历史执行节奏，用来调整估时和排序力度。",
                    "signal": "info",
                    "score": factors["personalization_signal_count"],
                }
            )
        if factors["energy_applied"]:
            signals.append(
                {
                    "key": "energy_fit",
                    "title": "精力信号已应用",
                    "message": f"今日精力为 {factors['energy_level']}，已影响容量保护或任务适配分。",
                    "signal": "info",
                    "score": None,
                }
            )
        if not signals and task_rationales:
            dominant = task_rationales[0].get("dominant_reason") or strategy.primary_reason
            signals.append(
                {
                    "key": "balanced_order",
                    "title": "稳定排序",
                    "message": dominant,
                    "signal": "info",
                    "score": None,
                }
            )

        return {
            "summary": summary,
            "signals": signals[:4],
            "source": "planning-engine-score-breakdown-v1",
        }

    def _strategy_energy_explanation(self, db: Session, *, plan: DailyPlan) -> dict:
        strategy = self._current_strategy(db, plan=plan)
        dashboard = energy_service.get_dashboard(db, user_id=plan.user_id, end_date=plan.plan_date, days=1)
        summary = dashboard["summary"]
        task_match = dashboard["task_match"]
        has_data = dashboard["trends"][0]["has_data"]
        applied_to_plan = bool(strategy.score_factors.get("energy_applied") or False)
        level = summary["energy_level"]
        if not has_data:
            explanation = "今天没有精力数据，排序仍只基于任务价值、截止时间和依赖。"
        elif level == "low":
            explanation = "今天精力偏低，Planning Engine 会降低容量，并优先选择更轻量的任务。"
        elif level == "high":
            explanation = "今天精力较好，Planning Engine 会给高价值或较深的任务更高适配分。"
        else:
            explanation = "今天精力状态可用，Planning Engine 会保持稳定容量和执行节奏。"
        return {
            "has_data": has_data,
            "metric_date": plan.plan_date,
            "energy_score": summary["energy_score"],
            "energy_level": level,
            "recommended_mode": task_match["recommended_mode"],
            "explanation": explanation,
            "applied_to_plan": applied_to_plan,
            "source": "energy_daily_metric" if has_data else "none",
        }

    def _strategy_factors(self, *, plan: DailyPlan, items: list[DailyPlanItem], score_factors: dict) -> dict:
        counted_items = [item for item in items if item.section != DailyPlanItemSection.ROLLED_OVER]
        daily_capacity_minutes = int(score_factors.get("daily_capacity_minutes", 0) or 0)
        selected_estimated_minutes = int(
            score_factors.get("selected_estimated_minutes", plan.total_estimated_minutes) or 0
        )
        over_capacity_minutes = int(
            score_factors.get(
                "over_capacity_minutes",
                self._over_capacity_minutes(
                    selected_minutes=selected_estimated_minutes,
                    daily_capacity_minutes=daily_capacity_minutes,
                ),
            )
            or 0
        )
        capacity_status = str(
            score_factors.get("capacity_status")
            or ("overloaded" if over_capacity_minutes else "within_capacity")
        )
        return {
            "task_count": int(score_factors.get("task_count", len(counted_items)) or 0),
            "high_value_task_count": len(
                [item for item in counted_items if item.task.value_level == ValueLevel.HIGH]
            ),
            "pinned_count": int(
                score_factors.get(
                    "pinned_count",
                    len([item for item in counted_items if item.section == DailyPlanItemSection.PINNED]),
                )
                or 0
            ),
            "recommended_count": len(
                [item for item in counted_items if item.section == DailyPlanItemSection.RECOMMENDED]
            ),
            "low_priority_count": len(
                [item for item in counted_items if item.section == DailyPlanItemSection.LOW_PRIORITY]
            ),
            "rolled_over_count": len([item for item in items if item.section == DailyPlanItemSection.ROLLED_OVER]),
            "total_estimated_minutes": int(score_factors.get("total_minutes", plan.total_estimated_minutes) or 0),
            "daily_capacity_minutes": daily_capacity_minutes,
            "selected_estimated_minutes": selected_estimated_minutes,
            "rolled_over_estimated_minutes": int(score_factors.get("rolled_over_estimated_minutes", 0) or 0),
            "over_capacity_minutes": over_capacity_minutes,
            "capacity_status": capacity_status,
            "dependency_protected_count": int(score_factors.get("dependency_protected_count", 0) or 0),
            "goal_next_action_count": int(score_factors.get("goal_next_action_count", 0) or 0),
            "goal_progress_signal_count": int(score_factors.get("goal_progress_signal_count", 0) or 0),
            "user_adjusted_count": int(score_factors.get("user_adjusted_count", 0) or 0),
            "semantic_signal_count": int(score_factors.get("semantic_signal_count", 0) or 0),
            "semantic_protected_count": int(score_factors.get("semantic_protected_count", 0) or 0),
            "minimum_viable_progress_count": int(score_factors.get("minimum_viable_progress_count", 0) or 0),
            "execution_feedback_count": int(score_factors.get("execution_feedback_count", 0) or 0),
            "personalization_signal_count": int(score_factors.get("personalization_signal_count", 0) or 0),
            "energy_level": str(score_factors.get("energy_level") or "unknown"),
            "energy_applied": bool(score_factors.get("energy_applied") or False),
            "planner_agent_latency_ms": score_factors.get("planner_agent_latency_ms"),
            "planner_agent_failure_type": score_factors.get("planner_agent_failure_type"),
            "completed_count": plan.completed_count,
            "focus_minutes": plan.focus_minutes,
        }

    def _strategy_explanation(self, *, strategy: StrategySnapshot, factors: dict) -> list[str]:
        explanation = [strategy.primary_reason]
        if factors["over_capacity_minutes"]:
            explanation.append(
                f"今天受保护任务已超过容量约 {factors['over_capacity_minutes']} 分钟，先完成一个高价值任务再决定是否拉回滚动任务。"
            )
        if factors["pinned_count"]:
            explanation.append(f"{factors['pinned_count']} 个任务被保护在前面，因为它们更重要或更紧急。")
        if factors["rolled_over_count"]:
            explanation.append(f"{factors['rolled_over_count']} 个任务被滚动到未来，避免挤占今天的主执行序列。")
        if factors["daily_capacity_minutes"]:
            explanation.append(
                f"今天主序列约 {factors['selected_estimated_minutes']} 分钟，容量参考为 {factors['daily_capacity_minutes']} 分钟。"
            )
        if factors["dependency_protected_count"]:
            explanation.append(f"{factors['dependency_protected_count']} 个前置任务被提前，用来保护任务依赖顺序。")
        if factors["goal_next_action_count"]:
            explanation.append(f"{factors['goal_next_action_count']} 个目标各自保留了一个下一步行动，避免高价值方向被单个任务列表挤掉。")
        if factors.get("goal_progress_signal_count"):
            explanation.append(f"{factors['goal_progress_signal_count']} 个目标下一步读取了目标完成率和剩余压力，让 Today 更像是在推进目标，而不是只排任务。")
        if factors["user_adjusted_count"]:
            explanation.append(f"{factors['user_adjusted_count']} 个任务读取了你的优先级修正，让 AI 判断保持可校正。")
        if factors["semantic_signal_count"]:
            explanation.append(f"{factors['semantic_signal_count']} 个任务读取了语义规划信号，用来理解目标对齐、复杂度和最小推进动作。")
        if factors["minimum_viable_progress_count"]:
            explanation.append(f"{factors['minimum_viable_progress_count']} 个高价值大任务只安排最小推进动作，避免 Today 变成不可执行清单。")
        if factors["execution_feedback_count"]:
            explanation.append(f"{factors['execution_feedback_count']} 个任务读取了真实执行时间，用来校准下一轮剩余估时。")
        if factors.get("personalization_signal_count"):
            explanation.append(f"{factors['personalization_signal_count']} 个任务读取了你的同类任务历史表现，用来让 Today 更贴近你的真实执行节奏。")
        if strategy.mode == PlanningPreference.LIGHT:
            explanation.append("今天保持轻量，让第一个动作更容易开始。")
        elif strategy.mode == PlanningPreference.SPRINT:
            explanation.append("今天使用冲刺模式，因为重要任务较多，需要更明确的顺序。")
        else:
            explanation.append("今天会平衡价值、截止时间和任务大小，不把 Today 变成复杂驾驶舱。")
        return explanation[:4]

    def _run_strategy_explanation_agent(
        self,
        db: Session,
        *,
        plan: DailyPlan,
        strategy: StrategySnapshot,
        factors: dict,
        score_explanation: dict,
        task_rationales: list[dict],
    ) -> dict:
        fallback_explanation = self._strategy_explanation(strategy=strategy, factors=factors)
        provider = llm_provider_registry.current_provider()
        job = ai_job_service.create_job(
            db,
            user_id=plan.user_id,
            job_type=AIJobType.STRATEGY_EXPLANATION,
            input_entity_type=EntityType.DAILY_PLAN.value,
            input_entity_id=plan.id,
            provider=provider.provider_name,
            model=provider.model_name,
            prompt_version=self.strategy_explanation_agent.prompt_version,
            metadata={
                "mode": "sync_structured_agent",
                "strategy_snapshot_id": str(strategy.id),
                "prompt_checksum": self.strategy_explanation_agent.prompt_checksum,
                "fallback_generator": "rule-strategy-explanation-v1",
            },
            commit=False,
        )
        job.status = AIJobStatus.RUNNING
        job.started_at = utc_now()
        started = perf_counter()

        try:
            agent_result = self.strategy_explanation_agent.run(
                strategy_context={
                    "daily_plan_id": str(plan.id),
                    "plan_date": plan.plan_date.isoformat(),
                    "strategy_snapshot_id": str(strategy.id),
                    "summary": strategy.summary,
                    "mode": strategy.mode.value,
                    "primary_reason": strategy.primary_reason,
                    "score_explanation": score_explanation,
                },
                factors=factors,
                task_rationales=self._strategy_explanation_task_context(task_rationales),
                fallback_output={
                    "explanation": fallback_explanation,
                    "confidence": 0.68,
                    "summary": strategy.summary,
                },
                provider=provider,
            )
            explanation = self._clean_strategy_explanation(agent_result.output)
            job.provider = agent_result.provider
            job.model = agent_result.model
            job.prompt_version = agent_result.prompt_version
            job.status = AIJobStatus.SUCCEEDED
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": True,
                "line_count": len(explanation),
                "confidence": agent_result.output.confidence,
                "prompt_checksum": agent_result.prompt_checksum,
                "provider_response_id": agent_result.response_id,
                "usage": agent_result.usage,
                "summary": agent_result.output.summary,
            }
        except Exception as exc:  # noqa: BLE001 - explanation must not block Strategy Detail.
            explanation = fallback_explanation
            job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
            job.error_message = str(exc)
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": False,
                "fallback_reason": self._strategy_explanation_fallback_reason(exc),
                "fallback_error_type": exc.__class__.__name__,
                "fallback_root_error_type": self._root_error_type(exc),
                "failure_type": self._planner_failure_type(exc),
            }

        job.result_entity_type = "strategy_snapshot"
        job.result_entity_id = strategy.id
        job.finished_at = utc_now()
        job.latency_ms = max(0, int((perf_counter() - started) * 1000))
        job.job_metadata = {
            **job.job_metadata,
            "provider_latency_ms": job.latency_ms,
            "provider_observability_version": "v1",
            "usage": self._planner_usage_metadata(job.job_metadata.get("usage")),
        }
        db.flush()
        db.commit()
        db.refresh(job)
        return {
            "explanation": explanation,
            "ai_job_id": str(job.id),
            "model_name": job.model,
            "prompt_version": job.prompt_version,
            "status": job.status.value,
        }

    def _strategy_explanation_task_context(self, task_rationales: list[dict]) -> list[dict]:
        return [
            {
                "task_id": str(item["task_id"]),
                "title": item["title"],
                "section": item["section"].value if hasattr(item["section"], "value") else item["section"],
                "sort_order": item["sort_order"],
                "recommendation_reason": item["recommendation_reason"],
                "estimated_duration_min": item["estimated_duration_min"],
                "priority": item["priority"],
                "value_level": item["value_level"].value if hasattr(item["value_level"], "value") else item["value_level"],
                "deadline": item["deadline"].isoformat() if item["deadline"] else None,
                "score_breakdown": item["score_breakdown"],
                "dominant_factor": item.get("dominant_factor"),
                "dominant_reason": item.get("dominant_reason"),
                "score_signals": item.get("score_signals") or [],
            }
            for item in task_rationales[:8]
        ]

    def _clean_strategy_explanation(self, output: StrategyExplanationOutput) -> list[str]:
        lines = [" ".join(line.strip().split()) for line in output.explanation]
        cleaned = [line for line in lines if line]
        if not cleaned:
            raise ValueError("Strategy explanation agent returned no usable explanation")
        return cleaned[:4]

    def _strategy_explanation_fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, ValueError):
            return "strategy_explanation_agent_invalid_output"
        return "strategy_explanation_agent_failed"

    def _over_capacity_minutes(self, *, selected_minutes: int, daily_capacity_minutes: int) -> int:
        if daily_capacity_minutes <= 0:
            return 0
        return max(selected_minutes - daily_capacity_minutes, 0)

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
            "score_breakdown": item.score_breakdown or {},
        }

    def _strategy_task_rationale_response(self, item: DailyPlanItem) -> dict:
        response = self._item_response(item)
        score_signals = self._task_score_signals(task=item.task, score_breakdown=response["score_breakdown"])
        dominant = score_signals[0]
        return {
            **response,
            "dominant_factor": dominant["key"],
            "dominant_reason": dominant["message"],
            "score_signals": score_signals[:4],
        }

    def _task_score_signals(self, *, task: Task, score_breakdown: dict) -> list[dict]:
        signals: list[dict] = []
        rollover_reason = score_breakdown.get("rollover_reason")
        if rollover_reason == "capacity":
            signals.append(
                {
                    "key": "capacity_rollover",
                    "title": "滚动到未来",
                    "message": "今日容量已优先留给更高价值或更紧急的主序列任务。",
                    "signal": "watch",
                    "score": None,
                }
            )
        elif rollover_reason == "postponed":
            signals.append(
                {
                    "key": "user_postponed",
                    "title": "已延后",
                    "message": "该任务保持可见，但不会重新挤入今天的主执行序列。",
                    "signal": "info",
                    "score": None,
                }
            )

        urgency_score = int(score_breakdown.get("urgency_score") or 0)
        if urgency_score >= 30:
            signals.append(
                {
                    "key": "overdue_deadline",
                    "title": "已超期",
                    "message": "任务已超过截止时间，因此被提升到更靠前的位置。",
                    "signal": "risk",
                    "score": urgency_score,
                }
            )
        elif urgency_score >= 24:
            signals.append(
                {
                    "key": "due_today",
                    "title": "今天截止",
                    "message": "任务今天截止，因此需要在轻量事务前处理。",
                    "signal": "risk",
                    "score": urgency_score,
                }
            )
        elif urgency_score > 0:
            signals.append(
                {
                    "key": "deadline_soon",
                    "title": "截止时间接近",
                    "message": "截止时间较近，因此排序会适度提前。",
                    "signal": "watch",
                    "score": urgency_score,
                }
            )

        goal_urgency_score = int(score_breakdown.get("goal_urgency_score") or 0)
        if goal_urgency_score > 0:
            signals.append(
                {
                    "key": "goal_deadline",
                    "title": "目标节点接近",
                    "message": "关联目标的截止时间正在接近，系统会保护它的下一步行动。",
                    "signal": "watch",
                    "score": goal_urgency_score,
                }
            )

        dependency_score = int(score_breakdown.get("dependency_score") or 0)
        if dependency_score > 0:
            signals.append(
                {
                    "key": "dependency_unlock",
                    "title": "前置任务",
                    "message": "完成它可以解锁后续任务，因此被放到更靠前的位置。",
                    "signal": "positive",
                    "score": dependency_score,
                }
            )
        elif dependency_score < 0:
            signals.append(
                {
                    "key": "dependency_wait",
                    "title": "等待前置任务",
                    "message": "该任务依赖前置事项，排序会避免它过早进入主行动。",
                    "signal": "info",
                    "score": dependency_score,
                }
            )

        user_preference_score = int(score_breakdown.get("user_preference_score") or 0)
        if user_preference_score > 0:
            signals.append(
                {
                    "key": "user_adjustment",
                    "title": "用户修正",
                    "message": "你的优先级或策略偏好已经进入本次排序。",
                    "signal": "positive",
                    "score": user_preference_score,
                }
            )

        if score_breakdown.get("minimum_viable_progress_applied"):
            signals.append(
                {
                    "key": "minimum_viable_progress",
                    "title": "最小推进动作",
                    "message": "任务本身偏大，Today 只保护一个今天做得出来的推进切片。",
                    "signal": "positive",
                    "score": score_breakdown.get("planned_duration_min"),
                }
            )

        if score_breakdown.get("execution_feedback_applied"):
            reason = score_breakdown.get("execution_feedback_reason")
            if reason == "actual_duration_overrun":
                message = "这个任务已经超过原估时但还没完成，Today 先按较小推进块继续安排。"
            elif reason == "task_progress_remaining":
                message = "这个任务已有部分进度，Today 按剩余进度重新估算时长。"
            else:
                message = "这个任务已经投入过时间，Today 按剩余工作量重新估算时长。"
            signals.append(
                {
                    "key": "execution_feedback",
                    "title": "执行反馈校准",
                    "message": message,
                    "signal": "info",
                    "score": score_breakdown.get("remaining_estimated_duration_min"),
                }
            )

        if score_breakdown.get("personalization_applied"):
            task_type = score_breakdown.get("personalization_task_type") or "同类"
            multiplier = float(score_breakdown.get("personalization_duration_multiplier") or 1.0)
            if score_breakdown.get("personalization_overrun_risk"):
                message = f"你过去的 {task_type} 类任务常超出估时，Today 已按更保守的时长安排。"
                signal = "watch"
            elif score_breakdown.get("personalization_interruption_risk") or score_breakdown.get("personalization_postponement_risk"):
                message = f"你过去的 {task_type} 类任务更容易中断或延后，排序会降低它抢占主序列的力度。"
                signal = "watch"
            elif score_breakdown.get("personalization_completion_momentum"):
                message = f"你过去的 {task_type} 类任务完成反馈较好，Today 会保留这个顺手推进的机会。"
                signal = "positive"
            else:
                message = f"Today 参考了你过去 {task_type} 类任务的执行节奏。"
                signal = "info"
            signals.append(
                {
                    "key": "personalization_signal",
                    "title": "个人执行画像",
                    "message": message,
                    "signal": signal,
                    "score": int(round(multiplier * 100)),
                }
            )

        semantic_total_score = int(score_breakdown.get("semantic_total_score") or 0)
        if score_breakdown.get("semantic_signal_applied") and semantic_total_score > 0:
            minimum_step = score_breakdown.get("semantic_minimum_viable_step")
            message = "语义信号认为它和目标推进、复杂度或阻塞风险相关，因此会影响今日排序。"
            if minimum_step:
                message = f"语义信号建议先推进最小动作：{minimum_step}"
            signals.append(
                {
                    "key": "semantic_planning",
                    "title": "语义规划信号",
                    "message": message,
                    "signal": "info" if semantic_total_score < 28 else "positive",
                    "score": semantic_total_score,
                }
            )

        goal_progress_score = int(score_breakdown.get("goal_progress_score") or 0)
        if score_breakdown.get("goal_progress_applied") and goal_progress_score > 0:
            reason_key = score_breakdown.get("goal_progress_reason_key")
            completion_rate = float(score_breakdown.get("goal_progress_completion_rate") or 0.0)
            unfinished_count = int(score_breakdown.get("goal_progress_unfinished_task_count") or 0)
            if reason_key == "goal_completion_closure":
                message = f"关联目标已完成约 {int(completion_rate * 100)}%，剩余 {unfinished_count} 个任务，Today 会保护这个收口动作。"
                signal = "positive"
            elif reason_key in {"goal_progress_overdue", "goal_progress_deadline_risk", "goal_progress_deadline_watch"}:
                message = "关联目标完成率偏低且截止压力较高，这个下一步被提前保护。"
                signal = "watch"
            elif reason_key in {"high_value_goal_under_progress", "high_value_goal_needs_progress"}:
                message = "高价值目标当前推进不足，系统会优先保护它的下一步。"
                signal = "watch"
            else:
                message = "系统读取了目标完成率、剩余任务和截止压力，确认这是今天值得推进的目标下一步。"
                signal = "info"
            signals.append(
                {
                    "key": "goal_progress_strategy",
                    "title": "目标进度策略",
                    "message": message,
                    "signal": signal,
                    "score": goal_progress_score,
                }
            )

        goal_next_action_score = int(score_breakdown.get("goal_next_action_score") or 0)
        if goal_next_action_score > 0:
            signals.append(
                {
                    "key": "goal_next_action",
                    "title": "目标下一步",
                    "message": "这是关联目标当前最适合推进的下一步，系统会保护它不被零散任务挤掉。",
                    "signal": "positive",
                    "score": goal_next_action_score,
                }
            )

        value_score = int(score_breakdown.get("value_score") or 0)
        if value_score >= 30:
            signals.append(
                {
                    "key": "high_value_task",
                    "title": "高价值任务",
                    "message": "这是高价值任务，系统会避免它被低价值事项挤掉。",
                    "signal": "positive",
                    "score": value_score,
                }
            )

        goal_value_score = int(score_breakdown.get("goal_value_score") or 0)
        if goal_value_score >= 12:
            signals.append(
                {
                    "key": "high_value_goal",
                    "title": "高价值目标",
                    "message": "它服务于高价值目标，因此下一步行动会被适度保护。",
                    "signal": "positive",
                    "score": goal_value_score,
                }
            )

        priority_score = int(score_breakdown.get("priority_score") or 0)
        if priority_score >= 16:
            signals.append(
                {
                    "key": "manual_priority",
                    "title": "高优先级",
                    "message": "任务优先级较高，因此排序更靠前。",
                    "signal": "positive",
                    "score": priority_score,
                }
            )

        energy_fit_score = int(score_breakdown.get("energy_fit_score") or 0)
        if score_breakdown.get("energy_applied") and energy_fit_score > 0:
            signals.append(
                {
                    "key": "energy_fit",
                    "title": "匹配今日精力",
                    "message": f"任务形态匹配今日 {score_breakdown.get('energy_level', 'unknown')} 精力状态。",
                    "signal": "info",
                    "score": energy_fit_score,
                }
            )
        elif score_breakdown.get("energy_applied") and energy_fit_score < 0:
            signals.append(
                {
                    "key": "energy_mismatch",
                    "title": "精力匹配偏弱",
                    "message": "任务偏重，不太适合当前精力状态，因此分数被压低。",
                    "signal": "watch",
                    "score": energy_fit_score,
                }
            )

        behavior_feedback_score = int(score_breakdown.get("behavior_feedback_score") or 0)
        if behavior_feedback_score < 0:
            signals.append(
                {
                    "key": "behavior_drag",
                    "title": "历史执行阻力",
                    "message": "近期延后或中断较多，系统会降低它进入主序列的力度。",
                    "signal": "watch",
                    "score": behavior_feedback_score,
                }
            )
        elif behavior_feedback_score > 0:
            signals.append(
                {
                    "key": "behavior_momentum",
                    "title": "执行势能",
                    "message": "近期完成反馈较好，排序会保留这个正向势能。",
                    "signal": "positive",
                    "score": behavior_feedback_score,
                }
            )

        duration_fit_score = int(score_breakdown.get("duration_fit_score") or 0)
        if duration_fit_score < 0:
            signals.append(
                {
                    "key": "heavy_duration",
                    "title": "任务偏重",
                    "message": "预计耗时较长，系统会结合容量判断是否放入主序列。",
                    "signal": "watch",
                    "score": duration_fit_score,
                }
            )
        elif duration_fit_score > 0 and task.value_level != ValueLevel.HIGH:
            signals.append(
                {
                    "key": "duration_fit",
                    "title": "容易开始",
                    "message": "任务耗时适中，适合作为今天可执行序列的一部分。",
                    "signal": "info",
                    "score": duration_fit_score,
                }
            )

        if not signals:
            signals.append(
                {
                    "key": "balanced_order",
                    "title": "平衡排序",
                    "message": "该任务按价值、截止时间、优先级和任务大小综合排序。",
                    "signal": "info",
                    "score": int(score_breakdown.get("total_score") or 0),
                }
            )
        return signals

    def _insights_preview(self, *, plan: DailyPlan, items: list[DailyPlanItem], progress: dict) -> dict:
        active_items = [
            item
            for item in items
            if item.section != DailyPlanItemSection.ROLLED_OVER
            and item.status
            not in {DailyPlanItemStatus.COMPLETED, DailyPlanItemStatus.SKIPPED, DailyPlanItemStatus.POSTPONED}
        ]
        remaining_minutes = sum(item.estimated_duration_min or item.task.estimated_duration_min or 25 for item in active_items)
        risk_alerts = self._today_risk_alerts(plan=plan, items=active_items)
        return {
            "risk_alerts": risk_alerts,
            "remaining_time_suggestion": self._remaining_time_suggestion(remaining_minutes=remaining_minutes),
            "adjustment_suggestions": self._today_adjustment_suggestions(
                items=items,
                active_items=active_items,
                risk_alerts=risk_alerts,
                progress=progress,
            ),
            "source": "rule-today-insights-v1",
        }

    def _today_risk_alerts(self, *, plan: DailyPlan, items: list[DailyPlanItem]) -> list[dict]:
        alerts: list[dict] = []
        for item in items:
            task = item.task
            if task.deadline is None:
                continue
            if task.deadline < plan.plan_date:
                alerts.append(
                    {
                        "key": "overdue_task",
                        "title": "Overdue task needs protection",
                        "message": f"{task.title} is past its deadline. Keep it near the front if it still matters.",
                        "signal": "risk",
                        "task_id": task.id,
                    }
                )
            elif task.deadline == plan.plan_date and task.value_level == ValueLevel.HIGH:
                alerts.append(
                    {
                        "key": "high_value_due_today",
                        "title": "High-value task is due today",
                        "message": f"{task.title} should stay protected before lighter work.",
                        "signal": "risk",
                        "task_id": task.id,
                    }
                )
        capacity_alert = self._today_capacity_alert(items=items)
        if capacity_alert is not None:
            alerts.append(capacity_alert)
        return alerts[:3]

    def _today_capacity_alert(self, *, items: list[DailyPlanItem]) -> dict | None:
        if not items:
            return None
        daily_capacity_minutes = int((items[0].score_breakdown or {}).get("daily_capacity_minutes") or 0)
        selected_minutes = sum(item.estimated_duration_min or item.task.estimated_duration_min or 25 for item in items)
        over_capacity_minutes = self._over_capacity_minutes(
            selected_minutes=selected_minutes,
            daily_capacity_minutes=daily_capacity_minutes,
        )
        if not over_capacity_minutes:
            return None
        return {
            "key": "main_sequence_over_capacity",
            "title": "Main sequence is heavy",
            "message": (
                f"Protected work is about {over_capacity_minutes} minutes over today's capacity. "
                "Finish one high-value task before pulling more work in."
            ),
            "signal": "risk",
            "task_id": None,
        }

    def _remaining_time_suggestion(self, *, remaining_minutes: int) -> dict:
        if remaining_minutes == 0:
            message = "No active planned work is left in the main sequence."
            signal = "positive"
        elif remaining_minutes <= 75:
            message = "The remaining plan is light enough to keep a calm pace."
            signal = "positive"
        elif remaining_minutes >= 180:
            message = "The remaining plan is heavy. Finish one protected task before deciding what to move."
            signal = "risk"
        else:
            message = "There is a steady block of work left. Keep the current order and avoid reshuffling too early."
            signal = "neutral"
        return {
            "key": "remaining_time",
            "title": "Remaining time",
            "message": message,
            "signal": signal,
            "task_id": None,
        }

    def _today_adjustment_suggestions(
        self,
        *,
        items: list[DailyPlanItem],
        active_items: list[DailyPlanItem],
        risk_alerts: list[dict],
        progress: dict,
    ) -> list[dict]:
        suggestions: list[dict] = []
        rolled_over_count = len([item for item in items if item.section == DailyPlanItemSection.ROLLED_OVER])
        if rolled_over_count:
            suggestions.append(
                {
                    "key": "rolled_over_visible",
                    "title": "Postponed work is visible",
                    "message": f"{rolled_over_count} postponed tasks are visible, but they do not need to lead the day.",
                    "signal": "neutral",
                    "task_id": None,
                }
            )
        if risk_alerts:
            suggestions.append(
                {
                    "key": "protect_risk_task",
                    "title": "Protect the risky item first",
                    "message": "Handle the first risk item before adding new work.",
                    "signal": "risk",
                    "task_id": risk_alerts[0]["task_id"],
                }
            )
        elif active_items and progress["completed_count"] == 0:
            first_item = active_items[0]
            suggestions.append(
                {
                    "key": "start_first_action",
                    "title": "Start with the first action",
                    "message": f"Begin with {first_item.task.title}; avoid replanning before one concrete step is done.",
                    "signal": "neutral",
                    "task_id": first_item.task_id,
                }
            )
        elif progress["completion_rate"] >= 0.8:
            suggestions.append(
                {
                    "key": "close_the_loop",
                    "title": "Close the loop",
                    "message": "Most planned work is done. Review the day before pulling in more tasks.",
                    "signal": "positive",
                    "task_id": None,
                }
            )
        return suggestions[:3]

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
                progress_delta = self.minimum_viable_progress_delta_for_item(item)
                if progress_delta is None:
                    task_service.complete_task(
                        db,
                        task_id=item.task_id,
                        user_id=user_id,
                        related_daily_plan_id=plan.id,
                        commit=False,
                    )
                else:
                    task_service.record_partial_progress(
                        db,
                        task_id=item.task_id,
                        user_id=user_id,
                        related_daily_plan_id=plan.id,
                        progress_delta=progress_delta,
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

    def _current_item_for_task(
        self,
        db: Session,
        *,
        plan: DailyPlan,
        task_id: uuid.UUID,
    ) -> DailyPlanItem | None:
        if plan.current_revision_id is None:
            return None
        stmt = (
            select(DailyPlanItem)
            .where(
                DailyPlanItem.daily_plan_id == plan.id,
                DailyPlanItem.plan_revision_id == plan.current_revision_id,
                DailyPlanItem.task_id == task_id,
            )
            .order_by(DailyPlanItem.sort_order)
        )
        return db.scalars(stmt).first()

    def _today_impact_response(
        self,
        *,
        plan: DailyPlan,
        item: DailyPlanItem | None,
        plan_date: date,
        replanned: bool,
        reason: str,
    ) -> dict:
        return {
            "plan_date": plan_date,
            "plan_exists": True,
            "replanned": replanned,
            "daily_plan_id": plan.id,
            "plan_version": plan.current_version,
            "daily_plan_item_id": item.id if item else None,
            "task_in_today": item is not None,
            "section": item.section if item else None,
            "item_status": item.status if item else None,
            "reason": reason,
        }

    def _no_active_today_impact(self, *, plan_date: date) -> dict:
        return {
            "plan_date": plan_date,
            "plan_exists": False,
            "replanned": False,
            "daily_plan_id": None,
            "plan_version": None,
            "daily_plan_item_id": None,
            "task_in_today": False,
            "section": None,
            "item_status": None,
            "reason": "no_active_today_plan",
        }

    def _current_strategy(self, db: Session, *, plan: DailyPlan) -> StrategySnapshot:
        stmt = select(StrategySnapshot).where(
            StrategySnapshot.daily_plan_id == plan.id,
            StrategySnapshot.plan_revision_id == plan.current_revision_id,
        )
        strategy = db.scalars(stmt).first()
        if strategy is None:
            raise InvalidStateError("Daily plan is missing strategy snapshot")
        return strategy

    def _current_revision(self, db: Session, *, plan: DailyPlan) -> PlanRevision:
        if plan.current_revision_id is None:
            raise InvalidStateError("Daily plan is missing current revision")
        revision = db.get(PlanRevision, plan.current_revision_id)
        if revision is None:
            raise InvalidStateError("Daily plan is missing current revision")
        return revision

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
