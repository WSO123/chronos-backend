import unittest
from datetime import datetime, timedelta
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

    def test_weekly_report_returns_trends_and_lagging_tasks(self):
        report_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        week_start = report_date - timedelta(days=report_date.weekday())
        goal_response = self.client.post(
            "/api/v1/goals",
            json={
                "title": "API weekly goal",
                "deadline": report_date.isoformat(),
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(goal_response.status_code, 201)
        goal_id = goal_response.json()["id"]
        high_task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "API high-value weekly task",
                "goal_id": goal_id,
                "value_level": "high",
                "deadline": report_date.isoformat(),
            },
            headers=self.headers,
        )
        lagging_task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "API overdue weekly task",
                "goal_id": goal_id,
                "value_level": "high",
                "deadline": (report_date - timedelta(days=2)).isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(high_task_response.status_code, 201)
        self.assertEqual(lagging_task_response.status_code, 201)
        other_goal_response = self.client.post(
            "/api/v1/goals",
            json={
                "title": "Other weekly goal",
                "deadline": report_date.isoformat(),
                "value_level": "high",
            },
            headers=self.other_headers,
        )
        self.assertEqual(other_goal_response.status_code, 201)
        other_task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "Other overdue weekly task",
                "goal_id": other_goal_response.json()["id"],
                "value_level": "high",
                "deadline": (report_date - timedelta(days=3)).isoformat(),
            },
            headers=self.other_headers,
        )
        self.assertEqual(other_task_response.status_code, 201)
        high_task_id = high_task_response.json()["id"]
        lagging_task_id = lagging_task_response.json()["id"]
        today_response = self.client.get(f"/api/v1/today?plan_date={report_date.isoformat()}", headers=self.headers)
        high_item = self._item_for_task(today_response.json(), high_task_id)
        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={
                "task_id": high_task_id,
                "daily_plan_item_id": high_item["daily_plan_item_id"],
            },
            headers=self.headers,
        )
        self.assertEqual(start_response.status_code, 201)
        complete_response = self.client.post(
            f"/api/v1/focus-sessions/{start_response.json()['id']}/complete",
            json={"actual_duration_min": 25},
            headers=self.headers,
        )
        self.assertEqual(complete_response.status_code, 200)

        response = self.client.get(
            f"/api/v1/reports/weekly?week_start={week_start.isoformat()}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["week_start"], week_start.isoformat())
        self.assertEqual(body["summary"]["total_completed_task_count"], 1)
        self.assertEqual(body["summary"]["high_value_completed_task_count"], 1)
        self.assertEqual(body["summary"]["total_focus_minutes"], 25)
        self.assertEqual(body["summary"]["active_goal_count"], 1)
        self.assertEqual(body["summary"]["overdue_task_count"], 1)
        self.assertEqual(body["focus"]["best_focus_date"], report_date.isoformat())
        self.assertEqual(body["lagging_tasks"][0]["id"], lagging_task_id)
        self.assertTrue(body["ai_suggestions"])

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

    def _item_for_task(self, today: dict, task_id: str) -> dict:
        for section_items in today["sections"].values():
            for item in section_items:
                if item["task_id"] == task_id:
                    return item
        raise AssertionError(f"Task {task_id} not found in Today items")


if __name__ == "__main__":
    unittest.main()
