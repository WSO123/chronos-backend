from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.enums import ActorType, EntityType, EventSource


class ActivityEventService:
    def build_event(
        self,
        *,
        user_id: uuid.UUID,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        event_type: str,
        actor_type: ActorType = ActorType.USER,
        source: EventSource = EventSource.API,
        payload: dict[str, Any] | None = None,
        related_task_id: uuid.UUID | None = None,
        related_daily_plan_id: uuid.UUID | None = None,
        related_focus_session_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> ActivityEvent:
        return ActivityEvent(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            actor_type=actor_type,
            source=source,
            payload=payload or {},
            related_task_id=related_task_id,
            related_daily_plan_id=related_daily_plan_id,
            related_focus_session_id=related_focus_session_id,
            idempotency_key=idempotency_key,
        )

    def add_event(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        event_type: str,
        actor_type: ActorType = ActorType.USER,
        source: EventSource = EventSource.API,
        payload: dict[str, Any] | None = None,
        related_task_id: uuid.UUID | None = None,
        related_daily_plan_id: uuid.UUID | None = None,
        related_focus_session_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> ActivityEvent:
        event = self.build_event(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            actor_type=actor_type,
            source=source,
            payload=payload,
            related_task_id=related_task_id,
            related_daily_plan_id=related_daily_plan_id,
            related_focus_session_id=related_focus_session_id,
            idempotency_key=idempotency_key,
        )
        db.add(event)
        return event


activity_event_service = ActivityEventService()
