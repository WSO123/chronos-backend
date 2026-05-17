import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class InsightAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.other_user = create_user(self.db, name="Bob")
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}
        self.anchor_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_insight_detail_uses_current_user_only(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={
                "title": "Insight API goal",
                "deadline": self.anchor_date.isoformat(),
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(goal_response.status_code, 201)
        high_task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "Insight API high task",
                "goal_id": goal_response.json()["id"],
                "deadline": self.anchor_date.isoformat(),
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(high_task_response.status_code, 201)
        overdue_task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "Insight API overdue task",
                "goal_id": goal_response.json()["id"],
                "deadline": (self.anchor_date - timedelta(days=2)).isoformat(),
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(overdue_task_response.status_code, 201)
        other_goal_response = self.client.post(
            "/api/v1/goals",
            json={
                "title": "Other insight goal",
                "deadline": self.anchor_date.isoformat(),
                "value_level": "high",
            },
            headers=self.other_headers,
        )
        self.assertEqual(other_goal_response.status_code, 201)
        other_task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "Other overdue insight task",
                "goal_id": other_goal_response.json()["id"],
                "deadline": (self.anchor_date - timedelta(days=3)).isoformat(),
                "value_level": "high",
            },
            headers=self.other_headers,
        )
        self.assertEqual(other_task_response.status_code, 201)
        today_response = self.client.get(
            f"/api/v1/today?plan_date={self.anchor_date.isoformat()}",
            headers=self.headers,
        )
        high_item = self._item_for_task(today_response.json(), high_task_response.json()["id"])
        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={
                "task_id": high_task_response.json()["id"],
                "daily_plan_item_id": high_item["daily_plan_item_id"],
            },
            headers=self.headers,
        )
        complete_response = self.client.post(
            f"/api/v1/focus-sessions/{start_response.json()['id']}/complete",
            json={"actual_duration_min": 25},
            headers=self.headers,
        )
        self.assertEqual(complete_response.status_code, 200)

        response = self.client.get(
            f"/api/v1/insights/detail?anchor_date={self.anchor_date.isoformat()}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["anchor_date"], self.anchor_date.isoformat())
        self.assertEqual(body["overview"]["high_value_completed_task_count"], 1)
        self.assertEqual(body["overview"]["total_focus_minutes"], 25)
        self.assertEqual(body["overview"]["overdue_task_count"], 1)
        self.assertEqual(body["overview"]["at_risk_goal_count"], 1)
        self.assertTrue(body["behavior_patterns"])
        self.assertTrue(body["recommendations"])
        self.assertEqual(body["source"]["generated_by"], "insight-agent-v1")
        self.assertEqual(body["source"]["ai_job_status"], "succeeded")
        self.assertEqual(body["source"]["prompt_version"], "p2-insight-detail-agent-v1")

    def _item_for_task(self, today: dict, task_id: str) -> dict:
        for section_items in today["sections"].values():
            for item in section_items:
                if item["task_id"] == task_id:
                    return item
        raise AssertionError(f"Task {task_id} not found in Today items")


if __name__ == "__main__":
    unittest.main()
