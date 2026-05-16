import unittest
from datetime import date
from unittest.mock import patch

from app.models.activity_event import ActivityEvent
from app.models.data_source_sync_run import DataSourceSyncRun
from app.models.energy import EnergyDailyMetric
from app.models.enums import DataSourceStatus, DataSourceType, EventSource
from app.models.external_import import ExternalCaptureImport
from app.services.data_source_service import data_source_service
from app.services.health_sync_service import health_sync_service
from app.workers.tasks import sync_health_energy_connection, sync_ready_health_energy_connections
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class HealthSyncServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_sync_energy_metrics_imports_explicit_metrics(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )

        result = health_sync_service.sync_energy_metrics(
            self.db,
            connection_id=connection.id,
            metrics=[
                {
                    "metric_date": date(2026, 5, 17),
                    "sleep_minutes": 450,
                    "sleep_quality_score": 80,
                    "stress_score": 35,
                    "metric_metadata": {"sample": "explicit"},
                }
            ],
        )
        self.db.refresh(connection)
        metric = self.db.query(EnergyDailyMetric).one()
        sync_run = self.db.get(DataSourceSyncRun, result["sync_run_id"])
        sync_event = (
            self.db.query(ActivityEvent)
            .filter(ActivityEvent.event_type == "DATA_SOURCE_SYNCED")
            .one()
        )

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["energy_metric_ids"], [str(metric.id)])
        self.assertFalse(result["fetched_from_provider"])
        self.assertEqual(metric.source, "health_import")
        self.assertEqual(metric.data_source_connection_id, connection.id)
        self.assertEqual(metric.metric_metadata["provider"], "apple_health")
        self.assertEqual(self.db.query(ExternalCaptureImport).count(), 0)
        self.assertIsNotNone(connection.last_sync_at)
        self.assertEqual(sync_run.status, "succeeded")
        self.assertEqual(sync_event.source, EventSource.WORKER)
        self.assertEqual(sync_event.payload["sync_run_id"], str(sync_run.id))

    def test_sync_energy_metrics_fetches_fake_provider_metadata(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
            connection_metadata={
                "fake_energy_metrics": [
                    {
                        "external_metric_id": "health-2026-05-16",
                        "metric_date": "2026-05-16",
                        "energy_score": 62,
                    },
                    {
                        "external_metric_id": "health-2026-05-17",
                        "metric_date": "2026-05-17",
                        "energy_score": 82,
                    },
                ],
                "fake_next_cursor": "health-cursor-2",
            },
        )

        result = health_sync_service.sync_energy_metrics(
            self.db,
            connection_id=connection.id,
            end_date=date(2026, 5, 17),
            days=1,
        )
        self.db.refresh(connection)
        metric = self.db.query(EnergyDailyMetric).one()

        self.assertEqual(result["status"], "synced")
        self.assertTrue(result["fetched_from_provider"])
        self.assertEqual(result["provider_mode"], "fake")
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(connection.sync_cursor, "health-cursor-2")
        self.assertEqual(metric.metric_date, date(2026, 5, 17))
        self.assertEqual(metric.energy_score, 82)
        self.assertEqual(metric.metric_metadata["external_metric_id"], "health-2026-05-17")

    def test_sync_energy_metrics_skips_non_ready_connections(self):
        paused = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )
        data_source_service.update_connection(
            self.db,
            connection_id=paused.id,
            user_id=self.user.id,
            updates={"status": DataSourceStatus.PAUSED},
        )
        calendar = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )

        paused_result = health_sync_service.sync_energy_metrics(self.db, connection_id=paused.id)
        calendar_result = health_sync_service.sync_energy_metrics(self.db, connection_id=calendar.id)

        self.assertEqual(paused_result["status"], "skipped")
        self.assertEqual(paused_result["skip_reason"], "status_not_connected")
        self.assertEqual(calendar_result["status"], "skipped")
        self.assertEqual(calendar_result["skip_reason"], "unsupported_source")
        self.assertEqual(self.db.query(EnergyDailyMetric).count(), 0)

    def test_worker_sync_health_energy_connection_returns_json_ready_result(self):
        connection = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="google_fit",
        )

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = sync_health_energy_connection.run(
                str(connection.id),
                metrics=[{"metric_date": "2026-05-17", "energy_score": 72}],
            )

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["connection_id"], str(connection.id))
        self.assertEqual(result["source_type"], "health")
        self.assertEqual(result["imported_count"], 1)
        self.assertTrue(result["energy_metric_ids"])

    def test_worker_sync_ready_health_energy_connections_filters_health_only(self):
        health = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
            connection_metadata={
                "fake_energy_metrics": [
                    {"metric_date": "2026-05-17", "energy_score": 88}
                ]
            },
        )
        data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = sync_ready_health_energy_connections.run(limit=10)
        self.db.refresh(health)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["processed_connection_count"], 1)
        self.assertEqual(result["failed_connection_count"], 0)
        self.assertIsNotNone(health.last_sync_at)
        self.assertEqual(self.db.query(EnergyDailyMetric).count(), 1)


if __name__ == "__main__":
    unittest.main()
