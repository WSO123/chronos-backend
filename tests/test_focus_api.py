import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class FocusAPITests(unittest.TestCase):
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

    def test_focus_from_today_item_complete_happy_path(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Focus API task"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        today_response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={"task_id": task_id, "daily_plan_item_id": item_id, "planned_duration_min": 25},
            headers=self.headers,
        )
        session_id = start_response.json()["id"]
        complete_response = self.client.post(
            f"/api/v1/focus-sessions/{session_id}/complete",
            json={"actual_duration_min": 12},
            headers=self.headers,
        )
        refreshed_today = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)

        self.assertEqual(start_response.status_code, 201)
        self.assertEqual(start_response.json()["status"], "active")
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["status"], "completed")
        self.assertEqual(complete_response.json()["actual_duration_min"], 12)
        self.assertEqual(refreshed_today.json()["progress"]["completed_count"], 1)
        self.assertEqual(refreshed_today.json()["progress"]["focus_minutes"], 12)

    def test_focus_without_item_auto_links_current_today_item(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Auto link Focus API task"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        today_response = self.client.get("/api/v1/today", headers=self.headers)
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={"task_id": task_id, "planned_duration_min": 25},
            headers=self.headers,
        )
        session_id = start_response.json()["id"]
        complete_response = self.client.post(
            f"/api/v1/focus-sessions/{session_id}/complete",
            json={"actual_duration_min": 9},
            headers=self.headers,
        )
        refreshed_today = self.client.get("/api/v1/today", headers=self.headers)

        self.assertEqual(start_response.status_code, 201)
        self.assertEqual(start_response.json()["daily_plan_item_id"], item_id)
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["daily_plan_item_id"], item_id)
        self.assertEqual(refreshed_today.json()["progress"]["completed_count"], 1)
        self.assertEqual(refreshed_today.json()["progress"]["focus_minutes"], 9)

    def test_interrupt_focus_session_then_start_again(self):
        task_response = self.client.post("/api/v1/tasks", json={"title": "Interrupt API task"}, headers=self.headers)
        task_id = task_response.json()["id"]
        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={"task_id": task_id},
            headers=self.headers,
        )
        session_id = start_response.json()["id"]

        interrupt_response = self.client.post(
            f"/api/v1/focus-sessions/{session_id}/interrupt",
            json={"actual_duration_min": 4, "interruption_reason": "Incoming call"},
            headers=self.headers,
        )
        restart_response = self.client.post(
            "/api/v1/focus-sessions",
            json={"task_id": task_id},
            headers=self.headers,
        )

        self.assertEqual(interrupt_response.status_code, 200)
        self.assertEqual(interrupt_response.json()["status"], "interrupted")
        self.assertEqual(restart_response.status_code, 201)

    def test_focus_session_user_id_isolation(self):
        task_response = self.client.post("/api/v1/tasks", json={"title": "Private focus"}, headers=self.headers)
        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={"task_id": task_response.json()["id"]},
            headers=self.headers,
        )
        session_id = start_response.json()["id"]

        response = self.client.get(f"/api/v1/focus-sessions/{session_id}", headers=self.other_headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_completed_focus_session_cannot_be_completed_again(self):
        task_response = self.client.post("/api/v1/tasks", json={"title": "Complete once"}, headers=self.headers)
        start_response = self.client.post(
            "/api/v1/focus-sessions",
            json={"task_id": task_response.json()["id"]},
            headers=self.headers,
        )
        session_id = start_response.json()["id"]
        self.client.post(
            f"/api/v1/focus-sessions/{session_id}/complete",
            json={"actual_duration_min": 1},
            headers=self.headers,
        )

        response = self.client.post(
            f"/api/v1/focus-sessions/{session_id}/complete",
            json={"actual_duration_min": 1},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")


if __name__ == "__main__":
    unittest.main()
