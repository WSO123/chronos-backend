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
        self.assertEqual(create_response.json()["seen_at"], None)
        self.assertEqual(create_response.json()["channel"], "in_app")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["scheduled_count"], 1)
        self.assertEqual(list_response.json()["overdue_count"], 0)
        self.assertEqual(len(list_response.json()["reminders"]), 1)
        self.assertEqual(dismiss_response.status_code, 200)
        self.assertEqual(dismiss_response.json()["status"], "dismissed")

    def test_list_reminders_filters_type_due_and_unseen(self):
        now = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        due_execution = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Due API execution",
                "scheduled_for": (now - timedelta(minutes=1)).isoformat(),
                "reminder_type": "execution",
            },
            headers=self.headers,
        ).json()
        seen_deadline = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Seen API deadline",
                "scheduled_for": (now - timedelta(minutes=2)).isoformat(),
                "reminder_type": "deadline",
            },
            headers=self.headers,
        ).json()
        self.client.post(f"/api/v1/reminders/{seen_deadline['id']}/seen", headers=self.headers)
        self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Future API execution",
                "scheduled_for": (now + timedelta(hours=1)).isoformat(),
                "reminder_type": "execution",
            },
            headers=self.headers,
        )

        response = self.client.get(
            "/api/v1/reminders",
            params={
                "reminder_type": "execution",
                "due_only": True,
                "unseen_only": True,
                "now": now.isoformat(),
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([reminder["id"] for reminder in body["reminders"]], [due_execution["id"]])
        self.assertEqual(body["scheduled_count"], 3)
        self.assertEqual(body["overdue_count"], 2)

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

    def test_mark_reminder_seen(self):
        create_response = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Seen API reminder",
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            headers=self.headers,
        )

        seen_response = self.client.post(
            f"/api/v1/reminders/{create_response.json()['id']}/seen",
            headers=self.headers,
        )
        other_seen_response = self.client.post(
            f"/api/v1/reminders/{create_response.json()['id']}/seen",
            headers=self.other_headers,
        )

        self.assertEqual(seen_response.status_code, 200)
        self.assertEqual(seen_response.json()["status"], "scheduled")
        self.assertIsNotNone(seen_response.json()["seen_at"])
        self.assertEqual(other_seen_response.status_code, 404)

    def test_mark_reminders_seen_batch(self):
        first = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Batch seen API 1",
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            headers=self.headers,
        ).json()
        second = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Batch seen API 2",
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            },
            headers=self.headers,
        ).json()
        self.client.post(f"/api/v1/reminders/{second['id']}/seen", headers=self.headers)

        response = self.client.post(
            "/api/v1/reminders/seen",
            json={"reminder_ids": [first["id"], second["id"], first["id"]]},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["updated_count"], 1)
        self.assertEqual(body["already_seen_count"], 1)
        self.assertEqual(len(body["reminders"]), 2)
        self.assertTrue(all(reminder["seen_at"] for reminder in body["reminders"]))

    def test_snooze_reminder(self):
        now = datetime.now(UTC)
        create_response = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Snooze API reminder",
                "scheduled_for": (now - timedelta(minutes=1)).isoformat(),
            },
            headers=self.headers,
        )

        response = self.client.post(
            f"/api/v1/reminders/{create_response.json()['id']}/snooze",
            json={"minutes": 30},
            headers=self.headers,
        )
        other_response = self.client.post(
            f"/api/v1/reminders/{create_response.json()['id']}/snooze",
            json={"minutes": 30},
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "scheduled")
        self.assertIsNotNone(body["seen_at"])
        self.assertEqual(body["reminder_metadata"]["snoozed_count"], 1)
        self.assertEqual(body["reminder_metadata"]["last_snooze_minutes"], 30)
        self.assertEqual(other_response.status_code, 404)

    def test_summary_returns_lightweight_header_counts(self):
        now = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        due_response = self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Due execution",
                "scheduled_for": (now - timedelta(minutes=1)).isoformat(),
                "reminder_type": "execution",
            },
            headers=self.headers,
        )
        self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Future deadline",
                "scheduled_for": (now + timedelta(hours=1)).isoformat(),
                "reminder_type": "deadline",
            },
            headers=self.headers,
        )
        self.client.post(
            "/api/v1/reminders",
            json={
                "title": "Other due",
                "scheduled_for": (now - timedelta(minutes=1)).isoformat(),
            },
            headers=self.other_headers,
        )

        response = self.client.get(
            "/api/v1/reminders/summary",
            params={"now": now.isoformat()},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["pending_count"], 2)
        self.assertEqual(body["unseen_count"], 2)
        self.assertEqual(body["due_count"], 1)
        self.assertEqual(body["execution_count"], 1)
        self.assertEqual(body["deadline_count"], 1)
        self.assertEqual(body["next_reminder"]["id"], due_response.json()["id"])

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
