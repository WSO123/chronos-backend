import unittest
from datetime import date, timedelta

from app.models.enums import DataSourceType
from app.services.data_source_service import data_source_service
from app.services.energy_service import energy_service
from app.services.errors import NotFoundError, ValidationDomainError
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class EnergyServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.other_user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_upsert_daily_metric_derives_energy_and_dashboard(self):
        metric_date = date(2026, 5, 17)

        metric = energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={
                "metric_date": metric_date,
                "source": "manual",
                "sleep_minutes": 450,
                "sleep_quality_score": 82,
                "stress_score": 30,
                "metric_metadata": {"entry": "manual_checkin"},
            },
        )
        dashboard = energy_service.get_dashboard(
            self.db,
            user_id=self.user.id,
            end_date=metric_date,
            days=3,
        )

        self.assertEqual(metric.energy_score, 83)
        self.assertEqual(energy_service.energy_level(metric.energy_score), "high")
        self.assertEqual(dashboard["start_date"], metric_date - timedelta(days=2))
        self.assertEqual(dashboard["summary"]["energy_level"], "high")
        self.assertEqual(dashboard["summary"]["sleep_minutes"], 450)
        self.assertEqual(len(dashboard["trends"]), 3)
        self.assertFalse(dashboard["trends"][0]["has_data"])
        self.assertTrue(dashboard["trends"][2]["has_data"])
        self.assertEqual(dashboard["task_match"]["recommended_mode"], "deep_work")
        self.assertEqual(dashboard["suggestions"][0]["key"], "protect_deep_work")

    def test_upsert_daily_metric_updates_same_day(self):
        metric_date = date(2026, 5, 17)

        first = energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={"metric_date": metric_date, "energy_score": 30},
        )
        second = energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={"metric_date": metric_date, "energy_score": 78, "source": "estimated"},
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.energy_score, 78)
        self.assertEqual(second.source, "estimated")

    def test_metric_can_only_link_owned_health_connection(self):
        metric_date = date(2026, 5, 17)
        calendar = data_source_service.connect_source(
            self.db,
            user_id=self.user.id,
            source_type=DataSourceType.CALENDAR,
            provider="google_calendar",
        )
        other_health = data_source_service.connect_source(
            self.db,
            user_id=self.other_user.id,
            source_type=DataSourceType.HEALTH,
            provider="apple_health",
        )

        with self.assertRaises(ValidationDomainError):
            energy_service.upsert_daily_metric(
                self.db,
                user_id=self.user.id,
                payload={
                    "metric_date": metric_date,
                    "data_source_connection_id": calendar.id,
                    "energy_score": 70,
                },
            )
        with self.assertRaises(NotFoundError):
            energy_service.upsert_daily_metric(
                self.db,
                user_id=self.user.id,
                payload={
                    "metric_date": metric_date,
                    "data_source_connection_id": other_health.id,
                    "energy_score": 70,
                },
            )

    def test_dashboard_is_user_isolated(self):
        metric_date = date(2026, 5, 17)
        energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={"metric_date": metric_date, "energy_score": 90},
        )

        dashboard = energy_service.get_dashboard(
            self.db,
            user_id=self.other_user.id,
            end_date=metric_date,
            days=1,
        )

        self.assertEqual(dashboard["summary"]["energy_level"], "unknown")
        self.assertFalse(dashboard["trends"][0]["has_data"])


if __name__ == "__main__":
    unittest.main()
