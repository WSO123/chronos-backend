import unittest
from unittest.mock import patch

from app.models.activity_event import ActivityEvent
from app.models.enums import ActorType, DataSourceStatus, DataSourceType, EventSource
from app.models.external_import import ExternalCaptureImport
from app.models.inbox import InboxItem
from app.services.data_source_service import data_source_service
from app.services.data_source_sync_service import data_source_sync_service
from app.workers.tasks import sync_data_source_connection, sync_ready_data_source_connections
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class DataSourceSyncServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_sync_connection_imports_items_and_updates_cursor(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )

        result = data_source_sync_service.sync_connection(
            self.db,
            connection_id=connection.id,
            items=[
                {
                    "external_item_id": "calendar-sync-1",
                    "external_item_type": "calendar_event",
                    "title": "完成同步验证",
                    "body": "来自占位 worker 的日历条目",
                    "occurred_at": "2026-05-17T09:00:00Z",
                    "external_payload": {"html_link": "https://calendar.example/sync-1"},
                }
            ],
            sync_cursor="cursor-1",
        )
        self.db.refresh(connection)
        sync_event = (
            self.db.query(ActivityEvent)
            .filter(ActivityEvent.event_type == "DATA_SOURCE_SYNCED")
            .one()
        )

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["reused_count"], 0)
        self.assertEqual(connection.sync_cursor, "cursor-1")
        self.assertIsNotNone(connection.last_sync_at)
        self.assertEqual(self.db.query(ExternalCaptureImport).count(), 1)
        self.assertEqual(self.db.query(InboxItem).count(), 1)
        self.assertEqual(sync_event.actor_type, ActorType.SYSTEM)
        self.assertEqual(sync_event.source, EventSource.WORKER)
        self.assertEqual(sync_event.payload["processed_count"], 1)

    def test_sync_connection_is_idempotent_for_existing_external_items(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )
        item = {
            "external_item_id": "email-sync-1",
            "external_item_type": "email_message",
            "title": "完成邮件同步验证",
        }

        first = data_source_sync_service.sync_connection(self.db, connection_id=connection.id, items=[item])
        second = data_source_sync_service.sync_connection(self.db, connection_id=connection.id, items=[item])

        self.assertEqual(first["imported_count"], 1)
        self.assertEqual(first["reused_count"], 0)
        self.assertEqual(second["imported_count"], 0)
        self.assertEqual(second["reused_count"], 1)
        self.assertEqual(self.db.query(ExternalCaptureImport).count(), 1)

    def test_sync_connection_skips_unsyncable_connections(self):
        paused = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )
        data_source_service.update_connection(
            self.db,
            connection_id=paused.id,
            user_id=self.user.id,
            updates={"status": DataSourceStatus.PAUSED},
        )
        health = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )

        paused_result = data_source_sync_service.sync_connection(self.db, connection_id=paused.id)
        health_result = data_source_sync_service.sync_connection(self.db, connection_id=health.id)

        self.assertEqual(paused_result["status"], "skipped")
        self.assertEqual(paused_result["skip_reason"], "status_not_connected")
        self.assertEqual(health_result["status"], "skipped")
        self.assertEqual(health_result["skip_reason"], "unsupported_source")
        self.assertEqual(self.db.query(ExternalCaptureImport).count(), 0)
        self.assertEqual(
            self.db.query(ActivityEvent)
            .filter(ActivityEvent.event_type == "DATA_SOURCE_SYNC_SKIPPED")
            .count(),
            2,
        )

    def test_worker_sync_connection_uses_session_and_returns_json_ready_result(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = sync_data_source_connection.run(
                str(connection.id),
                items=[
                    {
                        "external_item_id": "worker-email-1",
                        "title": "完成 worker 占位同步",
                    }
                ],
                sync_cursor="worker-cursor",
            )
        self.db.refresh(connection)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["connection_id"], str(connection.id))
        self.assertEqual(result["source_type"], "email")
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(connection.sync_cursor, "worker-cursor")

    def test_worker_sync_ready_connections_filters_calendar_and_email_only(self):
        calendar = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )
        email = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )
        data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = sync_ready_data_source_connections.run(limit=10)
        self.db.refresh(calendar)
        self.db.refresh(email)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["processed_connection_count"], 2)
        self.assertIsNotNone(calendar.last_sync_at)
        self.assertIsNotNone(email.last_sync_at)


if __name__ == "__main__":
    unittest.main()
