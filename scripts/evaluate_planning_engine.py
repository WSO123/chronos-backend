from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
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
from app.models.enums import DailyPlanItemStatus, EntityType, TaskStatus, ValueLevel
from app.services.energy_service import energy_service
from app.services.planning_service import planning_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


PLAN_DATE = date(2026, 5, 17)
EVALUATOR_VERSION = "p2-planning-engine-eval-v2"


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
        _scenario_protected_overload_warning,
        _scenario_low_energy_lightens_plan,
        _scenario_high_energy_prioritizes_deep_work_without_expansion,
        _scenario_dependency_chain_protection,
        _scenario_user_priority_adjustment_protection,
        _scenario_behavior_feedback_penalizes_interruptions,
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
        return ScenarioResult(
            name="capacity_rollover",
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
        return ScenarioResult(
            name="behavior_feedback_penalizes_interruptions",
            passed=not failures,
            details=_details(db=db, today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _fresh_db():
    reset_database()
    return TestingSessionLocal()


def _details(*, db, today: dict, strategy: dict) -> dict:
    ordered_items = _all_items(today)
    planner_trace = _planner_trace(db, strategy=strategy)
    return {
        "main_count": today["progress"]["total_count"],
        "rolled_over_count": len(today["sections"]["rolled_over_tasks"]),
        "ordered_titles": [item["title"] for item in ordered_items],
        "rolled_over_titles": [item["title"] for item in today["sections"]["rolled_over_tasks"]],
        "item_signals": _item_signals(ordered_items),
        "risk_keys": [alert["key"] for alert in today["insights_preview"]["risk_alerts"]],
        "capacity_status": strategy["factors"]["capacity_status"],
        "daily_capacity_minutes": strategy["factors"]["daily_capacity_minutes"],
        "selected_estimated_minutes": strategy["factors"]["selected_estimated_minutes"],
        "rolled_over_estimated_minutes": strategy["factors"]["rolled_over_estimated_minutes"],
        "over_capacity_minutes": strategy["factors"]["over_capacity_minutes"],
        "energy_applied": strategy["factors"]["energy_applied"],
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


def _item_signals(items: list[dict]) -> list[dict]:
    return [
        {
            "title": item["title"],
            "section": item["section"].value,
            "total_score": item["score_breakdown"].get("total_score"),
            "behavior_feedback_score": item["score_breakdown"].get("behavior_feedback_score"),
            "dependency_score": item["score_breakdown"].get("dependency_score"),
            "user_preference_score": item["score_breakdown"].get("user_preference_score"),
        }
        for item in items
    ]


def _check_all(*checks: tuple[str, bool]) -> list[str]:
    return [label for label, passed in checks if not passed]


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
