import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class TaskGoalAPITests(unittest.TestCase):
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

    def test_goal_and_task_happy_path(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Launch MVP", "value_level": "high"},
            headers=self.headers,
        )
        self.assertEqual(goal_response.status_code, 201)
        goal_id = goal_response.json()["id"]

        task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "Implement Task API",
                "goal_id": goal_id,
                "priority": 2,
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)
        task_body = task_response.json()
        self.assertEqual(task_body["title"], "Implement Task API")
        self.assertEqual(task_body["goal_id"], goal_id)
        task_id = task_body["id"]

        step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Write schemas"},
            headers=self.headers,
        )
        self.assertEqual(step_response.status_code, 201)
        step_id = step_response.json()["id"]

        complete_step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps/{step_id}/complete",
            headers=self.headers,
        )
        self.assertEqual(complete_step_response.status_code, 200)
        self.assertTrue(complete_step_response.json()["is_completed"])

        complete_task_response = self.client.post(
            f"/api/v1/tasks/{task_id}/complete",
            headers=self.headers,
        )
        self.assertEqual(complete_task_response.status_code, 200)
        self.assertEqual(complete_task_response.json()["status"], "completed")

        events_response = self.client.get(f"/api/v1/tasks/{task_id}/events", headers=self.headers)
        self.assertEqual(events_response.status_code, 200)
        event_types = {event["event_type"] for event in events_response.json()}
        self.assertIn("TASK_CREATED", event_types)
        self.assertIn("TASK_STEP_COMPLETED", event_types)
        self.assertIn("TASK_COMPLETED", event_types)

    def test_get_task_returns_task_detail_execution_context(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Detail Goal", "value_level": "high"},
            headers=self.headers,
        )
        goal_id = goal_response.json()["id"]
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Open Task Detail", "goal_id": goal_id, "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Check context"},
            headers=self.headers,
        )
        today_response = self.client.get("/api/v1/today", headers=self.headers)
        self.assertEqual(today_response.status_code, 200)

        detail_response = self.client.get(f"/api/v1/tasks/{task_id}", headers=self.headers)

        self.assertEqual(detail_response.status_code, 200)
        body = detail_response.json()
        self.assertEqual(body["title"], "Open Task Detail")
        self.assertEqual(body["goal"]["title"], "Detail Goal")
        self.assertEqual(body["ai_info"]["execution_suggestion"], "Continue with: Check context")
        self.assertIsNotNone(body["today_context"])
        self.assertTrue(body["actions"]["can_start_focus"])
        self.assertFalse(body["focus_state"]["is_currently_focusing_this_task"])

    def test_user_id_isolation(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Private task"},
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)
        task_id = task_response.json()["id"]

        forbidden_response = self.client.get(f"/api/v1/tasks/{task_id}", headers=self.other_headers)

        self.assertEqual(forbidden_response.status_code, 404)
        self.assertEqual(forbidden_response.json()["error"]["code"], "NOT_FOUND")

    def test_task_source_cannot_be_spoofed_by_client(self):
        response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Pretend AI made this", "source": "ai"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")

    def test_invalid_state_returns_error_payload(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Complete then postpone"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        response = self.client.post(f"/api/v1/tasks/{task_id}/postpone", headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")

    def test_repeated_complete_returns_invalid_state(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Complete once"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        response = self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")

    def test_completed_task_cannot_create_or_complete_steps(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Lock steps after complete"},
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Existing step"},
            headers=self.headers,
        )
        step_id = step_response.json()["id"]
        self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=self.headers)

        create_step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps",
            json={"title": "Too late"},
            headers=self.headers,
        )
        complete_step_response = self.client.post(
            f"/api/v1/tasks/{task_id}/steps/{step_id}/complete",
            headers=self.headers,
        )

        self.assertEqual(create_step_response.status_code, 400)
        self.assertEqual(create_step_response.json()["error"]["code"], "INVALID_STATE")
        self.assertEqual(complete_step_response.status_code, 400)
        self.assertEqual(complete_step_response.json()["error"]["code"], "INVALID_STATE")

    def test_goal_list_supports_pagination(self):
        for title in ("Goal A", "Goal B", "Goal C"):
            response = self.client.post("/api/v1/goals", json={"title": title}, headers=self.headers)
            self.assertEqual(response.status_code, 201)

        response = self.client.get("/api/v1/goals?limit=1&offset=1", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_missing_user_id_returns_error_payload(self):
        response = self.client.get("/api/v1/goals")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "MISSING_USER_ID")

    def test_request_validation_returns_error_payload(self):
        response = self.client.post("/api/v1/tasks", json={}, headers=self.headers)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
