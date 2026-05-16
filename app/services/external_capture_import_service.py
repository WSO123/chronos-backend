from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.capture import AIParseResult, CaptureInput
from app.models.data_source import DataSourceConnection
from app.models.enums import (
    ActorType,
    CaptureSource,
    DataSourceStatus,
    DataSourceType,
    EntityType,
)
from app.models.external_import import ExternalCaptureImport
from app.models.inbox import InboxItem
from app.services.activity_event_service import activity_event_service
from app.services.capture_service import capture_service
from app.services.errors import InvalidStateError, NotFoundError, ValidationDomainError


class ExternalCaptureImportService:
    def import_item(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        data_source_connection_id: uuid.UUID,
        external_item_id: str,
        external_item_type: str,
        title: str,
        body: str | None = None,
        occurred_at: datetime | None = None,
        external_payload: dict | None = None,
    ) -> dict:
        cleaned_external_item_id = external_item_id.strip()
        cleaned_external_item_type = external_item_type.strip() or "external_item"
        cleaned_title = title.strip()
        cleaned_body = body.strip() if body else None
        if not cleaned_external_item_id:
            raise ValidationDomainError("External item id cannot be empty")
        if not cleaned_title:
            raise ValidationDomainError("External item title cannot be empty")

        connection = self._get_connection(db, connection_id=data_source_connection_id, user_id=user_id)
        source = self._source_for_connection(connection)
        existing = self._existing_import(
            db,
            user_id=user_id,
            source=source,
            provider=connection.provider,
            external_item_id=cleaned_external_item_id,
        )
        if existing is not None:
            return self._import_response(db, import_record=existing, created=False)

        self._ensure_importable(connection)
        normalized_text = self._normalized_text(
            source=source,
            external_item_type=cleaned_external_item_type,
            title=cleaned_title,
            body=cleaned_body,
            occurred_at=occurred_at,
        )
        capture, parse_result, inbox_item = capture_service.create_external_capture(
            db,
            user_id=user_id,
            raw_text=normalized_text,
            source=source,
            parse_context={
                "data_source_connection_id": str(connection.id),
                "provider": connection.provider,
                "external_item_id": cleaned_external_item_id,
                "external_item_type": cleaned_external_item_type,
            },
            commit=False,
        )
        parse_result.title = cleaned_title
        inbox_item.title = cleaned_title
        if cleaned_body and not parse_result.description:
            parse_result.description = cleaned_body
            inbox_item.description = cleaned_body
        import_record = ExternalCaptureImport(
            user_id=user_id,
            data_source_connection_id=connection.id,
            source=source,
            provider=connection.provider,
            external_item_id=cleaned_external_item_id,
            external_item_type=cleaned_external_item_type,
            title=cleaned_title,
            body=cleaned_body,
            occurred_at=occurred_at,
            normalized_text=normalized_text,
            external_payload=external_payload or {},
            capture_input_id=capture.id,
            inbox_item_id=inbox_item.id,
        )
        db.add(import_record)
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.CAPTURE,
            entity_id=capture.id,
            event_type="EXTERNAL_CAPTURE_IMPORTED",
            actor_type=ActorType.SYSTEM,
            payload={
                "external_import_id": str(import_record.id),
                "source": source.value,
                "provider": connection.provider,
                "external_item_id": cleaned_external_item_id,
                "external_item_type": cleaned_external_item_type,
                "inbox_item_id": str(inbox_item.id),
            },
        )
        db.commit()
        db.refresh(import_record)
        db.refresh(capture)
        db.refresh(parse_result)
        db.refresh(inbox_item)
        return {
            "import_record": import_record,
            "capture": capture,
            "parse_result": parse_result,
            "inbox_item": inbox_item,
            "created": True,
        }

    def _get_connection(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DataSourceConnection:
        connection = db.get(DataSourceConnection, connection_id)
        if connection is None or connection.user_id != user_id:
            raise NotFoundError("Data source connection not found")
        return connection

    def _source_for_connection(self, connection: DataSourceConnection) -> CaptureSource:
        if connection.source_type == DataSourceType.CALENDAR:
            return CaptureSource.CALENDAR
        if connection.source_type == DataSourceType.EMAIL:
            return CaptureSource.EMAIL
        raise ValidationDomainError("Only calendar and email sources can import captures")

    def _ensure_importable(self, connection: DataSourceConnection) -> None:
        if connection.status != DataSourceStatus.CONNECTED:
            raise InvalidStateError(f"{connection.status.value} data source cannot import captures")
        if not connection.sync_enabled:
            raise InvalidStateError("Data source sync is disabled")

    def _existing_import(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        source: CaptureSource,
        provider: str,
        external_item_id: str,
    ) -> ExternalCaptureImport | None:
        stmt = select(ExternalCaptureImport).where(
            ExternalCaptureImport.user_id == user_id,
            ExternalCaptureImport.source == source,
            ExternalCaptureImport.provider == provider,
            ExternalCaptureImport.external_item_id == external_item_id,
        )
        return db.scalars(stmt).first()

    def _import_response(self, db: Session, *, import_record: ExternalCaptureImport, created: bool) -> dict:
        capture = db.get(CaptureInput, import_record.capture_input_id) if import_record.capture_input_id else None
        inbox_item = db.get(InboxItem, import_record.inbox_item_id) if import_record.inbox_item_id else None
        if capture is None or inbox_item is None:
            raise InvalidStateError("External import is missing capture or inbox item")
        parse_result = db.get(AIParseResult, inbox_item.parse_result_id)
        if parse_result is None:
            raise InvalidStateError("External import is missing parse result")
        return {
            "import_record": import_record,
            "capture": capture,
            "parse_result": parse_result,
            "inbox_item": inbox_item,
            "created": created,
        }

    def _normalized_text(
        self,
        *,
        source: CaptureSource,
        external_item_type: str,
        title: str,
        body: str | None,
        occurred_at: datetime | None,
    ) -> str:
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValidationDomainError("External item title cannot be empty")
        parts = [
            f"Source: {source.value}",
            f"Type: {external_item_type.strip() or 'external_item'}",
            f"Title: {cleaned_title}",
        ]
        if occurred_at is not None:
            parts.append(f"Occurred at: {occurred_at.isoformat()}")
        if body and body.strip():
            parts.append(f"Body: {body.strip()}")
        return "\n".join(parts)


external_capture_import_service = ExternalCaptureImportService()
