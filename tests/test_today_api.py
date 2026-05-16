import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class TodayAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.other_user = create_user(self.db, name="Bob")
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_get_today_lazy_creates_plan(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Do the important thing", "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)

        response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-05-16")
        self.assertEqual(body["plan_version"], 1)
        self.assertEqual(body["sections"]["pinned_tasks"][0]["title"], "Do the important thing")
        self.assertEqual(body["insights_preview"]["source"], "rule-today-insights-v1")
        self.assertEqual(body["insights_preview"]["remaining_time_suggestion"]["key"], "remaining_time")
        self.assertEqual(body["quick_actions"]["can_replan"], True)

    def test_get_strategy_detail_uses_current_user_only(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Private strategy task", "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        other_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Other strategy task", "priority": 1, "value_level": "high"},
            headers=self.other_headers,
        )
        self.assertEqual(task_response.status_code, 201)
        self.assertEqual(other_task_response.status_code, 201)

        response = self.client.get("/api/v1/today/strategy?plan_date=2026-05-16", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-05-16")
        self.assertEqual(body["plan_version"], 1)
        self.assertEqual(body["factors"]["task_count"], 1)
        self.assertEqual(body["task_rationales"][0]["title"], "Private strategy task")
        self.assertNotIn("Other strategy task", {item["title"] for item in body["task_rationales"]})
        self.assertTrue(body["explanation"])
        self.assertEqual(body["source"]["model_name"], "rule-planner")

    def test_replan_and_complete_today_item(self):
        self.client.post("/api/v1/tasks", json={"title": "First task"}, headers=self.headers)
        today_response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        plan_id = today_response.json()["daily_plan_id"]
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        replan_response = self.client.post(
            "/api/v1/today/replan?plan_date=2026-05-16",
            json={"reason": "Check ordering"},
            headers=self.headers,
        )
        updated_item_id = replan_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        complete_response = self.client.patch(
            f"/api/v1/today/items/{updated_item_id}",
            json={"status": "completed"},
            headers=self.headers,
        )
        refreshed_today = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        old_item_response = self.client.patch(
            f"/api/v1/today/items/{item_id}",
            json={"status": "completed"},
            headers=self.headers,
        )

        self.assertEqual(replan_response.status_code, 200)
        self.assertEqual(replan_response.json()["daily_plan_id"], plan_id)
        self.assertEqual(replan_response.json()["plan_version"], 2)
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["item_status"], "completed")
        self.assertEqual(refreshed_today.json()["progress"]["completion_rate"], 1.0)
        self.assertEqual(old_item_response.status_code, 404)

    def test_user_id_isolation_for_today_item(self):
        self.client.post("/api/v1/tasks", json={"title": "Private today task"}, headers=self.headers)
        today_response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        response = self.client.patch(
            f"/api/v1/today/items/{item_id}",
            json={"status": "completed"},
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
