import unittest

from app.models.activity_event import ActivityEvent
from app.models.enums import TaskStatus, ValueLevel
from app.services.errors import InvalidStateError
from app.services.goal_service import goal_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class TaskGoalServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)

    def tearDown(self):
        self.db.close()

    def test_create_task_with_goal_and_complete_records_events(self):
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Ship Chronos MVP",
            value_level=ValueLevel.HIGH,
        )
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Design Task API",
            value_level=ValueLevel.HIGH,
        )

        completed = task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.related_task_id == task.id).all()

        self.assertEqual(completed.status, TaskStatus.COMPLETED)
        self.assertEqual(completed.progress, 1)
        self.assertIn("TASK_CREATED", {event.event_type for event in events})
        self.assertIn("TASK_COMPLETED", {event.event_type for event in events})

    def test_postponing_completed_task_raises_invalid_state(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Finish this")
        task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

        with self.assertRaises(InvalidStateError):
            task_service.postpone_task(self.db, task_id=task.id, user_id=self.user.id)

    def test_completing_completed_task_raises_invalid_state(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Finish once")
        task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

        with self.assertRaises(InvalidStateError):
            task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

    def test_create_and_complete_step_records_event(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Break down")
        step = task_service.create_step(
            self.db,
            task_id=task.id,
            user_id=self.user.id,
            title="First step",
        )

        completed_step = task_service.complete_step(
            self.db,
            task_id=task.id,
            step_id=step.id,
            user_id=self.user.id,
        )
        events = task_service.list_task_events(self.db, task_id=task.id, user_id=self.user.id)

        self.assertTrue(completed_step.is_completed)
        self.assertIn("TASK_STEP_COMPLETED", [event.event_type for event in events])


if __name__ == "__main__":
    unittest.main()
