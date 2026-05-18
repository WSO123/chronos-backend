from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from typing import Callable
import uuid


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.activity_event import ActivityEvent
from app.models.ai_job import AIJob
from app.models.enums import DailyPlanItemSection, DailyPlanItemStatus, EntityType, TaskStatus, ValueLevel
from app.models.task import Task
from app.models.task_planning_signal import TaskPlanningSignal
from app.services.energy_service import energy_service
from app.services.goal_service import goal_service
from app.services.planning_service import planning_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


PLAN_DATE = date(2026, 5, 17)
EVALUATOR_VERSION = "p2-planning-engine-eval-v10"


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    details: dict
    failures: list[str]


def run_evaluation(*, run_id: str | None = None) -> dict:
    resolved_run_id = run_id or str(uuid.uuid4())
    scenarios: list[Callable[[], ScenarioResult]] = [
        _scenario_capacity_rollover,
        _scenario_capacity_objective_protects_goal_progress,
        _scenario_protected_overload_warning,
        _scenario_low_energy_lightens_plan,
        _scenario_high_energy_prioritizes_deep_work_without_expansion,
        _scenario_dependency_chain_protection,
        _scenario_user_priority_adjustment_protection,
        _scenario_behavior_feedback_penalizes_interruptions,
        _scenario_multi_goal_competition_protects_high_value_goal,
        _scenario_overdue_goal_recovery_promotes_next_task,
        _scenario_goal_progress_strategy_closes_near_done_goal,
        _scenario_semantic_history_personalizes_duration,
        _scenario_execution_learning_calibrates_focus_history,
        _scenario_semantic_coverage_v2_guides_minimum_goal_action,
        _scenario_planner_feedback_preference_explained_without_reordering,
    ]
    results = [scenario() for scenario in scenarios]
    return {
        "run_id": resolved_run_id,
        "evaluator_version": EVALUATOR_VERSION,
        "status": "ok" if all(result.passed for result in results) else "failed",
        "scenario_count": len(results),
        "passed_count": len([result for result in results if result.passed]),
        "failed_count": len([result for result in results if not result.passed]),
        "scenarios": [asdict(result) for result in results],
    }


def _scenario_capacity_rollover() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Capacity")
        task_service.create_task(
            db,
            user_id=user.id,
            title="Protected deep work",
            estimated_duration_min=90,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        for index in range(3):
            task_service.create_task(
                db,
                user_id=user.id,
                title=f"Medium follow-up {index}",
                estimated_duration_min=60,
                priority=3,
                value_level=ValueLevel.MEDIUM,
            )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        rolled = today["sections"]["rolled_over_tasks"]
        failures = _check_all(
            ("two tasks stay in main sequence", today["progress"]["total_count"] == 2),
            ("two tasks roll over", len(rolled) == 2),
            ("capacity rollover keeps task active", bool(rolled) and rolled[0]["task_status"] == TaskStatus.ACTIVE),
            (
                "capacity rollover keeps item planned",
                bool(rolled) and rolled[0]["item_status"] == DailyPlanItemStatus.PLANNED,
            ),
            ("selected minutes equals capacity", strategy["factors"]["selected_estimated_minutes"] == 150),
            ("no overload when selected equals capacity", strategy["factors"]["over_capacity_minutes"] == 0),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="capacity_rollover",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_capacity_objective_protects_goal_progress() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Objective")
        goal = goal_service.create_goal(
            db,
            user_id=user.id,
            title="Ship P2 execution loop",
            deadline=PLAN_DATE + timedelta(days=21),
            value_level=ValueLevel.HIGH,
        )
        first_goal_step = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=goal.id,
            title="Stabilize Today planning core",
            estimated_duration_min=45,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        followup_goal_step = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=goal.id,
            title="Connect goal progress to next planning step",
            estimated_duration_min=45,
            priority=4,
            value_level=ValueLevel.MEDIUM,
        )
        admin_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Clear ordinary admin backlog",
            estimated_duration_min=45,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.replan_today(
            db,
            user_id=user.id,
            plan_date=PLAN_DATE,
            reason="Evaluate objective under short capacity",
            available_minutes=90,
        )
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        followup_item = _find_item(today, followup_goal_step.id)
        admin_item = _find_item(today, admin_task.id)
        failures = _check_all(
            ("first goal step is protected", first_goal_step.id in [item["task_id"] for item in today["sections"]["pinned_tasks"]]),
            (
                "followup high-value goal step enters remaining capacity",
                bool(followup_item) and _section_value(followup_item) == DailyPlanItemSection.LOW_PRIORITY.value,
            ),
            (
                "ordinary admin task rolls over",
                bool(admin_item) and _section_value(admin_item) == DailyPlanItemSection.ROLLED_OVER.value,
            ),
            (
                "objective selected the goal followup",
                bool(followup_item) and followup_item["score_breakdown"].get("planning_objective_selected") is True,
            ),
            (
                "objective rejected ordinary admin task",
                bool(admin_item) and admin_item["score_breakdown"].get("planning_objective_selected") is False,
            ),
            (
                "selected minutes equals manual capacity",
                strategy["factors"]["selected_estimated_minutes"] == 90,
            ),
            (
                "objective is exposed in Strategy Detail",
                strategy["factors"].get("planning_objective_version") == "p2-planning-objective-v2",
            ),
            (
                "objective explanation signal is visible",
                "planning_objective" in [signal["key"] for signal in strategy["score_explanation"]["signals"]],
            ),
            (
                "goal objective score beats admin objective score",
                bool(followup_item)
                and bool(admin_item)
                and followup_item["score_breakdown"].get("planning_objective_score", 0)
                > admin_item["score_breakdown"].get("planning_objective_score", 0),
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="capacity_objective_protects_goal_progress",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_protected_overload_warning() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Overload")
        for index in range(3):
            task_service.create_task(
                db,
                user_id=user.id,
                title=f"Protected overload {index}",
                estimated_duration_min=70,
                priority=1,
                value_level=ValueLevel.HIGH,
            )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        failures = _check_all(
            ("protected tasks stay selected", today["progress"]["total_count"] == 3),
            ("overload warning appears", strategy["factors"]["capacity_status"] == "overloaded"),
            ("overload minutes are explicit", strategy["factors"]["over_capacity_minutes"] == 60),
            (
                "today preview shows one light risk",
                today["insights_preview"]["risk_alerts"][0]["key"] == "main_sequence_over_capacity",
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="protected_overload_warning",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_low_energy_lightens_plan() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Low Energy")
        energy_service.upsert_daily_metric(
            db,
            user_id=user.id,
            payload={"metric_date": PLAN_DATE, "energy_score": 35},
        )
        light_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Small admin step",
            estimated_duration_min=20,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        long_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Long writing block",
            estimated_duration_min=75,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        recommended = today["sections"]["recommended_tasks"]
        rolled = today["sections"]["rolled_over_tasks"]
        failures = _check_all(
            ("low energy lowers capacity", strategy["factors"]["daily_capacity_minutes"] == 90),
            ("light task is first", bool(recommended) and recommended[0]["task_id"] == light_task.id),
            ("long task rolls over under low capacity", bool(rolled) and rolled[0]["task_id"] == long_task.id),
            ("energy was applied", strategy["factors"]["energy_applied"] is True),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="low_energy_lightens_plan",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_high_energy_prioritizes_deep_work_without_expansion() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval High Energy")
        energy_service.upsert_daily_metric(
            db,
            user_id=user.id,
            payload={"metric_date": PLAN_DATE, "energy_score": 90},
        )
        shallow_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Small shallow task",
            estimated_duration_min=20,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        deep_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Deep work block",
            estimated_duration_min=60,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        recommended = today["sections"]["recommended_tasks"]
        failures = _check_all(
            ("high energy keeps normal capacity", strategy["factors"]["daily_capacity_minutes"] == 150),
            ("deep task is first", bool(recommended) and recommended[0]["task_id"] == deep_task.id),
            ("shallow task is still present", len(recommended) > 1 and recommended[1]["task_id"] == shallow_task.id),
            ("energy was applied", strategy["factors"]["energy_applied"] is True),
            ("no expansion overload", strategy["factors"]["over_capacity_minutes"] == 0),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="high_energy_deep_fit_no_expansion",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_dependency_chain_protection() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Dependencies")
        prerequisite = task_service.create_task(
            db,
            user_id=user.id,
            title="Draft source outline",
            estimated_duration_min=30,
            priority=4,
            value_level=ValueLevel.LOW,
        )
        dependent = task_service.create_task(
            db,
            user_id=user.id,
            title="Write final proposal",
            estimated_duration_min=60,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        task_service.add_task_dependency(
            db,
            task_id=dependent.id,
            user_id=user.id,
            prerequisite_task_id=prerequisite.id,
            reason="Proposal needs the outline first",
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        pinned = today["sections"]["pinned_tasks"]
        failures = _check_all(
            ("prerequisite is first pinned task", len(pinned) >= 2 and pinned[0]["task_id"] == prerequisite.id),
            ("dependent follows prerequisite", len(pinned) >= 2 and pinned[1]["task_id"] == dependent.id),
            ("dependency protection counted", strategy["factors"]["dependency_protected_count"] == 1),
            (
                "prerequisite reason explains unlock",
                bool(pinned) and "unlocks another planned task" in pinned[0]["recommendation_reason"],
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="dependency_chain_protection",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_user_priority_adjustment_protection() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval User Priority")
        adjusted_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Promote important follow-up",
            estimated_duration_min=35,
            priority=5,
            value_level=ValueLevel.LOW,
        )
        task_service.create_task(
            db,
            user_id=user.id,
            title="Ordinary medium work",
            estimated_duration_min=35,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        task_service.adjust_task_priority(
            db,
            task_id=adjusted_task.id,
            user_id=user.id,
            priority=1,
            value_level=ValueLevel.HIGH,
            reason="This became important today",
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        pinned = today["sections"]["pinned_tasks"]
        failures = _check_all(
            ("adjusted task is first pinned task", bool(pinned) and pinned[0]["task_id"] == adjusted_task.id),
            ("user adjustment counted", strategy["factors"]["user_adjusted_count"] == 1),
            (
                "recommendation references user correction",
                bool(pinned) and "Adjusted by you" in pinned[0]["recommendation_reason"],
            ),
            (
                "score breakdown applies user preference boost",
                bool(pinned) and pinned[0]["score_breakdown"].get("user_preference_score", 0) > 0,
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="user_priority_adjustment_protection",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_behavior_feedback_penalizes_interruptions() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Behavior Feedback")
        stable_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Stable task",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        interrupted_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Frequently interrupted task",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        db.add_all(
            [
                ActivityEvent(
                    user_id=user.id,
                    entity_type=EntityType.TASK,
                    entity_id=interrupted_task.id,
                    event_type="FOCUS_SESSION_INTERRUPTED",
                    related_task_id=interrupted_task.id,
                ),
                ActivityEvent(
                    user_id=user.id,
                    entity_type=EntityType.TASK,
                    entity_id=interrupted_task.id,
                    event_type="FOCUS_SESSION_INTERRUPTED",
                    related_task_id=interrupted_task.id,
                ),
            ]
        )
        db.commit()

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        recommended = today["sections"]["recommended_tasks"]
        failures = _check_all(
            ("stable task is recommended first", len(recommended) >= 2 and recommended[0]["task_id"] == stable_task.id),
            (
                "interrupted task follows stable task",
                len(recommended) >= 2 and recommended[1]["task_id"] == interrupted_task.id,
            ),
            (
                "interrupted task receives behavior penalty",
                len(recommended) >= 2 and recommended[1]["score_breakdown"].get("behavior_feedback_score", 0) < 0,
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="behavior_feedback_penalizes_interruptions",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_multi_goal_competition_protects_high_value_goal() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Multi Goal")
        high_value_goal = goal_service.create_goal(
            db,
            user_id=user.id,
            title="Ship portfolio launch",
            deadline=PLAN_DATE + timedelta(days=14),
            value_level=ValueLevel.HIGH,
        )
        low_value_goal = goal_service.create_goal(
            db,
            user_id=user.id,
            title="Tidy low-value backlog",
            deadline=PLAN_DATE + timedelta(days=14),
            value_level=ValueLevel.LOW,
        )
        protected_task = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=high_value_goal.id,
            title="Advance high-value goal",
            estimated_duration_min=90,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        urgent_low_goal_task = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=low_value_goal.id,
            title="Urgent low-goal follow-up",
            estimated_duration_min=60,
            priority=2,
            value_level=ValueLevel.MEDIUM,
        )
        optional_low_goal_task = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=low_value_goal.id,
            title="Optional low-goal cleanup",
            estimated_duration_min=60,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        pinned = today["sections"]["pinned_tasks"]
        rolled = today["sections"]["rolled_over_tasks"]
        protected_item = _find_item(today, protected_task.id)
        urgent_low_item = _find_item(today, urgent_low_goal_task.id)
        failures = _check_all(
            ("high-value goal task is first pinned task", bool(pinned) and pinned[0]["task_id"] == protected_task.id),
            (
                "high-value goal task receives goal value boost",
                bool(protected_item) and protected_item["score_breakdown"].get("goal_value_score", 0) > 0,
            ),
            (
                "high-value goal task outranks urgent low-goal work",
                bool(protected_item)
                and bool(urgent_low_item)
                and protected_item["score_breakdown"]["total_score"] > urgent_low_item["score_breakdown"]["total_score"],
            ),
            (
                "recommendation explains high-value goal protection",
                bool(protected_item)
                and (
                    "High-value goal" in protected_item["recommendation_reason"]
                    or "关联目标当前最适合推进的下一步" in protected_item["recommendation_reason"]
                    or "高价值目标当前推进不足" in protected_item["recommendation_reason"]
                ),
            ),
            ("optional low-goal work rolls over", bool(rolled) and rolled[0]["task_id"] == optional_low_goal_task.id),
            ("main sequence still respects capacity", strategy["factors"]["selected_estimated_minutes"] == 150),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="multi_goal_competition_protects_high_value_goal",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_overdue_goal_recovery_promotes_next_task() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Overdue Goal")
        overdue_goal = goal_service.create_goal(
            db,
            user_id=user.id,
            title="Recover overdue launch goal",
            deadline=PLAN_DATE - timedelta(days=2),
            value_level=ValueLevel.MEDIUM,
        )
        recovery_task = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=overdue_goal.id,
            title="Recover overdue goal next step",
            estimated_duration_min=45,
            priority=4,
            value_level=ValueLevel.LOW,
        )
        regular_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Regular priority work",
            estimated_duration_min=45,
            priority=2,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        pinned = today["sections"]["pinned_tasks"]
        recovery_item = _find_item(today, recovery_task.id)
        regular_item = _find_item(today, regular_task.id)
        failures = _check_all(
            ("overdue goal next step is first pinned task", bool(pinned) and pinned[0]["task_id"] == recovery_task.id),
            (
                "overdue goal next step has no task deadline",
                bool(recovery_item) and recovery_item["deadline"] is None,
            ),
            (
                "overdue goal urgency score is applied",
                bool(recovery_item) and recovery_item["score_breakdown"].get("goal_urgency_score", 0) > 0,
            ),
            (
                "overdue goal recovery outranks regular priority work",
                bool(recovery_item)
                and bool(regular_item)
                and recovery_item["score_breakdown"]["total_score"] > regular_item["score_breakdown"]["total_score"],
            ),
            (
                "recommendation explains overdue goal recovery",
                bool(recovery_item) and "Goal is overdue" in recovery_item["recommendation_reason"],
            ),
            ("plan stays within capacity", strategy["factors"]["capacity_status"] == "within_capacity"),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="overdue_goal_recovery_promotes_next_task",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_goal_progress_strategy_closes_near_done_goal() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Goal Progress")
        goal = goal_service.create_goal(
            db,
            user_id=user.id,
            title="Finish Chronos P2 core loop",
            deadline=PLAN_DATE + timedelta(days=10),
            value_level=ValueLevel.HIGH,
        )
        for title in ("Finish architecture review", "Validate P1 mainline"):
            completed = task_service.create_task(
                db,
                user_id=user.id,
                goal_id=goal.id,
                title=title,
                estimated_duration_min=30,
                priority=3,
                value_level=ValueLevel.MEDIUM,
            )
            task_service.complete_task(
                db,
                task_id=completed.id,
                user_id=user.id,
                actual_duration_min_delta=30,
            )
        closing_task = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=goal.id,
            title="Close goal progress strategy",
            estimated_duration_min=45,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        competing_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Handle ordinary admin backlog",
            estimated_duration_min=45,
            priority=2,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        closing_item = _find_item(today, closing_task.id)
        competing_item = _find_item(today, competing_task.id)
        closing_rationale = next(
            (item for item in strategy["task_rationales"] if item["task_id"] == closing_task.id),
            None,
        )
        failures = _check_all(
            (
                "near-done high-value goal task receives progress strategy",
                bool(closing_item) and closing_item["score_breakdown"].get("goal_progress_applied") is True,
            ),
            (
                "goal progress score is applied",
                bool(closing_item) and closing_item["score_breakdown"].get("goal_progress_score", 0) > 0,
            ),
            (
                "closure reason is preserved",
                bool(closing_item)
                and closing_item["score_breakdown"].get("goal_progress_reason_key") == "goal_completion_closure",
            ),
            (
                "goal progress completion rate is visible",
                bool(closing_item) and closing_item["score_breakdown"].get("goal_progress_completion_rate", 0) >= 0.65,
            ),
            (
                "goal progress outranks ordinary admin task",
                bool(closing_item)
                and bool(competing_item)
                and closing_item["score_breakdown"]["total_score"] > competing_item["score_breakdown"]["total_score"],
            ),
            (
                "strategy exposes goal progress signal",
                strategy["factors"].get("goal_progress_signal_count") == 1,
            ),
            (
                "task rationale explains goal progress",
                bool(closing_rationale)
                and "goal_progress_strategy"
                in [signal["key"] for signal in closing_rationale["score_signals"]],
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="goal_progress_strategy_closes_near_done_goal",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_semantic_history_personalizes_duration() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Personalization")
        history_one = task_service.create_task(
            db,
            user_id=user.id,
            title="Write previous launch memo",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        task_service.complete_task(
            db,
            task_id=history_one.id,
            user_id=user.id,
            actual_duration_min_delta=60,
        )
        _add_task_signal(db, user_id=user.id, task=history_one, task_type="writing", estimated_duration_min=30)
        history_two = task_service.create_task(
            db,
            user_id=user.id,
            title="Write previous planning memo",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        task_service.complete_task(
            db,
            task_id=history_two.id,
            user_id=user.id,
            actual_duration_min_delta=50,
        )
        _add_task_signal(db, user_id=user.id, task=history_two, task_type="writing", estimated_duration_min=30)
        current_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Write current strategy memo",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        _add_task_signal(db, user_id=user.id, task=current_task, task_type="writing", estimated_duration_min=30)

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        current_item = _find_item(today, current_task.id)
        current_rationale = next(
            (item for item in strategy["task_rationales"] if item["task_id"] == current_task.id),
            None,
        )
        failures = _check_all(
            (
                "current writing task receives personalization signal",
                bool(current_item) and current_item["score_breakdown"].get("personalization_applied") is True,
            ),
            (
                "semantic estimate feedback is explicit",
                bool(current_item)
                and current_item["score_breakdown"].get("semantic_estimate_feedback_applied") is True,
            ),
            (
                "semantic estimate feedback preserves source",
                bool(current_item)
                and current_item["score_breakdown"].get("semantic_estimate_feedback_source")
                == "semantic_task_history",
            ),
            (
                "semantic estimate feedback forbids task estimate mutation",
                bool(current_item)
                and "task_estimated_duration_min"
                in (
                    (
                        current_item["score_breakdown"].get("semantic_estimate_feedback_contract")
                        or {}
                    ).get("cannot_affect")
                    or []
                ),
            ),
            (
                "history sample count is preserved",
                bool(current_item) and current_item["score_breakdown"].get("personalization_sample_count") == 2,
            ),
            (
                "duration estimate is adjusted upward",
                bool(current_item) and current_item["score_breakdown"].get("personalized_estimated_duration_min", 0) > 30,
            ),
            (
                "personalization factor is visible in strategy",
                strategy["factors"].get("personalization_signal_count") == 1,
            ),
            (
                "task rationale explains personalization",
                bool(current_item)
                and bool(current_rationale)
                and "personalization_signal"
                in [signal["key"] for signal in current_rationale["score_signals"]],
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="semantic_history_personalizes_duration",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_execution_learning_calibrates_focus_history() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Execution Learning")
        for index, actual_minutes in enumerate([64, 58], start=1):
            history_task = task_service.create_task(
                db,
                user_id=user.id,
                title=f"Write previous focus memo {index}",
                estimated_duration_min=30,
                priority=3,
                value_level=ValueLevel.MEDIUM,
            )
            task_service.complete_task(
                db,
                task_id=history_task.id,
                user_id=user.id,
                actual_duration_min_delta=actual_minutes,
            )
            _add_task_signal(db, user_id=user.id, task=history_task, task_type="writing", estimated_duration_min=30)
            db.add(
                ActivityEvent(
                    user_id=user.id,
                    entity_type=EntityType.FOCUS_SESSION,
                    entity_id=uuid.uuid4(),
                    event_type="EXECUTION_LEARNING_OBSERVED",
                    related_task_id=history_task.id,
                    payload={
                        "version": "p2-execution-learning-v2",
                        "source": "focus_session",
                        "outcome": "completed",
                        "planned_duration_min": 30,
                        "actual_duration_min": actual_minutes,
                        "duration_delta_min": actual_minutes - 30,
                    },
                )
            )
        db.commit()
        current_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Write current focus-calibrated memo",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        _add_task_signal(db, user_id=user.id, task=current_task, task_type="writing", estimated_duration_min=30)

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        current_item = _find_item(today, current_task.id)
        current_rationale = next(
            (item for item in strategy["task_rationales"] if item["task_id"] == current_task.id),
            None,
        )
        failures = _check_all(
            (
                "execution learning signal is applied",
                bool(current_item) and current_item["score_breakdown"].get("execution_learning_applied") is True,
            ),
            (
                "execution learning preserves v2 version",
                bool(current_item)
                and current_item["score_breakdown"].get("execution_learning_version") == "p2-execution-learning-v2",
            ),
            (
                "focus sample count is preserved",
                bool(current_item)
                and current_item["score_breakdown"].get("execution_learning_focus_sample_count") == 2,
            ),
            (
                "focus overrun risk is explicit",
                bool(current_item)
                and current_item["score_breakdown"].get("execution_learning_signal") == "duration_overrun_risk",
            ),
            (
                "objective receives execution learning component",
                bool(current_item)
                and current_item["score_breakdown"].get("planning_objective_execution_learning_component", 0) < 0,
            ),
            (
                "strategy exposes execution learning count",
                strategy["factors"].get("execution_learning_signal_count") == 1,
            ),
            (
                "task rationale explains execution learning",
                bool(current_rationale)
                and "execution_learning"
                in [signal["key"] for signal in current_rationale["score_signals"]],
            ),
            (
                "execution learning forbids direct LLM sorting",
                bool(current_item)
                and "llm_direct_sort_order"
                in (
                    (
                        current_item["score_breakdown"].get("execution_learning_contract")
                        or {}
                    ).get("cannot_affect")
                    or []
                ),
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="execution_learning_calibrates_focus_history",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_semantic_coverage_v2_guides_minimum_goal_action() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Semantic Coverage")
        goal = goal_service.create_goal(
            db,
            user_id=user.id,
            title="Make Planning Engine goal-aware",
            deadline=PLAN_DATE + timedelta(days=14),
            value_level=ValueLevel.HIGH,
        )
        task = task_service.create_task(
            db,
            user_id=user.id,
            goal_id=goal.id,
            title="Implement semantic planning coverage v2",
            estimated_duration_min=180,
            priority=4,
            value_level=ValueLevel.MEDIUM,
        )
        signal = TaskPlanningSignal(
            user_id=user.id,
            task_id=task.id,
            source="ai",
            task_type="coding",
            complexity="high",
            cognitive_load="high",
            energy_fit="high_energy",
            blocking_risk="high",
            estimated_duration_min=160,
            duration_confidence=0.82,
            goal_alignment_score=0.96,
            semantic_priority_score=0.91,
            breakdown_recommended=True,
            minimum_viable_step="完成语义字段到 Planning Engine 的最小接入",
            semantic_summary="该任务直接推进高价值目标，适合先切一个可验证动作。",
            confidence=0.88,
            raw_payload={
                "semantic_schema_version": "task-semantic-planning-v2",
                "complexity_reason": "需要设计、实现并验证核心编排信号。",
                "duration_reason": "完整实现偏大，但可以先切出一个 30 分钟的可验证动作。",
                "goal_progress_impact": "large",
                "goal_relevance_reason": "该任务直接决定高价值目标是否能进入可用闭环。",
                "minimum_viable_minutes": 30,
            },
        )
        db.add(signal)
        db.commit()

        today = planning_service.get_today(db, user_id=user.id, plan_date=PLAN_DATE)
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        item = _find_item(today, task.id)
        failures = _check_all(
            (
                "semantic coverage v2 is preserved",
                bool(item) and item["score_breakdown"].get("semantic_schema_version") == "task-semantic-planning-v2",
            ),
            (
                "minimum viable minutes drive planned slice",
                bool(item) and item["estimated_duration_min"] == 30,
            ),
            (
                "large goal impact is scored",
                bool(item) and item["score_breakdown"].get("semantic_goal_progress_impact_score") == 12,
            ),
            (
                "goal relevance reason is visible",
                bool(item) and bool(item["score_breakdown"].get("semantic_goal_relevance_reason")),
            ),
            (
                "objective consumes semantic component",
                bool(item) and item["score_breakdown"].get("planning_objective_semantic_component", 0) >= 40,
            ),
            (
                "strategy exposes semantic goal impact count",
                strategy["factors"].get("semantic_goal_impact_count") == 1,
            ),
            (
                "semantic planning rationale remains visible",
                bool(item) and "semantic_planning" in [
                    signal["key"]
                    for signal in next(
                        rationale for rationale in strategy["task_rationales"] if rationale["task_id"] == task.id
                    )["score_signals"]
                ],
            ),
        )
        failures += _explainability_failures(strategy)
        return ScenarioResult(
            name="semantic_coverage_v2_guides_minimum_goal_action",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _scenario_planner_feedback_preference_explained_without_reordering() -> ScenarioResult:
    db = _fresh_db()
    try:
        user = create_user(db, name="Planner Eval Feedback Preference")
        protected_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Protect focused implementation",
            estimated_duration_min=60,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        rolled_task = task_service.create_task(
            db,
            user_id=user.id,
            title="Optional backlog cleanup",
            estimated_duration_min=60,
            priority=5,
            value_level=ValueLevel.LOW,
        )

        initial_today = planning_service.replan_today(
            db,
            user_id=user.id,
            plan_date=PLAN_DATE,
            reason="Short day before preference feedback",
            available_minutes=60,
        )
        initial_strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        initial_suggestion_keys = [
            suggestion["key"] for suggestion in (initial_strategy["planner_review"] or {}).get("suggestions", [])
        ]
        for _ in range(2):
            planning_service.record_planner_review_feedback(
                db,
                user_id=user.id,
                plan_date=PLAN_DATE,
                suggestion_key="respect_rollover",
                action="ignored",
            )

        today = planning_service.replan_today(
            db,
            user_id=user.id,
            plan_date=PLAN_DATE,
            reason="Replan with feedback preference",
            available_minutes=60,
        )
        strategy = planning_service.get_strategy_detail(db, user_id=user.id, plan_date=PLAN_DATE)
        rolled = today["sections"]["rolled_over_tasks"]
        protected_item = _find_item(today, protected_task.id)
        feedback_summary = ((strategy["planner_review"] or {}).get("feedback_summary") or {})
        learning_contract = feedback_summary.get("learning_contract") or {}
        updated_suggestion_keys = [
            suggestion["key"] for suggestion in (strategy["planner_review"] or {}).get("suggestions", [])
        ]
        failures = _check_all(
            ("initial review includes rollover suggestion", "respect_rollover" in initial_suggestion_keys),
            ("preference summary is exposed", feedback_summary.get("key") == "capacity_flexibility_preferred"),
            (
                "preference contract forbids plan mutation",
                learning_contract.get("plan_mutation_allowed") is False,
            ),
            (
                "preference contract allows explanation only",
                "strategy_explanation" in (learning_contract.get("can_affect") or []),
            ),
            (
                "preference contract blocks hidden ordering changes",
                "today_sort_order" in (learning_contract.get("cannot_affect") or []),
            ),
            ("main sequence count is unchanged by preference", today["progress"]["total_count"] == 1),
            (
                "protected task stays in main sequence",
                bool(protected_item)
                and _section_value(protected_item) != DailyPlanItemSection.ROLLED_OVER.value
                and protected_item["sort_order"] == 1,
            ),
            ("rolled task stays rolled over", bool(rolled) and rolled[0]["task_id"] == rolled_task.id),
            ("daily capacity is not expanded by preference", strategy["factors"]["daily_capacity_minutes"] == 60),
            (
                "manual capacity source is preserved",
                strategy["factors"]["capacity_source"] == "manual_today_override",
            ),
            ("selected minutes remain deterministic", strategy["factors"]["selected_estimated_minutes"] == 60),
            (
                "strategy explanation references capacity preference",
                any("主动调整容量" in line for line in strategy["explanation"]),
            ),
            (
                "review suggests manual capacity adjustment instead of hidden reordering",
                "adjust_capacity_if_needed" in updated_suggestion_keys,
            ),
            (
                "feedback preference does not keep asking for rollover respect",
                "respect_rollover" not in updated_suggestion_keys,
            ),
        )
        failures += _explainability_failures(strategy)
        details = _details(db=db, today=today, strategy=strategy)
        details.update(
            {
                "initial_ordered_titles": [item["title"] for item in _all_items(initial_today)],
                "initial_rolled_over_titles": [
                    item["title"] for item in initial_today["sections"]["rolled_over_tasks"]
                ],
                "planner_feedback_summary_key": feedback_summary.get("key"),
                "planner_feedback_learning_contract": learning_contract,
                "planner_review_suggestion_keys": updated_suggestion_keys,
                "strategy_explanation": strategy["explanation"],
            }
        )
        return ScenarioResult(
            name="planner_feedback_preference_explained_without_reordering",
            passed=not failures,
            details=details,
            failures=failures,
        )
    finally:
        db.close()


def _fresh_db():
    reset_database()
    return TestingSessionLocal()


def _add_task_signal(
    db,
    *,
    user_id,
    task: Task,
    task_type: str,
    estimated_duration_min: int | None = None,
) -> TaskPlanningSignal:
    signal = TaskPlanningSignal(
        user_id=user_id,
        task_id=task.id,
        source="rule",
        task_type=task_type,
        complexity="medium",
        cognitive_load="medium",
        energy_fit="steady",
        blocking_risk="low",
        estimated_duration_min=estimated_duration_min,
        duration_confidence=0.7,
        goal_alignment_score=0.4,
        semantic_priority_score=0.4,
        breakdown_recommended=False,
        minimum_viable_step=None,
        semantic_summary="Planner eval semantic signal.",
        confidence=0.7,
        raw_payload={},
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def _details(*, db, today: dict, strategy: dict) -> dict:
    ordered_items = _all_items(today)
    planner_trace = _planner_trace(db, strategy=strategy)
    score_explanation = strategy.get("score_explanation") or {}
    return {
        "main_count": today["progress"]["total_count"],
        "rolled_over_count": len(today["sections"]["rolled_over_tasks"]),
        "ordered_titles": [item["title"] for item in ordered_items],
        "rolled_over_titles": [item["title"] for item in today["sections"]["rolled_over_tasks"]],
        "score_explanation_summary": score_explanation.get("summary"),
        "score_explanation_signal_keys": [
            signal["key"] for signal in score_explanation.get("signals", []) if signal.get("key")
        ],
        "planner_feedback_summary_key": (
            ((strategy.get("planner_review") or {}).get("feedback_summary") or {}).get("key")
        ),
        "strategy_explanation": strategy.get("explanation", []),
        "item_signals": _item_signals(strategy.get("task_rationales", [])),
        "risk_keys": [alert["key"] for alert in today["insights_preview"]["risk_alerts"]],
        "capacity_status": strategy["factors"]["capacity_status"],
        "daily_capacity_minutes": strategy["factors"]["daily_capacity_minutes"],
        "selected_estimated_minutes": strategy["factors"]["selected_estimated_minutes"],
        "rolled_over_estimated_minutes": strategy["factors"]["rolled_over_estimated_minutes"],
        "over_capacity_minutes": strategy["factors"]["over_capacity_minutes"],
        "energy_applied": strategy["factors"]["energy_applied"],
        "semantic_goal_impact_count": strategy["factors"].get("semantic_goal_impact_count"),
        "execution_learning_signal_count": strategy["factors"].get("execution_learning_signal_count"),
        "execution_learning_friction_risk_count": strategy["factors"].get(
            "execution_learning_friction_risk_count"
        ),
        "execution_learning_momentum_count": strategy["factors"].get("execution_learning_momentum_count"),
        "planning_objective_applied": strategy["factors"].get("planning_objective_applied"),
        "planning_objective_version": strategy["factors"].get("planning_objective_version"),
        "objective_selected_score": strategy["factors"].get("objective_selected_score"),
        "objective_rolled_over_score": strategy["factors"].get("objective_rolled_over_score"),
        **planner_trace,
    }


def _all_items(today: dict) -> list[dict]:
    sections = today["sections"]
    return (
        sections["pinned_tasks"]
        + sections["recommended_tasks"]
        + sections["low_priority_tasks"]
        + sections["rolled_over_tasks"]
    )


def _find_item(today: dict, task_id) -> dict | None:
    for item in _all_items(today):
        if item["task_id"] == task_id:
            return item
    return None


def _section_value(item: dict) -> str:
    section = item["section"]
    return section.value if hasattr(section, "value") else str(section)


def _item_signals(items: list[dict]) -> list[dict]:
    return [
        {
            "title": item["title"],
            "section": item["section"].value if hasattr(item["section"], "value") else item["section"],
            "score_version": item["score_breakdown"].get("score_version"),
            "score_band": item["score_breakdown"].get("score_band"),
            "total_score": item["score_breakdown"].get("total_score"),
            "goal_value_score": item["score_breakdown"].get("goal_value_score"),
            "goal_urgency_score": item["score_breakdown"].get("goal_urgency_score"),
            "goal_progress_score": item["score_breakdown"].get("goal_progress_score"),
            "goal_progress_completion_rate": item["score_breakdown"].get("goal_progress_completion_rate"),
            "behavior_feedback_score": item["score_breakdown"].get("behavior_feedback_score"),
            "personalization_score": item["score_breakdown"].get("personalization_score"),
            "personalization_sample_count": item["score_breakdown"].get("personalization_sample_count"),
            "execution_learning_applied": item["score_breakdown"].get("execution_learning_applied"),
            "execution_learning_signal": item["score_breakdown"].get("execution_learning_signal"),
            "execution_learning_focus_sample_count": item["score_breakdown"].get(
                "execution_learning_focus_sample_count"
            ),
            "planning_objective_execution_learning_component": item["score_breakdown"].get(
                "planning_objective_execution_learning_component"
            ),
            "dependency_score": item["score_breakdown"].get("dependency_score"),
            "user_preference_score": item["score_breakdown"].get("user_preference_score"),
            "semantic_schema_version": item["score_breakdown"].get("semantic_schema_version"),
            "semantic_goal_progress_impact": item["score_breakdown"].get("semantic_goal_progress_impact"),
            "semantic_goal_progress_impact_score": item["score_breakdown"].get(
                "semantic_goal_progress_impact_score"
            ),
            "semantic_minimum_viable_minutes": item["score_breakdown"].get("semantic_minimum_viable_minutes"),
            "planning_objective_score": item["score_breakdown"].get("planning_objective_score"),
            "planning_objective_selected": item["score_breakdown"].get("planning_objective_selected"),
            "planning_objective_reason_key": item["score_breakdown"].get("planning_objective_reason_key"),
            "dominant_factor": item.get("dominant_factor"),
            "dominant_reason": item.get("dominant_reason"),
            "score_signal_keys": [signal["key"] for signal in item.get("score_signals", []) if signal.get("key")],
        }
        for item in items
    ]


def _check_all(*checks: tuple[str, bool]) -> list[str]:
    return [label for label, passed in checks if not passed]


def _explainability_failures(strategy: dict) -> list[str]:
    score_explanation = strategy.get("score_explanation") or {}
    score_signals = score_explanation.get("signals") or []
    task_rationales = strategy.get("task_rationales") or []
    return _check_all(
        ("score explanation has summary", bool(score_explanation.get("summary"))),
        ("score explanation has signals", bool(score_signals)),
        (
            "task rationales have dominant factors",
            bool(task_rationales)
            and all(item.get("dominant_factor") and item.get("dominant_reason") for item in task_rationales),
        ),
        (
            "task rationales have score signals",
            bool(task_rationales) and all(item.get("score_signals") for item in task_rationales),
        ),
    )


def _planner_trace(db, *, strategy: dict) -> dict:
    ai_job_id = strategy.get("source", {}).get("ai_job_id")
    if not ai_job_id:
        return _empty_planner_trace()
    job = db.get(AIJob, uuid.UUID(ai_job_id))
    if job is None:
        return _empty_planner_trace()
    metadata = job.job_metadata or {}
    return {
        "planner_agent_job_id": str(job.id),
        "planner_agent_status": job.status.value,
        "planner_agent_provider": job.provider,
        "planner_agent_model": job.model,
        "planner_agent_prompt_version": job.prompt_version,
        "planner_agent_prompt_checksum": metadata.get("prompt_checksum"),
        "planner_agent_latency_ms": job.latency_ms,
        "planner_agent_failure_type": metadata.get("failure_type"),
        "planner_agent_output_applied": metadata.get("output_applied"),
        "planner_agent_usage": metadata.get("usage"),
    }


def _empty_planner_trace() -> dict:
    return {
        "planner_agent_job_id": None,
        "planner_agent_status": None,
        "planner_agent_provider": None,
        "planner_agent_model": None,
        "planner_agent_prompt_version": None,
        "planner_agent_prompt_checksum": None,
        "planner_agent_latency_ms": None,
        "planner_agent_failure_type": None,
        "planner_agent_output_applied": None,
        "planner_agent_usage": None,
    }


def write_jsonl_result(result: dict, output_path: Path, *, append: bool = False) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with output_path.open(mode, encoding="utf-8") as file:
        records = _jsonl_records(result)
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, default=str))
            file.write("\n")
    return output_path


def _jsonl_records(result: dict) -> list[dict]:
    base = {
        "run_id": result["run_id"],
        "evaluator_version": result["evaluator_version"],
    }
    records = [
        {
            **base,
            "record_type": "run_summary",
            "status": result["status"],
            "scenario_count": result["scenario_count"],
            "passed_count": result["passed_count"],
            "failed_count": result["failed_count"],
        }
    ]
    records.extend(
        {
            **base,
            "record_type": "scenario_result",
            "scenario_name": scenario["name"],
            "passed": scenario["passed"],
            "failures": scenario["failures"],
            "details": scenario["details"],
        }
        for scenario in result["scenarios"]
    )
    return records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate deterministic Chronos planning scenarios.")
    parser.add_argument(
        "--jsonl-output",
        type=Path,
        default=None,
        help="Optional path to write offline evaluation JSONL records.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append JSONL records instead of overwriting the output file.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional stable run id for repeatable offline comparisons.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run_evaluation(run_id=args.run_id)
    if args.jsonl_output is not None:
        write_jsonl_result(result, args.jsonl_output, append=args.append)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
