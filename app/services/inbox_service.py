from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CaptureSource, EntityType, InboxItemStatus, InboxItemType, TaskSource, ValueLevel
from app.models.inbox import InboxItem
from app.services.activity_event_service import activity_event_service
from app.services.errors import InvalidStateError, NotFoundError, ValidationDomainError
from app.services.goal_service import goal_service
from app.services.task_service import task_service


class InboxService:
    def list_items(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        status: InboxItemStatus | None = InboxItemStatus.PENDING,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InboxItem]:
        stmt = select(InboxItem).where(InboxItem.user_id == user_id)
        if status is not None:
            stmt = stmt.where(InboxItem.status == status)
        stmt = stmt.order_by(InboxItem.created_at.desc()).limit(limit).offset(offset)
        return list(db.scalars(stmt).all())

    def get_item(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID) -> InboxItem:
        item = db.get(InboxItem, item_id)
        if item is None or item.user_id != user_id:
            raise NotFoundError("Inbox item not found")
        return item

    def update_item(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID, updates: dict) -> InboxItem:
        item = self.get_item(db, item_id=item_id, user_id=user_id)
        self._ensure_editable(item)
        changed_fields: list[str] = []

        for field in ("item_type", "title", "description", "suggested_goal_id", "suggested_priority", "suggested_deadline"):
            if field in updates:
                setattr(item, field, updates[field])
                changed_fields.append(field)

        if changed_fields:
            item.status = InboxItemStatus.EDITED
            activity_event_service.add_event(
                db,
                user_id=user_id,
                entity_type=EntityType.INBOX,
                entity_id=item.id,
                event_type="INBOX_ITEM_UPDATED",
                payload={"changed_fields": changed_fields},
            )
        db.commit()
        db.refresh(item)
        return item

    def confirm_item(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID) -> InboxItem:
        item = self._get_item_for_update(db, item_id=item_id, user_id=user_id)
        if item.status == InboxItemStatus.CONFIRMED:
            if item.result_entity_type and item.result_entity_id:
                db.commit()
                db.refresh(item)
                return item
            raise InvalidStateError("confirmed inbox item is missing result entity")

        if item.status not in {InboxItemStatus.PENDING, InboxItemStatus.EDITED}:
            raise InvalidStateError(f"{item.status.value} inbox item cannot be confirmed")

        if item.item_type == InboxItemType.TASK:
            task = task_service.create_task(
                db,
                user_id=user_id,
                title=item.title,
                description=item.description,
                goal_id=item.suggested_goal_id,
                estimated_duration_min=item.parse_result.estimated_duration_min,
                priority=item.suggested_priority or 3,
                value_level=ValueLevel.MEDIUM,
                deadline=item.suggested_deadline,
                source=self._task_source_for(item),
                commit=False,
            )
            item.status = InboxItemStatus.CONFIRMED
            item.result_entity_type = "task"
            item.result_entity_id = task.id
        elif item.item_type == InboxItemType.GOAL:
            goal = goal_service.create_goal(
                db,
                user_id=user_id,
                title=item.title,
                description=item.description,
                deadline=item.suggested_deadline,
                value_level=ValueLevel.MEDIUM,
                commit=False,
            )
            item.status = InboxItemStatus.CONFIRMED
            item.result_entity_type = "goal"
            item.result_entity_id = goal.id
        else:
            raise ValidationDomainError("Only task or goal inbox items can be confirmed")

        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.INBOX,
            entity_id=item.id,
            event_type="INBOX_ITEM_CONFIRMED",
            payload={"result_entity_type": item.result_entity_type, "result_entity_id": str(item.result_entity_id)},
        )
        db.commit()
        db.refresh(item)
        return item

    def discard_item(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID) -> InboxItem:
        item = self.get_item(db, item_id=item_id, user_id=user_id)
        if item.status not in {InboxItemStatus.PENDING, InboxItemStatus.EDITED}:
            raise InvalidStateError(f"{item.status.value} inbox item cannot be discarded")

        item.status = InboxItemStatus.DISCARDED
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.INBOX,
            entity_id=item.id,
            event_type="INBOX_ITEM_DISCARDED",
        )
        db.commit()
        db.refresh(item)
        return item

    def _ensure_editable(self, item: InboxItem) -> None:
        if item.status not in {InboxItemStatus.PENDING, InboxItemStatus.EDITED}:
            raise InvalidStateError(f"{item.status.value} inbox item cannot be edited")

    def _get_item_for_update(self, db: Session, *, item_id: uuid.UUID, user_id: uuid.UUID) -> InboxItem:
        stmt = (
            select(InboxItem)
            .where(InboxItem.id == item_id, InboxItem.user_id == user_id)
            .with_for_update()
        )
        item = db.scalars(stmt).first()
        if item is None:
            raise NotFoundError("Inbox item not found")
        return item

    def _task_source_for(self, item: InboxItem) -> TaskSource:
        capture_source = item.capture_input.source
        if capture_source == CaptureSource.EMAIL:
            return TaskSource.EMAIL
        if capture_source == CaptureSource.CALENDAR:
            return TaskSource.CALENDAR
        return TaskSource.CAPTURE


inbox_service = InboxService()
