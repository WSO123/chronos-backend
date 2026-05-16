import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class ReminderAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.other_user = create_user(self.db)
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_create_list_and_dismiss_reminder(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "API reminder task"},
            headers=self.headers,
        )
        scheduled_for = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        create_response = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Start gently",
                "message": "Begin the next task",
                "task_id": task_response.json()["id"],
                "scheduled_for": scheduled_for,
                "reminder_type": "execution",
            },
            headers=self.headers,
        )
        list_response = self.client.get("/api/v1/reminders", headers=self.headers)
        dismiss_response = self.client.post(
            f"/api/v1/reminders/{create_response.json()['id']}/dismiss",
            headers=self.headers,
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["status"], "scheduled")
        self.assertEqual(create_response.json()["channel"], "in_app")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["scheduled_count"], 1)
        self.assertEqual(list_response.json()["overdue_count"], 0)
        self.assertEqual(len(list_response.json()["reminders"]), 1)
        self.assertEqual(dismiss_response.status_code, 200)
        self.assertEqual(dismiss_response.json()["status"], "dismissed")

    def test_reminder_user_isolation(self):
        create_response = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Private reminder",
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            headers=self.headers,
        )

        other_list_response = self.client.get("/api/v1/reminders", headers=self.other_headers)
        other_dismiss_response = self.client.post(
            f"/api/v1/reminders/{create_response.json()['id']}/dismiss",
            headers=self.other_headers,
        )

        self.assertEqual(other_list_response.status_code, 200)
        self.assertEqual(other_list_response.json()["reminders"], [])
        self.assertEqual(other_dismiss_response.status_code, 404)
        self.assertEqual(other_dismiss_response.json()["error"]["code"], "NOT_FOUND")

    def test_create_reminder_rejects_cross_user_task(self):
        other_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Other task"},
            headers=self.other_headers,
        )

        response = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Bad reminder",
                "task_id": other_task_response.json()["id"],
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_list_reminders_rejects_unknown_status(self):
        response = self.client.get("/api/v1/reminders?status=unknown", headers=self.headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
