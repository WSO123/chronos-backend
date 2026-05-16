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
        return self._create_parsed_capture(
            db,
            user_id=user_id,
            raw_text=raw_text,
            input_type=CaptureInputType.TEXT,
            source=CaptureSource.MANUAL,
            parse_context=None,
            commit=True,
        )

    def create_external_capture(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        raw_text: str,
        source: CaptureSource,
        parse_context: dict | None = None,
        commit: bool = True,
    ) -> tuple[CaptureInput, AIParseResult, InboxItem]:
        if source not in {CaptureSource.CALENDAR, CaptureSource.EMAIL}:
            raise ValidationDomainError("External capture source must be calendar or email")
        return self._create_parsed_capture(
            db,
            user_id=user_id,
            raw_text=raw_text,
            input_type=CaptureInputType.EXTERNAL,
            source=source,
            parse_context=parse_context,
            commit=commit,
        )

    def _create_parsed_capture(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        raw_text: str,
        input_type: CaptureInputType,
        source: CaptureSource,
        parse_context: dict | None,
        commit: bool,
    ) -> tuple[CaptureInput, AIParseResult, InboxItem]:
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            raise ValidationDomainError("Capture text cannot be empty")

        capture = CaptureInput(
            user_id=user_id,
            input_type=input_type,
            raw_text=cleaned_text,
            source=source,
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
            payload={"input_type": input_type.value, "source": source.value},
        )

        parsed = rule_capture_parser.parse_text(cleaned_text)
        raw_model_output = dict(parsed.raw_model_output)
        if parse_context:
            raw_model_output["context"] = parse_context
        parse_result = AIParseResult(
            capture_input_id=capture.id,
            result_type=parsed.result_type,
            title=parsed.title,
            description=parsed.description,
            estimated_duration_min=parsed.estimated_duration_min,
            suggested_priority=parsed.suggested_priority,
            suggested_deadline=parsed.suggested_deadline,
            confidence=Decimal(str(parsed.confidence)),
            raw_model_output=raw_model_output,
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
            payload={"result_type": parsed.result_type.value, "confidence": parsed.confidence, "source": source.value},
        )
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.INBOX,
            entity_id=inbox_item.id,
            event_type="INBOX_ITEM_CREATED",
            payload={"item_type": parsed.item_type.value},
        )
        if commit:
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
