import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class ReportAndMeAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.other_user = create_user(self.db, name="Bob")
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}
        self.report_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_generate_and_get_daily_report(self):
        task_response = self.client.post("/api/v1/tasks", json={"title": "API report task"}, headers=self.headers)
        self.assertEqual(task_response.status_code, 201)
        today_response = self.client.get(f"/api/v1/today?plan_date={self.report_date}", headers=self.headers)
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        complete_response = self.client.patch(
            f"/api/v1/today/items/{item_id}",
            json={"status": "completed"},
            headers=self.headers,
        )
        self.assertEqual(complete_response.status_code, 200)

        generate_response = self.client.post(
            f"/api/v1/reports/daily/generate?report_date={self.report_date}",
            headers=self.headers,
        )
        query_get_response = self.client.get(
            f"/api/v1/reports/daily?report_date={self.report_date}",
            headers=self.headers,
        )
        get_response = self.client.get(f"/api/v1/reports/daily/{self.report_date}", headers=self.headers)

        self.assertEqual(generate_response.status_code, 200)
        self.assertEqual(query_get_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(generate_response.json()["id"], query_get_response.json()["id"])
        self.assertEqual(generate_response.json()["id"], get_response.json()["id"])
        self.assertEqual(generate_response.json()["completed_task_count"], 1)
        self.assertEqual(generate_response.json()["completion_rate"], 1.0)
        self.assertTrue(generate_response.json()["ai_suggestions"])

    def test_me_overview_uses_current_user_only(self):
        self.client.post("/api/v1/tasks", json={"title": "Private overview task"}, headers=self.headers)
        self.client.get(f"/api/v1/today?plan_date={self.report_date}", headers=self.headers)
        self.client.post("/api/v1/tasks", json={"title": "Other user task"}, headers=self.other_headers)

        response = self.client.get(f"/api/v1/me/overview?today={self.report_date}", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["profile"]["user_id"], str(self.user.id))
        self.assertEqual(body["tasks"]["active_task_count"], 1)
        self.assertEqual(body["reports"]["daily_report_available"], False)

    def test_report_user_isolation(self):
        self.client.post("/api/v1/tasks", json={"title": "Only Alice task"}, headers=self.headers)
        self.client.get(f"/api/v1/today?plan_date={self.report_date}", headers=self.headers)

        response = self.client.post(
            f"/api/v1/reports/daily/generate?report_date={self.report_date}",
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], str(self.other_user.id))
        self.assertEqual(response.json()["completed_task_count"], 0)


if __name__ == "__main__":
    unittest.main()
