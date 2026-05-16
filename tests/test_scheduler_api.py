import unittest

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class SchedulerAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.headers = {"X-User-Id": str(self.user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_get_reminder_scheduler_plan(self):
        response = self.client.get("/api/v1/scheduler/reminders", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        task_names = {entry["task_name"] for entry in body["entries"]}
        self.assertEqual(body["timezone"], "UTC")
        self.assertIn("reminder.generate_deadline", task_names)
        self.assertIn("reminder.generate_execution_for_active_users", task_names)
        self.assertIn("reminder.dispatch_due", task_names)
        self.assertIn("reminder.cleanup_delivery_attempts", task_names)
        self.assertTrue(body["notes"])

    def test_get_reminder_celery_beat_schedule(self):
        response = self.client.get("/api/v1/scheduler/reminders/celery-beat", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        tasks = {entry["task"] for entry in body["entries"]}
        excluded = {entry["task_name"] for entry in body["excluded_entries"]}
        self.assertEqual(body["timezone"], "UTC")
        self.assertIn("reminder.generate_deadline", tasks)
        self.assertIn("reminder.generate_execution_for_active_users", tasks)
        self.assertIn("reminder.dispatch_due", tasks)
        self.assertIn("reminder.cleanup_delivery_attempts", tasks)
        self.assertIn("reminder.generate_execution", excluded)
        self.assertTrue(body["notes"])


if __name__ == "__main__":
    unittest.main()
