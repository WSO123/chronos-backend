from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
import uuid
from zoneinfo import ZoneInfo

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import SessionLocal
from app.models.enums import GoalStatus, InboxItemStatus, TaskStatus, ValueLevel
from app.models.goal import Goal
from app.models.inbox import InboxItem
from app.models.task import Task
from app.services.capture_service import capture_service
from app.services.goal_service import goal_service
from app.services.planning_service import planning_service
from app.services.report_service import report_service
from app.services.task_service import task_service
from scripts.dev_seed_user import seed_user


DEMO_EMAIL = "demo@chronos.local"
DEMO_NAME = "Chronos Demo"
DEMO_TIMEZONE = "Asia/Shanghai"


def seed_demo_data(
    *,
    email: str,
    name: str,
    timezone: str,
    password: str | None = None,
    emit_token: bool = False,
) -> dict:
    if emit_token and not password:
        raise ValueError("emit_token requires password")
    user = seed_user(email=email, name=name, timezone=timezone, password=password)
    email = user.email
    user_id = user.id
    today = datetime.now(ZoneInfo(timezone)).date()

    with SessionLocal() as db:
        goal = _get_or_create_goal(
            db,
            user_id=user_id,
            title="Ship Chronos P1 execution loop",
            description="Demo goal for Capture -> Inbox -> Today -> Task Detail -> Focus -> Report.",
            deadline=today + timedelta(days=14),
            value_level=ValueLevel.HIGH,
        )
        high_value_task = _get_or_create_task(
            db,
            user_id=user_id,
            goal_id=goal.id,
            title="Prepare the P1 execution loop demo",
            description="Keep the demo focused on the daily execution loop.",
            estimated_duration_min=70,
            priority=1,
            value_level=ValueLevel.HIGH,
            deadline=today,
        )
        supporting_task = _get_or_create_task(
            db,
            user_id=user_id,
            goal_id=goal.id,
            title="Review Task Detail handoff copy",
            description="Make sure execution suggestions stay light and actionable.",
            estimated_duration_min=25,
            priority=3,
            value_level=ValueLevel.MEDIUM,
            deadline=today + timedelta(days=2),
        )
        rolled_task = _get_or_create_task(
            db,
            user_id=user_id,
            goal_id=None,
            title="Tidy low priority notes",
            description="A lower-value task kept visible without crowding out the main sequence.",
            estimated_duration_min=20,
            priority=5,
            value_level=ValueLevel.LOW,
            deadline=None,
        )
        if rolled_task.status == TaskStatus.ACTIVE:
            rolled_task = task_service.postpone_task(db, task_id=rolled_task.id, user_id=user_id)

        if high_value_task.status in {TaskStatus.ACTIVE, TaskStatus.POSTPONED} and not high_value_task.steps:
            task_service.breakdown_task(db, task_id=high_value_task.id, user_id=user_id)

        capture_text = "todo 整理今天突然想到的 Chronos P1 验证点"
        inbox_item = _get_pending_inbox_item(db, user_id=user_id, title=capture_text)
        if inbox_item is None:
            _, _, inbox_item = capture_service.create_text_capture(db, user_id=user_id, raw_text=capture_text)

        today_payload = planning_service.get_today(db, user_id=user_id, plan_date=today)
        report = report_service.generate_daily_report(db, user_id=user_id, report_date=today)

        result = {
            "user_id": user_id,
            "header": f"X-User-Id: {user_id}",
            "goal_id": goal.id,
            "high_value_task_id": high_value_task.id,
            "supporting_task_id": supporting_task.id,
            "rolled_task_id": rolled_task.id,
            "pending_inbox_item_id": inbox_item.id,
            "today_plan_id": today_payload["daily_plan_id"],
            "today_plan_version": today_payload["plan_version"],
            "daily_report_id": report.id,
        }
        if password:
            result["login"] = {
                "email": email,
                "endpoint": "POST /api/v1/auth/login",
            }
        if emit_token:
            from scripts.dev_seed_user import issue_local_token

            result["auth"] = issue_local_token(email=email, password=password)
        return result


def _get_or_create_goal(
    db: Session,
    *,
    user_id: uuid.UUID,
    title: str,
    description: str,
    deadline: date,
    value_level: ValueLevel,
) -> Goal:
    existing = db.scalars(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.title == title,
            Goal.status == GoalStatus.ACTIVE,
        )
    ).first()
    if existing is not None:
        return existing
    return goal_service.create_goal(
        db,
        user_id=user_id,
        title=title,
        description=description,
        deadline=deadline,
        value_level=value_level,
    )


def _get_or_create_task(
    db: Session,
    *,
    user_id: uuid.UUID,
    goal_id: uuid.UUID | None,
    title: str,
    description: str,
    estimated_duration_min: int,
    priority: int,
    value_level: ValueLevel,
    deadline: date | None,
) -> Task:
    existing = db.scalars(
        select(Task)
        .options(selectinload(Task.steps))
        .where(
            Task.user_id == user_id,
            Task.title == title,
            Task.status.in_([TaskStatus.ACTIVE, TaskStatus.IN_FOCUS, TaskStatus.POSTPONED]),
        )
    ).first()
    if existing is not None:
        return existing
    return task_service.create_task(
        db,
        user_id=user_id,
        goal_id=goal_id,
        title=title,
        description=description,
        estimated_duration_min=estimated_duration_min,
        priority=priority,
        value_level=value_level,
        deadline=deadline,
    )


def _get_pending_inbox_item(db: Session, *, user_id: uuid.UUID, title: str) -> InboxItem | None:
    return db.scalars(
        select(InboxItem).where(
            InboxItem.user_id == user_id,
            InboxItem.title == title,
            InboxItem.status == InboxItemStatus.PENDING,
        )
    ).first()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Chronos P1 demo data for local development.")
    parser.add_argument("--email", default=DEMO_EMAIL)
    parser.add_argument("--name", default=DEMO_NAME)
    parser.add_argument("--timezone", default=DEMO_TIMEZONE)
    parser.add_argument("--password", default=None, help="Optional local password for /api/v1/auth/login.")
    parser.add_argument(
        "--emit-token",
        action="store_true",
        help="Print a local auth token pair. Requires --password.",
    )
    args = parser.parse_args()
    if args.emit_token and not args.password:
        parser.error("--emit-token requires --password")

    result = seed_demo_data(
        email=args.email,
        name=args.name,
        timezone=args.timezone,
        password=args.password,
        emit_token=args.emit_token,
    )
    print("Chronos P1 demo data ready.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
