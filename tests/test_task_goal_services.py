import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.activity_event import ActivityEvent
from app.models.enums import AIJobStatus, TaskStatus, ValueLevel
from app.services.errors import InvalidStateError
from app.services.focus_service import focus_service
from app.services.goal_service import goal_service
from app.services.planning_service import planning_service
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

    def test_task_detail_returns_light_execution_context(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Launch MVP",
            value_level=ValueLevel.HIGH,
        )
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Write Task Detail",
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        task_service.create_step(self.db, task_id=task.id, user_id=self.user.id, title="Return light context")
        planning_service.get_today(self.db, user_id=self.user.id, plan_date=today)

        detail = task_service.get_task_detail(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(detail["goal"]["title"], "Launch MVP")
        self.assertEqual(detail["ai_info"]["recommended_duration_min"], 25)
        self.assertEqual(detail["ai_info"]["execution_suggestion"], "Continue with: Return light context")
        self.assertIsNotNone(detail["today_context"])
        self.assertEqual(detail["today_context"]["plan_version"], 1)
        self.assertTrue(detail["actions"]["can_start_focus"])
        self.assertFalse(detail["focus_state"]["is_currently_focusing_this_task"])

    def test_task_detail_disables_start_focus_when_another_session_is_active(self):
        first = task_service.create_task(self.db, user_id=self.user.id, title="Currently focusing")
        second = task_service.create_task(self.db, user_id=self.user.id, title="Waiting task")
        session = focus_service.start_session(self.db, user_id=self.user.id, task_id=first.id)

        detail = task_service.get_task_detail(self.db, task_id=second.id, user_id=self.user.id)

        self.assertEqual(detail["focus_state"]["active_focus_session_id"], session.id)
        self.assertFalse(detail["focus_state"]["is_currently_focusing_this_task"])
        self.assertFalse(detail["actions"]["can_start_focus"])

    def test_breakdown_task_creates_rule_steps_and_ai_job(self):
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Break this into steps",
            estimated_duration_min=70,
        )

        result = task_service.breakdown_task(self.db, task_id=task.id, user_id=self.user.id)
        events = task_service.list_task_events(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(result["ai_job"]["status"], AIJobStatus.SUCCEEDED_WITH_FALLBACK)
        self.assertEqual(result["ai_job"]["job_metadata"]["fallback_reason"], "rule_mock_breakdown")
        self.assertEqual(len(result["created_steps"]), 4)
        self.assertEqual([step.sort_order for step in result["created_steps"]], [1, 2, 3, 4])
        self.assertIn("TASK_BREAKDOWN_GENERATED", [event.event_type for event in events])
        self.assertIn("TASK_STEP_CREATED", [event.event_type for event in events])

    def test_breakdown_task_preserves_existing_steps(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Already split")
        existing_step = task_service.create_step(self.db, task_id=task.id, user_id=self.user.id, title="Keep this")

        result = task_service.breakdown_task(self.db, task_id=task.id, user_id=self.user.id)
        detail = task_service.get_task_detail(self.db, task_id=task.id, user_id=self.user.id)

        self.assertEqual(result["created_steps"], [])
        self.assertEqual(result["ai_job"]["job_metadata"]["fallback_reason"], "existing_steps_preserved")
        self.assertEqual(len(detail["steps"]), 1)
        self.assertEqual(detail["steps"][0].id, existing_step.id)

    def test_breakdown_completed_task_raises_invalid_state(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Already done")
        task_service.complete_task(self.db, task_id=task.id, user_id=self.user.id)

        with self.assertRaises(InvalidStateError):
            task_service.breakdown_task(self.db, task_id=task.id, user_id=self.user.id)


if __name__ == "__main__":
    unittest.main()
