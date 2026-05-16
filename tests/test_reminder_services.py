import unittest
from datetime import UTC, datetime, timedelta

from app.models.reminder import Reminder
from app.services.errors import NotFoundError, ValidationDomainError
from app.services.reminder_service import reminder_service
from app.services.task_service import task_service
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


if __name__ == "__main__":
    unittest.main()
