from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.agents.daily_planner import DailyPlannerAgent, daily_planner_agent
from app.ai.schemas.planning import DailyPlannerOutput
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
    PlanningPreference,
    PlanRevisionTrigger,
    TaskStatus,
    ValueLevel,
)
from app.models.mixins import utc_now
from app.models.task_dependency import TaskDependency
from app.models.task import Task
from app.models.user import User, UserSettings
from app.services.activity_event_service import activity_event_service
from app.services.ai_job_service import ai_job_service
from app.services.energy_service import energy_service
from app.services.errors import InvalidStateError, NotFoundError
from app.services.task_service import task_service


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
    def __init__(self, *, planner_agent: DailyPlannerAgent | None = None) -> None:
        self.planner_agent = planner_agent or daily_planner_agent

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
        stmt = select(Task).where(
            Task.user_id == user_id,
            Task.status.in_([TaskStatus.ACTIVE, TaskStatus.POSTPONED]),
        )
        tasks = list(db.scalars(stmt).all())
        context = self._planning_context(db, user_id=user_id, plan_date=plan_date)
        signals = self._planning_signals(db, user_id=user_id, tasks=tasks)
        scored_tasks: list[PlannedTask] = []
        for task in tasks:
            score_breakdown = self._score_breakdown_for(task, context=context, signals=signals)
            base_section = self._section_for(
                task,
                plan_date=plan_date,
                unlocking_task_ids=signals["unlocking_task_ids"],
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
                        score_breakdown=score_breakdown,
                    ),
                    estimated_duration_min=task.estimated_duration_min or 25,
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
        job = ai_job_service.create_job(
            db,
            user_id=plan.user_id,
            job_type=AIJobType.DAILY_PLANNER,
            input_entity_type=EntityType.DAILY_PLAN.value,
            input_entity_id=plan.id,
            provider="mock",
            model="structured-mock-v1",
            prompt_version=self.planner_agent.prompt_version,
            metadata={
                "mode": "sync_structured_shell",
                "plan_revision_id": str(revision.id),
                "candidate_count": len(planned_tasks),
                "planner_core": "planning-engine-v1",
            },
            commit=False,
        )
        job.status = AIJobStatus.RUNNING
        job.started_at = utc_now()

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
            }
        except Exception as exc:  # noqa: BLE001 - fallback is the product boundary here.
            fallback_reason = (
                "daily_planner_agent_invalid_output"
                if isinstance(exc, ValueError)
                else "daily_planner_agent_failed"
            )
            job.status = AIJobStatus.SUCCEEDED_WITH_FALLBACK
            job.error_message = str(exc)
            job.job_metadata = {
                **job.job_metadata,
                "output_applied": False,
                "fallback_reason": fallback_reason,
                "fallback_error_type": exc.__class__.__name__,
            }

        job.finished_at = utc_now()
        strategy_payload["score_factors"] = {
            **strategy_payload["score_factors"],
            "ai_job_id": str(job.id),
            "planner_agent_status": job.status.value,
            "planner_agent_provider": job.provider,
            "planner_agent_model": job.model,
            "planner_agent_prompt_version": job.prompt_version,
            "planner_agent_output_applied": job.job_metadata.get("output_applied", False),
        }
        return {"planned_tasks": planned_tasks, "strategy_payload": strategy_payload, "ai_job": job}

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
        }
        return applied_tasks, strategy_payload

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
        estimated_minutes = task.estimated_duration_min or 25
        behavior = signals["behavior_by_task_id"].get(
            task.id,
            {"completed": 0, "postponed": 0, "interrupted": 0},
        )
        value_score = {ValueLevel.HIGH: 30, ValueLevel.MEDIUM: 18, ValueLevel.LOW: 8}[task.value_level]
        urgency_score = self._urgency_score(task=task, plan_date=context.plan_date)
        dependency_score = 0
        if task.id in signals["unlocking_task_ids"]:
            dependency_score += 18
        if task.id in signals["blocked_task_ids"]:
            dependency_score -= 10
        duration_fit_score = self._duration_fit_score(estimated_minutes, capacity=context.daily_capacity_minutes)
        energy_fit_score = self._energy_fit_score(
            estimated_minutes,
            value_level=task.value_level,
            context=context,
        )
        behavior_feedback_score = min(behavior["completed"], 3) * 2
        behavior_feedback_score -= min(behavior["postponed"], 3) * 6
        behavior_feedback_score -= min(behavior["interrupted"], 3) * 4
        user_preference_score = 10 if task.id in signals["adjusted_task_ids"] else 0
        if context.ai_strategy_preference == AIStrategyPreference.HIGH_VALUE_FIRST and task.value_level == ValueLevel.HIGH:
            user_preference_score += 8
        if context.ai_strategy_preference == AIStrategyPreference.ENERGY_AWARE and context.energy_has_data:
            user_preference_score += max(energy_fit_score, 0) // 2
        postponement_penalty = -12 if task.status == TaskStatus.POSTPONED else 0
        priority_score = max(0, 6 - task.priority) * 4
        total_score = (
            value_score
            + urgency_score
            + dependency_score
            + duration_fit_score
            + energy_fit_score
            + behavior_feedback_score
            + user_preference_score
            + postponement_penalty
            + priority_score
        )
        return {
            "total_score": int(total_score),
            "value_score": int(value_score),
            "urgency_score": int(urgency_score),
            "dependency_score": int(dependency_score),
            "duration_fit_score": int(duration_fit_score),
            "energy_fit_score": int(energy_fit_score),
            "behavior_feedback_score": int(behavior_feedback_score),
            "user_preference_score": int(user_preference_score),
            "postponement_penalty": int(postponement_penalty),
            "priority_score": int(priority_score),
            "estimated_duration_min": int(estimated_minutes),
            "daily_capacity_minutes": int(context.daily_capacity_minutes),
            "energy_level": context.energy_level,
            "energy_applied": context.energy_has_data,
            "behavior": behavior,
        }

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

    def _planning_signals(self, db: Session, *, user_id: uuid.UUID, tasks: list[Task]) -> dict:
        task_by_id = {task.id: task for task in tasks}
        if not task_by_id:
            return {
                "dependency_depth_by_task_id": {},
                "unlocking_task_ids": set(),
                "blocked_task_ids": set(),
                "adjusted_task_ids": set(),
                "behavior_by_task_id": {},
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

        return {
            "dependency_depth_by_task_id": depth_by_task_id,
            "unlocking_task_ids": unlocking_task_ids,
            "blocked_task_ids": blocked_task_ids,
            "adjusted_task_ids": adjusted_task_ids,
            "behavior_by_task_id": behavior_by_task_id,
        }

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
    ) -> DailyPlanItemSection:
        if task.status == TaskStatus.POSTPONED:
            return DailyPlanItemSection.ROLLED_OVER
        if task.id in unlocking_task_ids:
            return DailyPlanItemSection.PINNED
        if task.deadline is not None and task.deadline <= plan_date:
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
        score_breakdown: dict,
    ) -> str:
        if task.status == TaskStatus.POSTPONED:
            return "Postponed item kept visible without pushing it back into the main sequence."
        if task.deadline is not None and task.deadline < plan_date:
            return "Overdue task protected at the top of today's sequence."
        if task.deadline == plan_date:
            return "Due today, so it is protected in the priority section."
        if task.id in unlocking_task_ids:
            return "Prerequisite task placed early because it unlocks another planned task."
        if task.id in blocked_task_ids:
            return "Dependent task kept after its prerequisite in today's sequence."
        if task.id in adjusted_task_ids:
            return "Adjusted by you, so the planner keeps that preference visible."
        if task.value_level == ValueLevel.HIGH:
            return "High-value task protected from being crowded out by lighter work."
        if task.priority <= 2:
            return "High-priority task placed early for a clearer start."
        if task.priority >= 4:
            return "Lower-priority task kept available after the main sequence."
        if score_breakdown.get("energy_applied") and score_breakdown.get("energy_fit_score", 0) > 0:
            return "Placed here because the task shape fits today's energy signal."
        return "Balanced task placed in the recommended execution order."

    def _planned_sort_key(self, planned: PlannedTask) -> tuple[int, int, int, int, int, int, date, int, int, datetime]:
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
        user_adjusted_count = len([planned for planned in active_tasks if planned.priority_adjusted])
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
                    "user_adjusted_count": 0,
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
                "user_adjusted_count": user_adjusted_count,
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
            "explanation": self._strategy_explanation(strategy=strategy, factors=factors),
            "energy": self._strategy_energy_explanation(db, plan=plan),
            "task_rationales": [self._item_response(item) for item in items],
            "source": {
                "strategy_snapshot_id": strategy.id,
                "ai_job_id": strategy.score_factors.get("ai_job_id"),
                "model_name": strategy.model_name,
                "prompt_version": strategy.prompt_version,
                "generated_at": strategy.created_at,
            },
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
            "user_adjusted_count": int(score_factors.get("user_adjusted_count", 0) or 0),
            "energy_level": str(score_factors.get("energy_level") or "unknown"),
            "energy_applied": bool(score_factors.get("energy_applied") or False),
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
        if factors["user_adjusted_count"]:
            explanation.append(f"{factors['user_adjusted_count']} 个任务读取了你的优先级修正，让 AI 判断保持可校正。")
        if strategy.mode == PlanningPreference.LIGHT:
            explanation.append("今天保持轻量，让第一个动作更容易开始。")
        elif strategy.mode == PlanningPreference.SPRINT:
            explanation.append("今天使用冲刺模式，因为重要任务较多，需要更明确的顺序。")
        else:
            explanation.append("今天会平衡价值、截止时间和任务大小，不把 Today 变成复杂驾驶舱。")
        return explanation[:4]

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
