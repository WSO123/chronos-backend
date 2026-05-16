from __future__ import annotations

from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from app.models.capture import AIParseResult, CaptureInput
from app.models.enums import (
    CaptureInputType,
    CaptureSource,
    CaptureStatus,
    EntityType,
    InboxItemStatus,
)
from app.models.inbox import InboxItem
from app.services.activity_event_service import activity_event_service
from app.services.capture_parser import rule_capture_parser
from app.services.errors import NotFoundError, ValidationDomainError


class CaptureService:
    def create_text_capture(self, db: Session, *, user_id: uuid.UUID, raw_text: str) -> tuple[CaptureInput, AIParseResult, InboxItem]:
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise ValidationDomainError("Capture text cannot be empty")

        capture = CaptureInput(
            user_id=user_id,
            input_type=CaptureInputType.TEXT,
            raw_text=cleaned_text,
            source=CaptureSource.MANUAL,
            status=CaptureStatus.RECEIVED,
        )
        db.add(capture)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.CAPTURE,
            entity_id=capture.id,
            event_type="CAPTURE_CREATED",
            payload={"input_type": CaptureInputType.TEXT.value},
        )

        parsed = rule_capture_parser.parse_text(cleaned_text)
        parse_result = AIParseResult(
            capture_input_id=capture.id,
            result_type=parsed.result_type,
            title=parsed.title,
            description=parsed.description,
            estimated_duration_min=parsed.estimated_duration_min,
            suggested_priority=parsed.suggested_priority,
            suggested_deadline=parsed.suggested_deadline,
            confidence=Decimal(str(parsed.confidence)),
            raw_model_output=parsed.raw_model_output,
        )
        db.add(parse_result)
        db.flush()

        inbox_item = InboxItem(
            user_id=user_id,
            capture_input_id=capture.id,
            parse_result_id=parse_result.id,
            item_type=parsed.item_type,
            title=parsed.title,
            description=parsed.description,
            suggested_priority=parsed.suggested_priority,
            suggested_deadline=parsed.suggested_deadline,
            status=InboxItemStatus.PENDING,
        )
        db.add(inbox_item)
        capture.status = CaptureStatus.PARSED
        db.flush()

        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.CAPTURE,
            entity_id=capture.id,
            event_type="CAPTURE_PARSED",
            payload={"result_type": parsed.result_type.value, "confidence": parsed.confidence},
        )
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.INBOX,
            entity_id=inbox_item.id,
            event_type="INBOX_ITEM_CREATED",
            payload={"item_type": parsed.item_type.value},
        )
        db.commit()
        db.refresh(capture)
        db.refresh(parse_result)
        db.refresh(inbox_item)
        return capture, parse_result, inbox_item

    def get_capture(self, db: Session, *, capture_id: uuid.UUID, user_id: uuid.UUID) -> CaptureInput:
        capture = db.get(CaptureInput, capture_id)
        if capture is None or capture.user_id != user_id:
            raise NotFoundError("Capture not found")
        return capture


capture_service = CaptureService()
