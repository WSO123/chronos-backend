from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path
import sys
from typing import Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.enums import DailyPlanItemStatus, TaskStatus, ValueLevel
from app.services.energy_service import energy_service
from app.services.planning_service import planning_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


PLAN_DATE = date(2026, 5, 17)


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    details: dict
    failures: list[str]


def run_evaluation() -> dict:
    scenarios: list[Callable[[], ScenarioResult]] = [
        _scenario_capacity_rollover,
        _scenario_protected_overload_warning,
        _scenario_low_energy_lightens_plan,
        _scenario_high_energy_prioritizes_deep_work_without_expansion,
    ]
    results = [scenario() for scenario in scenarios]
    return {
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
            details=_details(today=today, strategy=strategy),
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
            details=_details(today=today, strategy=strategy),
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
            details=_details(today=today, strategy=strategy),
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
            details=_details(today=today, strategy=strategy),
            failures=failures,
        )
    finally:
        db.close()


def _fresh_db():
    reset_database()
    return TestingSessionLocal()


def _details(*, today: dict, strategy: dict) -> dict:
    ordered_items = _all_items(today)
    return {
        "main_count": today["progress"]["total_count"],
        "rolled_over_count": len(today["sections"]["rolled_over_tasks"]),
        "ordered_titles": [item["title"] for item in ordered_items],
        "rolled_over_titles": [item["title"] for item in today["sections"]["rolled_over_tasks"]],
        "risk_keys": [alert["key"] for alert in today["insights_preview"]["risk_alerts"]],
        "capacity_status": strategy["factors"]["capacity_status"],
        "daily_capacity_minutes": strategy["factors"]["daily_capacity_minutes"],
        "selected_estimated_minutes": strategy["factors"]["selected_estimated_minutes"],
        "rolled_over_estimated_minutes": strategy["factors"]["rolled_over_estimated_minutes"],
        "over_capacity_minutes": strategy["factors"]["over_capacity_minutes"],
        "energy_applied": strategy["factors"]["energy_applied"],
    }


def _all_items(today: dict) -> list[dict]:
    sections = today["sections"]
    return (
        sections["pinned_tasks"]
        + sections["recommended_tasks"]
        + sections["low_priority_tasks"]
        + sections["rolled_over_tasks"]
    )


def _check_all(*checks: tuple[str, bool]) -> list[str]:
    return [label for label, passed in checks if not passed]


def main() -> None:
    result = run_evaluation()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
