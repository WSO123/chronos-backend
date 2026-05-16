from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
import uuid

from app.core.celery import celery_app
from app.core.db import SessionLocal
from app.services.data_source_sync_service import data_source_sync_service
from app.services.health_sync_service import health_sync_service


@celery_app.task(name="data_source.sync_connection")
def sync_data_source_connection(
    connection_id: str,
    items: list[dict[str, Any]] | None = None,
    sync_cursor: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        result = data_source_sync_service.sync_connection(
            db,
            connection_id=uuid.UUID(connection_id),
            items=items,
            sync_cursor=sync_cursor,
        )
        return _json_ready(result)
    finally:
        db.close()


@celery_app.task(name="data_source.sync_ready_connections")
def sync_ready_data_source_connections(limit: int = 50) -> dict:
    db = SessionLocal()
    try:
        result = data_source_sync_service.sync_ready_connections(db, limit=limit)
        return _json_ready(result)
    finally:
        db.close()


@celery_app.task(name="health.sync_energy_connection")
def sync_health_energy_connection(
    connection_id: str,
    metrics: list[dict[str, Any]] | None = None,
    end_date: str | None = None,
    days: int = 7,
) -> dict:
    db = SessionLocal()
    try:
        result = health_sync_service.sync_energy_metrics(
            db,
            connection_id=uuid.UUID(connection_id),
            metrics=metrics,
            end_date=date.fromisoformat(end_date) if end_date else None,
            days=days,
        )
        return _json_ready(result)
    finally:
        db.close()


@celery_app.task(name="health.sync_ready_energy_connections")
def sync_ready_health_energy_connections(limit: int = 50) -> dict:
    db = SessionLocal()
    try:
        result = health_sync_service.sync_ready_energy_connections(db, limit=limit)
        return _json_ready(result)
    finally:
        db.close()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value
