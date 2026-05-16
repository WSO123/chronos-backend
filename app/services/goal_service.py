from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EntityType, GoalStatus, ValueLevel
from app.models.goal import Goal
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


goal_service = GoalService()
