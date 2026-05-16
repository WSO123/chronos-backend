from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
import uuid

from app.core.celery import celery_app
from app.core.db import SessionLocal
from app.services.data_source_sync_service import data_source_sync_service
from app.services.health_sync_service import health_sync_service
from app.services.reminder_service import reminder_service


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


@celery_app.task(name="reminder.dispatch_due")
def dispatch_due_reminders(
    limit: int = 50,
    channel: str | None = None,
    now: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        result = reminder_service.dispatch_due_reminders(
            db,
            limit=limit,
            channel=channel,
            now=datetime.fromisoformat(now) if now else None,
        )
        result["reminders"] = [reminder_service.to_response(reminder) for reminder in result["reminders"]]
        return _json_ready(result)
    finally:
        db.close()


@celery_app.task(name="reminder.generate_deadline")
def generate_deadline_reminders(
    user_id: str | None = None,
    target_date: str | None = None,
    window_days: int = 1,
    reminder_hour: int | None = None,
) -> dict:
    db = SessionLocal()
    try:
        result = reminder_service.generate_deadline_reminders(
            db,
            user_id=uuid.UUID(user_id) if user_id else None,
            target_date=date.fromisoformat(target_date) if target_date else None,
            window_days=window_days,
            reminder_hour=reminder_hour,
        )
        result["reminders"] = [reminder_service.to_response(reminder) for reminder in result["reminders"]]
        return _json_ready(result)
    finally:
        db.close()


@celery_app.task(name="reminder.generate_execution")
def generate_execution_reminders(
    user_id: str,
    plan_date: str,
    limit: int | None = None,
    start_hour: int | None = None,
    spacing_minutes: int | None = None,
) -> dict:
    db = SessionLocal()
    try:
        result = reminder_service.generate_execution_reminders(
            db,
            user_id=uuid.UUID(user_id),
            plan_date=date.fromisoformat(plan_date),
            limit=limit,
            start_hour=start_hour,
            spacing_minutes=spacing_minutes,
        )
        result["reminders"] = [reminder_service.to_response(reminder) for reminder in result["reminders"]]
        return _json_ready(result)
    finally:
        db.close()


@celery_app.task(name="reminder.cleanup_delivery_attempts")
def cleanup_delivery_attempts(
    retention_days: int = 30,
    now: str | None = None,
    limit: int = 500,
) -> dict:
    db = SessionLocal()
    try:
        result = reminder_service.cleanup_delivery_attempts(
            db,
            retention_days=retention_days,
            now=datetime.fromisoformat(now) if now else None,
            limit=limit,
        )
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
