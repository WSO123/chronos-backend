from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy.orm import Session

from app.models.enums import EntityType, GoalStatus, ValueLevel
from app.models.goal import Goal
from app.services.activity_event_service import activity_event_service


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
        db.commit()
        db.refresh(goal)
        return goal


goal_service = GoalService()
