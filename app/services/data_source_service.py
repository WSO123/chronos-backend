from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataSourceConnection
from app.models.enums import ActorType, DataSourceStatus, DataSourceType, EntityType
from app.models.user import User
from app.services.activity_event_service import activity_event_service
from app.services.errors import NotFoundError, ValidationDomainError


SUPPORTED_DATA_SOURCES = {
    DataSourceType.CALENDAR: {
        "display_name": "Calendar",
        "supported_providers": ["google_calendar", "outlook_calendar", "apple_calendar"],
        "default_scopes": ["calendar.read"],
        "capabilities": ["task_import", "rolling_plan_context", "reminder_context"],
    },
    DataSourceType.EMAIL: {
        "display_name": "Email",
        "supported_providers": ["gmail", "outlook_email"],
        "default_scopes": ["email.read"],
        "capabilities": ["task_import", "source_context"],
    },
    DataSourceType.HEALTH: {
        "display_name": "Health",
        "supported_providers": ["apple_health", "google_fit"],
        "default_scopes": ["sleep.read", "stress.read"],
        "capabilities": ["energy_prediction", "insight_context"],
    },
}


class DataSourceService:
    def list_sources(self, db: Session, *, user_id: uuid.UUID) -> dict:
        self._ensure_user(db, user_id=user_id)
        connections = self._connections_for_user(db, user_id=user_id)
        by_source: dict[DataSourceType, list[DataSourceConnection]] = {}
        for connection in connections:
            by_source.setdefault(connection.source_type, []).append(connection)

        sources = []
        for source_type, catalog in SUPPORTED_DATA_SOURCES.items():
            connection = self._primary_connection(by_source.get(source_type, []))
            sources.append(
                {
                    "source_type": source_type,
                    "display_name": catalog["display_name"],
                    "supported_providers": catalog["supported_providers"],
                    "default_scopes": catalog["default_scopes"],
                    "capabilities": catalog["capabilities"],
                    "status": connection.status if connection else DataSourceStatus.DISCONNECTED,
                    "connection": connection,
                }
            )

        connected_count = len(
            [connection for connection in connections if connection.status == DataSourceStatus.CONNECTED]
        )
        return {"sources": sources, "connected_count": connected_count}

    def connect_source(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        source_type: DataSourceType,
        provider: str,
        external_account_label: str | None = None,
        scopes: list[str] | None = None,
        sync_enabled: bool = True,
        connection_metadata: dict | None = None,
    ) -> DataSourceConnection:
        self._ensure_user(db, user_id=user_id)
        self._validate_provider(source_type=source_type, provider=provider)
        now = datetime.now(timezone.utc)
        connection = self._connection_by_source_provider(
            db,
            user_id=user_id,
            source_type=source_type,
            provider=provider,
        )
        created = connection is None
        if connection is None:
            connection = DataSourceConnection(
                user_id=user_id,
                source_type=source_type,
                provider=provider,
                status=DataSourceStatus.CONNECTED,
                connected_at=now,
                revoked_at=None,
            )
            db.add(connection)
        else:
            connection.status = DataSourceStatus.CONNECTED
            connection.connected_at = connection.connected_at or now
            connection.revoked_at = None

        connection.external_account_label = external_account_label
        connection.scopes = scopes if scopes is not None else self._default_scopes(source_type)
        connection.sync_enabled = sync_enabled
        connection.connection_metadata = connection_metadata or {}
        db.flush()
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type="DATA_SOURCE_CONNECTED" if created else "DATA_SOURCE_RECONNECTED",
            actor_type=ActorType.USER,
            payload={
                "source_type": source_type.value,
                "provider": provider,
                "sync_enabled": sync_enabled,
                "scopes": connection.scopes,
            },
        )
        db.commit()
        db.refresh(connection)
        return connection

    def update_connection(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID,
        updates: dict,
    ) -> DataSourceConnection:
        connection = self._get_user_connection(db, connection_id=connection_id, user_id=user_id)
        previous_status = connection.status

        for field in (
            "status",
            "external_account_label",
            "scopes",
            "sync_enabled",
            "sync_cursor",
            "last_sync_at",
            "connection_metadata",
        ):
            if field in updates:
                setattr(connection, field, updates[field])

        if connection.status == DataSourceStatus.CONNECTED and connection.connected_at is None:
            connection.connected_at = datetime.now(timezone.utc)
        if previous_status != connection.status and connection.status == DataSourceStatus.DISCONNECTED:
            connection.revoked_at = datetime.now(timezone.utc)
            connection.sync_enabled = False

        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type="DATA_SOURCE_UPDATED",
            actor_type=ActorType.USER,
            payload={
                "source_type": connection.source_type.value,
                "provider": connection.provider,
                "changed_fields": sorted(updates),
                "previous_status": previous_status.value,
                "current_status": connection.status.value,
            },
        )
        db.commit()
        db.refresh(connection)
        return connection

    def disconnect_source(
        self,
        db: Session,
        *,
        connection_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DataSourceConnection:
        connection = self._get_user_connection(db, connection_id=connection_id, user_id=user_id)
        connection.status = DataSourceStatus.DISCONNECTED
        connection.sync_enabled = False
        connection.revoked_at = datetime.now(timezone.utc)
        activity_event_service.add_event(
            db,
            user_id=user_id,
            entity_type=EntityType.DATA_SOURCE,
            entity_id=connection.id,
            event_type="DATA_SOURCE_DISCONNECTED",
            actor_type=ActorType.USER,
            payload={
                "source_type": connection.source_type.value,
                "provider": connection.provider,
            },
        )
        db.commit()
        db.refresh(connection)
        return connection

    def _ensure_user(self, db: Session, *, user_id: uuid.UUID) -> User:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _connections_for_user(self, db: Session, *, user_id: uuid.UUID) -> list[DataSourceConnection]:
        stmt = select(DataSourceConnection).where(DataSourceConnection.user_id == user_id)
        return list(db.scalars(stmt).all())

    def _connection_by_source_provider(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        source_type: DataSourceType,
        provider: str,
    ) -> DataSourceConnection | None:
        stmt = select(DataSourceConnection).where(
            DataSourceConnection.user_id == user_id,
            DataSourceConnection.source_type == source_type,
            DataSourceConnection.provider == provider,
        )
        return db.scalars(stmt).first()

    def _get_user_connection(
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

    def _validate_provider(self, *, source_type: DataSourceType, provider: str) -> None:
        supported_providers = SUPPORTED_DATA_SOURCES[source_type]["supported_providers"]
        if provider not in supported_providers:
            raise ValidationDomainError(f"Provider {provider} is not supported for {source_type.value}")

    def _default_scopes(self, source_type: DataSourceType) -> list[str]:
        return list(SUPPORTED_DATA_SOURCES[source_type]["default_scopes"])

    def _primary_connection(self, connections: list[DataSourceConnection]) -> DataSourceConnection | None:
        if not connections:
            return None
        status_rank = {
            DataSourceStatus.CONNECTED: 0,
            DataSourceStatus.NEEDS_REAUTH: 1,
            DataSourceStatus.PAUSED: 2,
            DataSourceStatus.DISCONNECTED: 3,
        }
        return sorted(
            connections,
            key=lambda connection: (
                status_rank[connection.status],
                -(connection.updated_at.timestamp() if connection.updated_at else 0),
            ),
        )[0]


data_source_service = DataSourceService()
