import unittest
from datetime import date
from decimal import Decimal

from app.models.activity_event import ActivityEvent
from app.models.enums import DailyPlanItemStatus, FocusSessionStatus, TaskStatus, ValueLevel
from app.models.focus_session import FocusSession
from app.models.task import Task
from app.services.errors import InvalidStateError
from app.services.focus_service import focus_service
from app.services.goal_service import goal_service
from app.services.planning_service import planning_service
from app.services.task_planning_signal_service import task_planning_signal_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class FocusServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.plan_date = date(2026, 5, 16)

    def tearDown(self):
        self.db.close()

    def test_start_and_complete_focus_updates_task_today_and_events(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Execute from Focus")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=task.id,
            daily_plan_item_id=item_id,
            planned_duration_min=25,
        )
        completed = focus_service.complete_session(
            self.db,
            session_id=session.id,
            user_id=self.user.id,
            actual_duration_min=18,
        )
        refreshed_task = self.db.get(Task, task.id)
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(completed.status, FocusSessionStatus.COMPLETED)
        self.assertEqual(completed.actual_duration_min, 18)
        self.assertEqual(refreshed_task.status, TaskStatus.COMPLETED)
        self.assertEqual(refreshed_task.actual_duration_min, 18)
        self.assertEqual(refreshed_today["progress"]["completed_count"], 1)
        self.assertEqual(refreshed_today["progress"]["focus_minutes"], 18)
        self.assertEqual(refreshed_today["sections"]["recommended_tasks"][0]["item_status"], DailyPlanItemStatus.COMPLETED)
        self.assertIn("FOCUS_SESSION_STARTED", {event.event_type for event in events})
        self.assertIn("FOCUS_SESSION_COMPLETED", {event.event_type for event in events})
        self.assertIn("TASK_COMPLETED", {event.event_type for event in events})
        completed_event = next(event for event in events if event.event_type == "FOCUS_SESSION_COMPLETED")
        self.assertEqual(completed_event.payload["planned_duration_min"], 25)
        self.assertEqual(completed_event.payload["duration_delta_min"], -7)

    def test_start_focus_without_item_auto_links_current_today_item(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Auto link Today item")
        today = planning_service.get_today(self.db, user_id=self.user.id)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=task.id,
            planned_duration_min=25,
        )
        completed = focus_service.complete_session(
            self.db,
            session_id=session.id,
            user_id=self.user.id,
            actual_duration_min=14,
        )
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id)

        self.assertEqual(session.daily_plan_item_id, item_id)
        self.assertEqual(completed.daily_plan_item_id, item_id)
        self.assertEqual(refreshed_today["progress"]["completed_count"], 1)
        self.assertEqual(refreshed_today["progress"]["focus_minutes"], 14)
        self.assertEqual(refreshed_today["sections"]["recommended_tasks"][0]["item_status"], DailyPlanItemStatus.COMPLETED)

    def test_complete_minimum_viable_focus_records_partial_task_progress(self):
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Focus slice goal",
            value_level=ValueLevel.HIGH,
        )
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="完成一个很大的专注任务",
            estimated_duration_min=180,
            priority=4,
            value_level=ValueLevel.MEDIUM,
        )
        task_planning_signal_service.generate_signal(self.db, task_id=task.id, user_id=self.user.id)
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item = today["sections"]["pinned_tasks"][0]
        session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=task.id,
            daily_plan_item_id=item["daily_plan_item_id"],
            planned_duration_min=item["estimated_duration_min"],
        )

        completed = focus_service.complete_session(
            self.db,
            session_id=session.id,
            user_id=self.user.id,
            actual_duration_min=40,
        )
        refreshed_task = self.db.get(Task, task.id)
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertTrue(item["score_breakdown"]["minimum_viable_progress_applied"])
        self.assertEqual(completed.status, FocusSessionStatus.COMPLETED)
        self.assertEqual(refreshed_task.status, TaskStatus.ACTIVE)
        self.assertEqual(refreshed_task.progress, Decimal("0.25"))
        self.assertEqual(refreshed_task.actual_duration_min, 40)
        self.assertEqual(refreshed_today["progress"]["completed_count"], 1)
        self.assertEqual(refreshed_today["progress"]["focus_minutes"], 40)
        self.assertEqual(refreshed_today["sections"]["pinned_tasks"][0]["item_status"], DailyPlanItemStatus.COMPLETED)
        event_types = {event.event_type for event in events}
        self.assertIn("TASK_PARTIAL_PROGRESS_RECORDED", event_types)
        self.assertNotIn("TASK_COMPLETED", event_types)

    def test_interrupt_focus_returns_task_to_active_and_keeps_item_planned(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Interruptible task")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        session = focus_service.start_session(self.db, user_id=self.user.id, task_id=task.id, daily_plan_item_id=item_id)

        interrupted = focus_service.interrupt_session(
            self.db,
            session_id=session.id,
            user_id=self.user.id,
            actual_duration_min=7,
            interruption_reason="Need to switch context",
        )
        refreshed_task = self.db.get(Task, task.id)
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(interrupted.status, FocusSessionStatus.INTERRUPTED)
        self.assertEqual(refreshed_task.status, TaskStatus.ACTIVE)
        self.assertEqual(refreshed_task.actual_duration_min, 7)
        self.assertEqual(refreshed_today["progress"]["completed_count"], 0)
        self.assertEqual(refreshed_today["progress"]["focus_minutes"], 7)
        self.assertEqual(refreshed_today["sections"]["recommended_tasks"][0]["item_status"], DailyPlanItemStatus.PLANNED)

    def test_postpone_focus_updates_task_and_today_item(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Postpone from Focus")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        session = focus_service.start_session(self.db, user_id=self.user.id, task_id=task.id, daily_plan_item_id=item_id)

        postponed = focus_service.postpone_session(
            self.db,
            session_id=session.id,
            user_id=self.user.id,
            actual_duration_min=5,
            interruption_reason="Not the right moment",
        )
        refreshed_task = self.db.get(Task, task.id)
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(postponed.status, FocusSessionStatus.POSTPONED)
        self.assertEqual(refreshed_task.status, TaskStatus.POSTPONED)
        self.assertEqual(refreshed_task.actual_duration_min, 5)
        self.assertEqual(refreshed_today["sections"]["recommended_tasks"][0]["item_status"], DailyPlanItemStatus.POSTPONED)

    def test_user_cannot_start_second_active_focus_session(self):
        first = task_service.create_task(self.db, user_id=self.user.id, title="First focus")
        second = task_service.create_task(self.db, user_id=self.user.id, title="Second focus")
        focus_service.start_session(self.db, user_id=self.user.id, task_id=first.id)

        with self.assertRaises(InvalidStateError):
            focus_service.start_session(self.db, user_id=self.user.id, task_id=second.id)

    def test_focus_session_model_has_active_user_unique_index(self):
        index = next(
            idx for idx in FocusSession.__table__.indexes if idx.name == "uq_focus_sessions_user_active"
        )

        self.assertTrue(index.unique)
        self.assertEqual([column.name for column in index.columns], ["user_id"])


if __name__ == "__main__":
    unittest.main()
