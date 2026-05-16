import unittest
from datetime import date

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class EnergyAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.other_user = create_user(self.db)
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}
        self.metric_date = date(2026, 5, 17)

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_upsert_metric_and_get_dashboard(self):
        upsert_response = self.client.put(
            "/api/v1/energy/daily-metrics",
            json={
                "metric_date": self.metric_date.isoformat(),
                "sleep_minutes": 320,
                "sleep_quality_score": 55,
                "stress_score": 80,
                "source": "manual",
            },
            headers=self.headers,
        )
        dashboard_response = self.client.get(
            f"/api/v1/energy/dashboard?end_date={self.metric_date.isoformat()}&days=2",
            headers=self.headers,
        )

        self.assertEqual(upsert_response.status_code, 200)
        upsert_body = upsert_response.json()
        self.assertEqual(upsert_body["metric_date"], self.metric_date.isoformat())
        self.assertEqual(upsert_body["energy_level"], "low")
        self.assertIsNotNone(upsert_body["energy_score"])
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard = dashboard_response.json()
        self.assertEqual(dashboard["start_date"], "2026-05-16")
        self.assertEqual(dashboard["end_date"], self.metric_date.isoformat())
        self.assertEqual(dashboard["summary"]["energy_level"], "low")
        self.assertEqual(dashboard["task_match"]["recommended_mode"], "light")
        self.assertEqual(dashboard["suggestions"][0]["key"], "short_sleep")

    def test_dashboard_is_user_isolated(self):
        self.client.put(
            "/api/v1/energy/daily-metrics",
            json={"metric_date": self.metric_date.isoformat(), "energy_score": 88},
            headers=self.headers,
        )

        response = self.client.get(
            f"/api/v1/energy/dashboard?end_date={self.metric_date.isoformat()}&days=1",
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["energy_level"], "unknown")
        self.assertFalse(body["trends"][0]["has_data"])

    def test_upsert_rejects_empty_metric(self):
        response = self.client.put(
            "/api/v1/energy/daily-metrics",
            json={"metric_date": self.metric_date.isoformat()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
