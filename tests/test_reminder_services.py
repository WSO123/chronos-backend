import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.models.daily_plan import DailyPlan
from app.models.reminder import Reminder
from app.models.enums import TaskStatus
from app.models.user import UserSettings
from app.services.errors import NotFoundError, ValidationDomainError
from app.services.goal_service import goal_service
from app.services.planning_service import planning_service
from app.services.reminder_service import reminder_service
from app.services.task_service import task_service
from app.workers.tasks import dispatch_due_reminders, generate_deadline_reminders, generate_execution_reminders
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
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["reminders"][0].id, due.id)
        self.assertEqual(result["delivery_results"][0]["provider"], "reminder_center")
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
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["reminders"][0]["id"], str(reminder.id))
        self.assertEqual(result["reminders"][0]["status"], "sent")
        self.assertEqual(result["delivery_results"][0]["provider"], "reminder_center")

    def test_dispatch_due_reminders_skips_unconfigured_external_channel(self):
        now = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        email_reminder = reminder_service.create_reminder(
            self.db,
            user_id=self.user.id,
            payload={
                "title": "Email due reminder",
                "scheduled_for": now - timedelta(minutes=1),
                "channel": "email",
            },
        )

        result = reminder_service.dispatch_due_reminders(self.db, now=now)
        self.db.refresh(email_reminder)

        self.assertEqual(result["sent_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["delivery_results"][0]["status"], "skipped")
        self.assertEqual(result["delivery_results"][0]["reason"], "provider_not_configured")
        self.assertEqual(email_reminder.status, "scheduled")
        self.assertEqual(email_reminder.sent_at, None)

    def test_generate_deadline_reminders_creates_task_and_goal_reminders_once(self):
        target_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Due task",
            deadline=target_date,
        )
        completed_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Completed due task",
            deadline=target_date,
        )
        completed_task.status = TaskStatus.COMPLETED
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Due goal",
            deadline=target_date,
        )
        self.db.commit()

        first = reminder_service.generate_deadline_reminders(
            self.db,
            user_id=self.user.id,
            target_date=target_date,
            window_days=1,
        )
        second = reminder_service.generate_deadline_reminders(
            self.db,
            user_id=self.user.id,
            target_date=target_date,
            window_days=1,
        )

        reminders = self.db.query(Reminder).order_by(Reminder.title).all()
        self.assertEqual(first["created_count"], 2)
        self.assertEqual(first["skipped_existing_count"], 0)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["skipped_existing_count"], 2)
        self.assertEqual(len(reminders), 2)
        self.assertEqual({reminder.task_id for reminder in reminders}, {task.id, None})
        self.assertEqual({reminder.goal_id for reminder in reminders}, {goal.id, None})
        self.assertTrue(all(reminder.reminder_type == "deadline" for reminder in reminders))
        self.assertTrue(all(reminder.source == "worker" for reminder in reminders))

    def test_generate_deadline_reminders_worker_returns_json_ready_payload(self):
        target_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Worker due task",
            deadline=target_date,
        )

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = generate_deadline_reminders.run(
                user_id=str(self.user.id),
                target_date=target_date.isoformat(),
                window_days=1,
            )

        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["reminders"][0]["reminder_type"], "deadline")
        self.assertEqual(result["reminders"][0]["task_id"] is not None, True)

    def test_generate_execution_reminders_uses_existing_today_plan_once(self):
        plan_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Pinned execution task",
            priority=1,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Recommended execution task",
            priority=3,
        )
        planning_service.get_today(self.db, user_id=self.user.id, plan_date=plan_date)

        first = reminder_service.generate_execution_reminders(
            self.db,
            user_id=self.user.id,
            plan_date=plan_date,
            limit=2,
        )
        second = reminder_service.generate_execution_reminders(
            self.db,
            user_id=self.user.id,
            plan_date=plan_date,
            limit=2,
        )

        self.assertEqual(first["status"], "generated")
        self.assertEqual(first["created_count"], 2)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["skipped_existing_count"], 2)
        self.assertEqual(
            self.db.query(Reminder).filter(Reminder.reminder_type == "execution").count(),
            2,
        )
        self.assertTrue(all(reminder.task_id for reminder in first["reminders"]))
        self.assertTrue(all(reminder.reminder_metadata["generator"] == "execution_v1" for reminder in first["reminders"]))
        self.assertEqual(
            {reminder.reminder_metadata["section"] for reminder in first["reminders"]},
            {"pinned", "recommended"},
        )

    def test_generate_execution_reminders_does_not_create_today_plan(self):
        plan_date = datetime(2026, 5, 17, tzinfo=UTC).date()

        result = reminder_service.generate_execution_reminders(
            self.db,
            user_id=self.user.id,
            plan_date=plan_date,
        )

        self.assertEqual(result["status"], "no_plan")
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(self.db.query(DailyPlan).count(), 0)
        self.assertEqual(self.db.query(Reminder).count(), 0)

    def test_generate_execution_reminders_worker_returns_json_ready_payload(self):
        plan_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Worker execution task",
            priority=1,
        )
        planning_service.get_today(self.db, user_id=self.user.id, plan_date=plan_date)

        with patch("app.workers.tasks.SessionLocal", TestingSessionLocal):
            result = generate_execution_reminders.run(
                user_id=str(self.user.id),
                plan_date=plan_date.isoformat(),
                limit=1,
            )

        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["reminders"][0]["reminder_type"], "execution")
        self.assertTrue(result["reminders"][0]["task_id"])

    def test_generate_execution_reminders_respects_disabled_preference(self):
        plan_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        self.db.add(UserSettings(user_id=self.user.id, reminder_execution_enabled=False))
        self.db.commit()
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Muted execution task",
            priority=1,
        )
        planning_service.get_today(self.db, user_id=self.user.id, plan_date=plan_date)

        result = reminder_service.generate_execution_reminders(
            self.db,
            user_id=self.user.id,
            plan_date=plan_date,
        )

        self.assertEqual(result["status"], "disabled")
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(self.db.query(Reminder).filter(Reminder.reminder_type == "execution").count(), 0)

    def test_generate_execution_reminders_uses_settings_defaults(self):
        plan_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        self.db.add(
            UserSettings(
                user_id=self.user.id,
                reminder_channel_in_app_enabled=False,
                reminder_channel_push_enabled=True,
                execution_reminder_limit=1,
                execution_reminder_start_hour=10,
                execution_reminder_spacing_minutes=30,
            )
        )
        self.db.commit()
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Settings execution task 1",
            priority=1,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Settings execution task 2",
            priority=2,
        )
        planning_service.get_today(self.db, user_id=self.user.id, plan_date=plan_date)

        result = reminder_service.generate_execution_reminders(
            self.db,
            user_id=self.user.id,
            plan_date=plan_date,
        )

        scheduled_for = result["reminders"][0].scheduled_for
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=UTC)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["reminders"][0].channel, "push")
        self.assertEqual(scheduled_for, datetime(2026, 5, 17, 2, 0, tzinfo=UTC))

    def test_generate_deadline_reminders_respects_disabled_preference(self):
        target_date = datetime(2026, 5, 17, tzinfo=UTC).date()
        self.db.add(UserSettings(user_id=self.user.id, reminder_deadline_enabled=False))
        self.db.commit()
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Muted deadline task",
            deadline=target_date,
        )

        result = reminder_service.generate_deadline_reminders(
            self.db,
            user_id=self.user.id,
            target_date=target_date,
        )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["skipped_disabled_count"], 1)
        self.assertEqual(self.db.query(Reminder).filter(Reminder.reminder_type == "deadline").count(), 0)


if __name__ == "__main__":
    unittest.main()
