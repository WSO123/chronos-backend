from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.data_source import DataSourceConnection
from app.models.data_source_sync_run import DataSourceSyncRun
from app.models.enums import ActorType, DataSourceStatus, DataSourceType, EntityType, EventSource
from app.models.mixins import utc_now
from app.providers.health import health_provider_registry
from app.services.activity_event_service import activity_event_service
from app.services.energy_service import energy_service
from app.services.errors import NotFoundError


class HealthSyncService:
    def sync_energy_metrics(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        metrics: list[dict[str, Any]] | None = None,
        end_date: date | None = None,
        days: int = 7,
        trigger: str = "health_worker",
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

        fetched_from_provider = metrics is None
        provider_mode: str | None = None
        try:
            if fetched_from_provider:
                fetch_result = self._fetch_provider_metrics(connection, days=days, end_date=end_date)
                metrics = fetch_result["metrics"]
                provider_mode = fetch_result["provider_mode"]
                if fetch_result["next_cursor"] is not None:
                    connection.sync_cursor = fetch_result["next_cursor"]

            imported_metric_ids: list[str] = []
            for metric in metrics or []:
                imported = energy_service.upsert_daily_metric(
                    db,
                    user_id=connection.user_id,
                    payload=self._metric_payload(connection=connection, metric=metric, provider_mode=provider_mode),
                )
                imported_metric_ids.append(str(imported.id))

            connection.last_sync_at = utc_now()
            processed_count = len(metrics or [])
            self._finish_sync_run(
                run,
                status="succeeded",
                processed_count=processed_count,
                imported_count=processed_count,
                fetched_from_provider=fetched_from_provider,
                provider_mode=provider_mode,
                sync_cursor_after=connection.sync_cursor,
                metadata={"energy_metric_ids": imported_metric_ids},
            )
            self._add_event(
                db,
                connection=connection,
                event_type="DATA_SOURCE_SYNCED",
                run=run,
                payload={
                    "processed_count": processed_count,
                    "imported_count": processed_count,
                    "energy_metric_ids": imported_metric_ids,
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
                imported_count=processed_count,
                energy_metric_ids=imported_metric_ids,
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
                processed_count=len(metrics or []),
                fetched_from_provider=fetched_from_provider,
                provider_mode=provider_mode,
            )
            raise

    def sync_ready_energy_connections(self, db: Session, *, limit: int = 50) -> dict:
        stmt = (
            select(DataSourceConnection)
            .where(
                DataSourceConnection.source_type == DataSourceType.HEALTH,
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
                results.append(
                    self.sync_energy_metrics(
                        db,
                        connection_id=connection.id,
                        trigger="health_ready_batch",
                    )
                )
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
        if connection.source_type != DataSourceType.HEALTH:
            return "unsupported_source"
        if connection.status != DataSourceStatus.CONNECTED:
            return "status_not_connected"
        if not connection.sync_enabled:
            return "sync_disabled"
        return None

    def _skip(self, db: Session, *, connection: DataSourceConnection, run: DataSourceSyncRun, reason: str) -> dict:
        self._finish_sync_run(run, status="skipped", skip_reason=reason)
        self._add_event(
            db,
            connection=connection,
            event_type="DATA_SOURCE_SYNC_SKIPPED",
            run=run,
            payload={"reason": reason, "status": connection.status.value, "sync_enabled": connection.sync_enabled},
        )
        db.commit()
        db.refresh(run)
        return self._result(connection, status="skipped", sync_run=run, skip_reason=reason)

    def _metric_payload(
        self,
        *,
        connection: DataSourceConnection,
        metric: dict[str, Any],
        provider_mode: str | None,
    ) -> dict:
        metadata = {
            **(metric.get("metric_metadata") or {}),
            "provider": connection.provider,
        }
        if provider_mode is not None:
            metadata["provider_mode"] = provider_mode
        return {
            "metric_date": self._parse_metric_date(metric.get("metric_date")),
            "source": "health_import",
            "data_source_connection_id": connection.id,
            "sleep_minutes": metric.get("sleep_minutes"),
            "sleep_quality_score": metric.get("sleep_quality_score"),
            "stress_score": metric.get("stress_score"),
            "energy_score": metric.get("energy_score"),
            "note": metric.get("note"),
            "metric_metadata": metadata,
        }

    def _parse_metric_date(self, value: Any) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return date.fromisoformat(str(value))

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
        run.reused_count = 0
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
        fetched_from_provider: bool,
        provider_mode: str | None,
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
            fetched_from_provider=fetched_from_provider,
            provider_mode=provider_mode,
            sync_cursor_after=connection.sync_cursor,
            retryable=retryable,
            next_retry_at=next_retry_at,
            metadata={"error_type": type(error).__name__},
        )
        self._add_event(
            db,
            connection=connection,
            event_type="DATA_SOURCE_SYNC_FAILED",
            run=run,
            payload={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "retryable": retryable,
                "next_retry_at": next_retry_at.isoformat() if next_retry_at else None,
            },
        )
        db.commit()

    def _add_event(
        self,
        db: Session,
        *,
        connection: DataSourceConnection,
        event_type: str,
        run: DataSourceSyncRun,
        payload: dict,
    ) -> ActivityEvent:
        return activity_event_service.add_event(
            db,
            user_id=connection.user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type=event_type,
            actor_type=ActorType.SYSTEM,
            source=EventSource.WORKER,
            payload={
                "source_type": connection.source_type.value,
                "provider": connection.provider,
                "sync_run_id": str(run.id),
                **payload,
            },
        )

    def _fetch_provider_metrics(
        self,
        connection: DataSourceConnection,
        *,
        days: int,
        end_date: date | None,
    ) -> dict:
        adapter = health_provider_registry.adapter_for(connection)
        if adapter is None:
            return {"metrics": [], "next_cursor": None, "provider_mode": None}
        result = adapter.fetch_daily_metrics(connection, days=days, end_date=end_date)
        return {
            "metrics": result.metrics,
            "next_cursor": result.next_cursor,
            "provider_mode": result.provider_mode,
        }

    def _result(
        self,
        connection: DataSourceConnection,
        *,
        status: str,
        sync_run: DataSourceSyncRun | None = None,
        skip_reason: str | None = None,
        error_message: str | None = None,
        processed_count: int = 0,
        imported_count: int = 0,
        energy_metric_ids: list[str] | None = None,
        fetched_from_provider: bool = False,
        provider_mode: str | None = None,
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
            "energy_metric_ids": energy_metric_ids or [],
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
            energy_metric_ids=metadata.get("energy_metric_ids", []),
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


health_sync_service = HealthSyncService()
