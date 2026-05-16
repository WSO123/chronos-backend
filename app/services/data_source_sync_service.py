from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataSourceConnection
from app.models.enums import ActorType, DataSourceStatus, DataSourceType, EntityType, EventSource
from app.models.mixins import utc_now
from app.providers.data_sources import data_source_provider_registry
from app.services.activity_event_service import activity_event_service
from app.services.errors import NotFoundError
from app.services.external_capture_import_service import external_capture_import_service


class DataSourceSyncService:
    syncable_source_types = {DataSourceType.CALENDAR, DataSourceType.EMAIL}

    def sync_connection(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        items: list[dict[str, Any]] | None = None,
        sync_cursor: str | None = None,
        fetch_limit: int = 50,
    ) -> dict:
        connection = self._get_connection(db, connection_id=connection_id, user_id=user_id)
        skip_reason = self._skip_reason(connection)
        if skip_reason is not None:
            return self._skip(db, connection=connection, reason=skip_reason)

        fetched_from_provider = items is None
        provider_mode: str | None = None
        if fetched_from_provider:
            fetch_result = self._fetch_provider_items(connection, limit=fetch_limit)
            items = fetch_result["items"]
            provider_mode = fetch_result["provider_mode"]
            if sync_cursor is None:
                sync_cursor = fetch_result["next_cursor"]

        imported_count = 0
        reused_count = 0
        import_record_ids: list[str] = []
        for item in items or []:
            result = external_capture_import_service.import_item(
                db,
                user_id=connection.user_id,
                data_source_connection_id=connection.id,
                external_item_id=str(item.get("external_item_id", "")),
                external_item_type=str(item.get("external_item_type") or self._default_external_item_type(connection)),
                title=str(item.get("title", "")),
                body=item.get("body"),
                occurred_at=self._parse_occurred_at(item.get("occurred_at")),
                external_payload=item.get("external_payload") or {},
            )
            if result["created"]:
                imported_count += 1
            else:
                reused_count += 1
            import_record_ids.append(str(result["import_record"].id))

        synced_at = utc_now()
        connection.last_sync_at = synced_at
        if sync_cursor is not None:
            connection.sync_cursor = sync_cursor
        activity_event_service.add_event(
            db,
            user_id=connection.user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type="DATA_SOURCE_SYNCED",
            actor_type=ActorType.SYSTEM,
            source=EventSource.WORKER,
            payload={
                "source_type": connection.source_type.value,
                "provider": connection.provider,
                "processed_count": len(items or []),
                "imported_count": imported_count,
                "reused_count": reused_count,
                "sync_cursor": connection.sync_cursor,
                "import_record_ids": import_record_ids,
                "fetched_from_provider": fetched_from_provider,
                "provider_mode": provider_mode,
            },
        )
        db.commit()
        db.refresh(connection)
        return self._result(
            connection,
            status="synced",
            processed_count=len(items or []),
            imported_count=imported_count,
            reused_count=reused_count,
            import_record_ids=import_record_ids,
            fetched_from_provider=fetched_from_provider,
            provider_mode=provider_mode,
        )

    def sync_ready_connections(self, db: Session, *, limit: int = 50) -> dict:
        stmt = (
            select(DataSourceConnection)
            .where(
                DataSourceConnection.source_type.in_(self.syncable_source_types),
                DataSourceConnection.status == DataSourceStatus.CONNECTED,
                DataSourceConnection.sync_enabled.is_(True),
            )
            .order_by(DataSourceConnection.updated_at)
            .limit(limit)
        )
        connections = list(db.scalars(stmt).all())
        results = [
            self.sync_connection(db, connection_id=connection.id)
            for connection in connections
        ]
        return {
            "status": "synced",
            "processed_connection_count": len(results),
            "results": results,
        }

    def _get_connection(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> DataSourceConnection:
        connection = db.get(DataSourceConnection, connection_id)
        if connection is None or (user_id is not None and connection.user_id != user_id):
            raise NotFoundError("Data source connection not found")
        return connection

    def _skip_reason(self, connection: DataSourceConnection) -> str | None:
        if connection.source_type not in self.syncable_source_types:
            return "unsupported_source"
        if connection.status != DataSourceStatus.CONNECTED:
            return "status_not_connected"
        if not connection.sync_enabled:
            return "sync_disabled"
        return None

    def _skip(self, db: Session, *, connection: DataSourceConnection, reason: str) -> dict:
        activity_event_service.add_event(
            db,
            user_id=connection.user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type="DATA_SOURCE_SYNC_SKIPPED",
            actor_type=ActorType.SYSTEM,
            source=EventSource.WORKER,
            payload={
                "source_type": connection.source_type.value,
                "provider": connection.provider,
                "reason": reason,
                "status": connection.status.value,
                "sync_enabled": connection.sync_enabled,
            },
        )
        db.commit()
        return self._result(connection, status="skipped", skip_reason=reason)

    def _result(
        self,
        connection: DataSourceConnection,
        *,
        status: str,
        skip_reason: str | None = None,
        processed_count: int = 0,
        imported_count: int = 0,
        reused_count: int = 0,
        import_record_ids: list[str] | None = None,
        fetched_from_provider: bool = False,
        provider_mode: str | None = None,
    ) -> dict:
        return {
            "status": status,
            "skip_reason": skip_reason,
            "connection_id": connection.id,
            "user_id": connection.user_id,
            "source_type": connection.source_type,
            "provider": connection.provider,
            "processed_count": processed_count,
            "imported_count": imported_count,
            "reused_count": reused_count,
            "import_record_ids": import_record_ids or [],
            "sync_cursor": connection.sync_cursor,
            "last_sync_at": connection.last_sync_at,
            "fetched_from_provider": fetched_from_provider,
            "provider_mode": provider_mode,
        }

    def _fetch_provider_items(self, connection: DataSourceConnection, *, limit: int) -> dict:
        adapter = data_source_provider_registry.adapter_for(connection)
        if adapter is None:
            return {"items": [], "next_cursor": connection.sync_cursor, "provider_mode": None}
        fetch_result = adapter.fetch_items(connection, limit=limit)
        return {
            "items": fetch_result.items,
            "next_cursor": fetch_result.next_cursor,
            "provider_mode": fetch_result.provider_mode,
        }

    def _default_external_item_type(self, connection: DataSourceConnection) -> str:
        if connection.source_type == DataSourceType.CALENDAR:
            return "calendar_event"
        if connection.source_type == DataSourceType.EMAIL:
            return "email_message"
        return "external_item"

    def _parse_occurred_at(self, value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return None


data_source_sync_service = DataSourceSyncService()
