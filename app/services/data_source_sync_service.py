from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataSourceConnection
from app.models.data_source_sync_run import DataSourceSyncRun
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
        trigger: str = "worker",
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> dict:
        connection = self._get_connection(db, connection_id=connection_id, user_id=user_id)
        run = self._start_sync_run(
            db,
            connection=connection,
            trigger=trigger,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        skip_reason = self._skip_reason(connection)
        if skip_reason is not None:
            return self._skip(db, connection=connection, run=run, reason=skip_reason)

        fetched_from_provider = items is None
        provider_mode: str | None = None
        imported_count = 0
        reused_count = 0
        import_record_ids: list[str] = []
        try:
            if fetched_from_provider:
                fetch_result = self._fetch_provider_items(connection, limit=fetch_limit)
                items = fetch_result["items"]
                provider_mode = fetch_result["provider_mode"]
                if sync_cursor is None:
                    sync_cursor = fetch_result["next_cursor"]

            for item in items or []:
                result = external_capture_import_service.import_item(
                    db,
                    user_id=connection.user_id,
                    data_source_connection_id=connection.id,
                    external_item_id=str(item.get("external_item_id", "")),
                    external_item_type=str(
                        item.get("external_item_type") or self._default_external_item_type(connection)
                    ),
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
            processed_count = len(items or [])
            self._finish_sync_run(
                run,
                status="succeeded",
                processed_count=processed_count,
                imported_count=imported_count,
                reused_count=reused_count,
                fetched_from_provider=fetched_from_provider,
                provider_mode=provider_mode,
                sync_cursor_after=connection.sync_cursor,
                metadata={"import_record_ids": import_record_ids},
            )
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
                    "sync_run_id": str(run.id),
                    "processed_count": processed_count,
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
            db.refresh(run)
            return self._result(
                connection,
                status="synced",
                sync_run=run,
                processed_count=processed_count,
                imported_count=imported_count,
                reused_count=reused_count,
                import_record_ids=import_record_ids,
                fetched_from_provider=fetched_from_provider,
                provider_mode=provider_mode,
            )
        except Exception as exc:
            db.rollback()
            self._record_failure(
                db,
                connection=connection,
                run_id=run.id,
                error=exc,
                processed_count=len(items or []),
                imported_count=imported_count,
                reused_count=reused_count,
                fetched_from_provider=fetched_from_provider,
                provider_mode=provider_mode,
                import_record_ids=import_record_ids,
            )
            raise

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
        results = []
        for connection in connections:
            try:
                results.append(self.sync_connection(db, connection_id=connection.id, trigger="ready_batch"))
            except Exception as exc:
                sync_run = self._latest_sync_run(db, connection=connection)
                results.append(self._failure_result(connection, sync_run=sync_run, error=exc))
        failed_connection_count = len([result for result in results if result["status"] == "failed"])
        return {
            "status": "partial_failed" if failed_connection_count else "synced",
            "processed_connection_count": len(results),
            "failed_connection_count": failed_connection_count,
            "results": results,
        }

    def list_sync_runs(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[DataSourceSyncRun]:
        connection = self._get_connection(db, connection_id=connection_id, user_id=user_id)
        stmt = (
            select(DataSourceSyncRun)
            .where(
                DataSourceSyncRun.user_id == user_id,
                DataSourceSyncRun.data_source_connection_id == connection.id,
            )
            .order_by(DataSourceSyncRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(stmt).all())

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

    def _skip(self, db: Session, *, connection: DataSourceConnection, run: DataSourceSyncRun, reason: str) -> dict:
        self._finish_sync_run(run, status="skipped", skip_reason=reason)
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
                "sync_run_id": str(run.id),
                "reason": reason,
                "status": connection.status.value,
                "sync_enabled": connection.sync_enabled,
            },
        )
        db.commit()
        db.refresh(run)
        return self._result(connection, status="skipped", sync_run=run, skip_reason=reason)

    def _result(
        self,
        connection: DataSourceConnection,
        *,
        status: str,
        sync_run: DataSourceSyncRun | None = None,
        skip_reason: str | None = None,
        processed_count: int = 0,
        imported_count: int = 0,
        reused_count: int = 0,
        import_record_ids: list[str] | None = None,
        fetched_from_provider: bool = False,
        provider_mode: str | None = None,
        error_message: str | None = None,
    ) -> dict:
        return {
            "status": status,
            "sync_run_id": sync_run.id if sync_run else None,
            "skip_reason": skip_reason,
            "error_message": error_message,
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
            "retryable": sync_run.retryable if sync_run else False,
            "next_retry_at": sync_run.next_retry_at if sync_run else None,
        }

    def _failure_result(
        self,
        connection: DataSourceConnection,
        *,
        sync_run: DataSourceSyncRun | None,
        error: Exception,
    ) -> dict:
        if sync_run is None:
            return self._result(connection, status="failed", error_message=str(error))

        metadata = sync_run.run_metadata or {}
        return self._result(
            connection,
            status="failed",
            sync_run=sync_run,
            processed_count=sync_run.processed_count,
            imported_count=sync_run.imported_count,
            reused_count=sync_run.reused_count,
            import_record_ids=metadata.get("import_record_ids", []),
            fetched_from_provider=sync_run.fetched_from_provider,
            provider_mode=sync_run.provider_mode,
            error_message=sync_run.error_message or str(error),
        )

    def _latest_sync_run(
        self,
        db: Session,
        *,
        connection: DataSourceConnection,
    ) -> DataSourceSyncRun | None:
        stmt = (
            select(DataSourceSyncRun)
            .where(DataSourceSyncRun.data_source_connection_id == connection.id)
            .order_by(DataSourceSyncRun.created_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()

    def _start_sync_run(
        self,
        db: Session,
        *,
        connection: DataSourceConnection,
        trigger: str,
        attempt: int,
        max_attempts: int,
    ) -> DataSourceSyncRun:
        run = DataSourceSyncRun(
            user_id=connection.user_id,
            data_source_connection_id=connection.id,
            source_type=connection.source_type,
            provider=connection.provider,
            status="running",
            trigger=trigger,
            attempt=attempt,
            max_attempts=max_attempts,
            sync_cursor_before=connection.sync_cursor,
            run_metadata={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def _finish_sync_run(
        self,
        run: DataSourceSyncRun,
        *,
        status: str,
        skip_reason: str | None = None,
        error_message: str | None = None,
        processed_count: int = 0,
        imported_count: int = 0,
        reused_count: int = 0,
        fetched_from_provider: bool = False,
        provider_mode: str | None = None,
        sync_cursor_after: str | None = None,
        retryable: bool = False,
        next_retry_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> None:
        finished_at = utc_now()
        run.status = status
        run.skip_reason = skip_reason
        run.error_message = error_message
        run.processed_count = processed_count
        run.imported_count = imported_count
        run.reused_count = reused_count
        run.fetched_from_provider = fetched_from_provider
        run.provider_mode = provider_mode
        run.sync_cursor_after = sync_cursor_after
        run.retryable = retryable
        run.next_retry_at = next_retry_at
        run.finished_at = finished_at
        run.duration_ms = self._duration_ms(started_at=run.started_at, finished_at=finished_at)
        run.run_metadata = metadata or {}

    def _duration_ms(self, *, started_at: datetime, finished_at: datetime) -> int:
        if started_at.tzinfo is None and finished_at.tzinfo is not None:
            started_at = started_at.replace(tzinfo=finished_at.tzinfo)
        if started_at.tzinfo is not None and finished_at.tzinfo is None:
            finished_at = finished_at.replace(tzinfo=started_at.tzinfo)
        return max(int((finished_at - started_at).total_seconds() * 1000), 0)

    def _record_failure(
        self,
        db: Session,
        *,
        connection: DataSourceConnection,
        run_id: uuid.UUID,
        error: Exception,
        processed_count: int,
        imported_count: int,
        reused_count: int,
        fetched_from_provider: bool,
        provider_mode: str | None,
        import_record_ids: list[str],
    ) -> None:
        run = db.get(DataSourceSyncRun, run_id)
        if run is None:
            return
        retryable = run.attempt < run.max_attempts
        next_retry_at = utc_now() + timedelta(minutes=5) if retryable else None
        self._finish_sync_run(
            run,
            status="failed",
            error_message=str(error),
            processed_count=processed_count,
            imported_count=imported_count,
            reused_count=reused_count,
            fetched_from_provider=fetched_from_provider,
            provider_mode=provider_mode,
            sync_cursor_after=connection.sync_cursor,
            retryable=retryable,
            next_retry_at=next_retry_at,
            metadata={"import_record_ids": import_record_ids, "error_type": type(error).__name__},
        )
        activity_event_service.add_event(
            db,
            user_id=connection.user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type="DATA_SOURCE_SYNC_FAILED",
            actor_type=ActorType.SYSTEM,
            source=EventSource.WORKER,
            payload={
                "source_type": connection.source_type.value,
                "provider": connection.provider,
                "sync_run_id": str(run.id),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "retryable": retryable,
                "next_retry_at": next_retry_at.isoformat() if next_retry_at else None,
            },
        )
        db.commit()

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
