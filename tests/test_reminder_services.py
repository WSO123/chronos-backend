import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.models.reminder import Reminder
from app.services.errors import NotFoundError, ValidationDomainError
from app.services.reminder_service import reminder_service
from app.services.task_service import task_service
from app.workers.tasks import dispatch_due_reminders
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class ReminderServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.other_user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_create_list_and_dismiss_reminder(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Reminder task")
        scheduled_for = datetime.now(UTC) + timedelta(hours=2)

        reminder = reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={
                "title": "Start task",
                "message": "Begin gently",
                "task_id": task.id,
                "reminder_type": "execution",
                "scheduled_for": scheduled_for,
            },
        )
        listed = reminder_service.list_reminders(self.db, user_id=self.user.id)

        self.assertEqual(reminder.status, "scheduled")
        self.assertEqual(listed["scheduled_count"], 1)
        self.assertEqual(listed["overdue_count"], 0)
        self.assertEqual(listed["reminders"][0].id, reminder.id)
        dismissed = reminder_service.dismiss_reminder(self.db, reminder_id=reminder.id, user_id=self.user.id)
        self.assertEqual(dismissed.status, "dismissed")
        self.assertIsNotNone(dismissed.dismissed_at)

    def test_list_reminders_counts_overdue(self):
        reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={
                "title": "Past reminder",
                "scheduled_for": datetime.now(UTC) - timedelta(minutes=5),
                "reminder_type": "deadline",
            },
        )

        result = reminder_service.list_reminders(self.db, user_id=self.user.id)

        self.assertEqual(result["scheduled_count"], 1)
        self.assertEqual(result["overdue_count"], 1)

    def test_create_reminder_validates_owner_and_single_target(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Owned task")
        other_task = task_service.create_task(self.db, user_id=self.other_user.id, title="Other task")

        with self.assertRaises(ValidationDomainError):
            reminder_service.create_reminder(
                self.db,
                user_id=self.user.id,
                payload={
                    "title": "Bad target",
                    "task_id": task.id,
                    "goal_id": task.goal_id or task.id,
                    "scheduled_for": datetime.now(UTC),
                },
            )
        with self.assertRaises(NotFoundError):
            reminder_service.create_reminder(
                self.db,
                user_id=self.user.id,
                payload={
                    "title": "Other task",
                    "task_id": other_task.id,
                    "scheduled_for": datetime.now(UTC),
                },
            )
        self.assertEqual(self.db.query(Reminder).count(), 0)

    def test_dismiss_reminder_is_user_isolated(self):
        reminder = reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={"title": "Private reminder", "scheduled_for": datetime.now(UTC)},
        )

        with self.assertRaises(NotFoundError):
            reminder_service.dismiss_reminder(self.db, reminder_id=reminder.id, user_id=self.other_user.id)

    def test_dispatch_due_reminders_marks_due_as_sent(self):
        now = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        due = reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={"title": "Due reminder", "scheduled_for": now - timedelta(minutes=1)},
        )
        reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={"title": "Future reminder", "scheduled_for": now + timedelta(minutes=5)},
        )
        reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={
                "title": "Email reminder",
                "scheduled_for": now - timedelta(minutes=2),
                "channel": "email",
            },
        )

        result = reminder_service.dispatch_due_reminders(self.db, now=now, channel="in_app")
        self.db.refresh(due)

        self.assertEqual(result["status"], "dispatched")
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["reminders"][0].id, due.id)
        self.assertEqual(due.status, "sent")
        self.assertEqual(due.sent_at.replace(tzinfo=UTC), now)
        self.assertEqual(
            self.db.query(Reminder).filter(Reminder.status == "scheduled").count(),
            2,
        )

    def test_dispatch_due_reminders_worker_returns_json_ready_payload(self):
        now = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        reminder = reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={"title": "Worker due reminder", "scheduled_for": now - timedelta(minutes=1)},
        )

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = dispatch_due_reminders.run(limit=10, now=now.isoformat())

        self.assertEqual(result["status"], "dispatched")
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["reminders"][0]["id"], str(reminder.id))
        self.assertEqual(result["reminders"][0]["status"], "sent")


if __name__ == "__main__":
    unittest.main()
