import unittest

from app.models.activity_event import ActivityEvent
from app.models.data_source_sync_run import DataSourceSyncRun
from app.models.enums import DataSourceStatus, DataSourceType, EntityType
from app.services.data_source_service import data_source_service
from app.services.data_source_sync_service import data_source_sync_service
from app.services.errors import NotFoundError, ValidationDomainError
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class DataSourceServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.other_user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_list_sources_returns_p3_catalog_without_connections(self):
        result = data_source_service.list_sources(self.db, user_id=self.user.id)

        self.assertEqual(result["connected_count"], 0)
        self.assertEqual(
            {source["source_type"] for source in result["sources"]},
            {DataSourceType.CALENDAR, DataSourceType.EMAIL, DataSourceType.HEALTH},
        )
        for source in result["sources"]:
            self.assertEqual(source["status"], DataSourceStatus.DISCONNECTED)
            self.assertIsNone(source["connection"])

    def test_connect_source_creates_connection_and_activity_event(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
            external_account_label="alice@example.com",
            sync_enabled=True,
            connection_metadata={"origin": "settings"},
        )
        listed = data_source_service.list_sources(self.db, user_id=self.user.id)
        calendar_source = next(source for source in listed["sources"] if source["source_type"] == DataSourceType.CALENDAR)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(connection.status, DataSourceStatus.CONNECTED)
        self.assertEqual(connection.scopes, ["calendar.read"])
        self.assertEqual(connection.connection_metadata["origin"], "settings")
        self.assertEqual(listed["connected_count"], 1)
        self.assertEqual(calendar_source["connection"].id, connection.id)
        self.assertIn("DATA_SOURCE_CONNECTED", {event.event_type for event in events})
        self.assertIn(EntityType.DATA_SOURCE, {event.entity_type for event in events})

    def test_sync_summary_returns_connection_health_without_syncing(self):
        calendar = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
            connection_metadata={
                "fake_items": [
                    {
                        "external_item_id": "summary-calendar-1",
                        "title": "同步摘要验证",
                    }
                ]
            },
        )
        health = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )
        data_source_service.update_connection(
            self.db,
            connection_id=health.id,
            user_id=self.user.id,
            updates={"status": DataSourceStatus.PAUSED},
        )
        data_source_sync_service.sync_connection(self.db, connection_id=calendar.id)

        summary = data_source_service.sync_summary(self.db, user_id=self.user.id)
        items = {item["connection_id"]: item for item in summary["items"]}

        self.assertEqual(summary["connected_count"], 1)
        self.assertEqual(summary["sync_enabled_count"], 1)
        self.assertEqual(summary["attention_count"], 1)
        self.assertIsNotNone(summary["latest_success_at"])
        self.assertEqual(items[calendar.id]["latest_run_status"], "succeeded")
        self.assertEqual(items[calendar.id]["imported_count"], 1)
        self.assertFalse(items[calendar.id]["needs_attention"])
        self.assertEqual(items[health.id]["attention_reason"], "paused")
        self.assertTrue(items[health.id]["needs_attention"])

    def test_sync_summary_marks_failed_latest_run_as_attention(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )
        failed_run = DataSourceSyncRun(
            user_id=self.user.id,
            data_source_connection_id=connection.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
            status="failed",
            trigger="worker",
            retryable=True,
            error_message="provider timeout",
            finished_at=connection.updated_at,
        )
        self.db.add(failed_run)
        self.db.commit()

        summary = data_source_service.sync_summary(self.db, user_id=self.user.id)
        item = summary["items"][0]

        self.assertEqual(summary["connected_count"], 1)
        self.assertEqual(summary["attention_count"], 1)
        self.assertIsNotNone(summary["latest_failure_at"])
        self.assertTrue(item["needs_attention"])
        self.assertEqual(item["attention_reason"], "latest_sync_failed")
        self.assertTrue(item["retryable"])
        self.assertEqual(item["latest_run_error_message"], "provider timeout")

    def test_update_and_disconnect_connection(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )

        updated = data_source_service.update_connection(
            self.db,
            connection_id=connection.id,
            user_id=self.user.id,
            updates={"status": DataSourceStatus.PAUSED, "sync_enabled": False},
        )
        self.assertEqual(updated.status, DataSourceStatus.PAUSED)
        self.assertFalse(updated.sync_enabled)

        disconnected = data_source_service.disconnect_source(
            self.db,
            connection_id=connection.id,
            user_id=self.user.id,
        )
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(disconnected.status, DataSourceStatus.DISCONNECTED)
        self.assertFalse(disconnected.sync_enabled)
        self.assertIsNotNone(disconnected.revoked_at)
        self.assertIn("DATA_SOURCE_UPDATED", {event.event_type for event in events})
        self.assertIn("DATA_SOURCE_DISCONNECTED", {event.event_type for event in events})

    def test_rejects_unsupported_provider(self):
        with self.assertRaises(ValidationDomainError):
            data_source_service.connect_source(
                self.db,
                user_id=self.user.id,
                source_type=DataSourceType.EMAIL,
                provider="google_calendar",
            )

    def test_user_isolation_for_connection_mutation(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.EMAIL,
            provider="gmail",
        )

        with self.assertRaises(NotFoundError):
            data_source_service.disconnect_source(
                self.db,
                connection_id=connection.id,
                user_id=self.other_user.id,
            )


if __name__ == "__main__":
    unittest.main()
