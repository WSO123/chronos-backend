import unittest
from datetime import date, timedelta

from app.models.activity_event import ActivityEvent
from app.models.enums import DailyPlanItemStatus, TaskStatus, ValueLevel
from app.models.task import Task
from app.services.planning_service import planning_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class TodayServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.plan_date = date(2026, 5, 16)

    def tearDown(self):
        self.db.close()

    def test_today_lazy_creates_daily_plan_with_light_sections(self):
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Protect high value work",
            estimated_duration_min=45,
            priority=2,
            value_level=ValueLevel.HIGH,
            deadline=self.plan_date,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Optional cleanup",
            estimated_duration_min=20,
            priority=5,
            value_level=ValueLevel.LOW,
        )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        same_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(today["daily_plan_id"], same_today["daily_plan_id"])
        self.assertEqual(today["plan_version"], 1)
        self.assertEqual(today["sections"]["pinned_tasks"][0]["title"], "Protect high value work")
        self.assertEqual(today["sections"]["low_priority_tasks"][0]["title"], "Optional cleanup")
        self.assertEqual(today["progress"]["total_count"], 2)

    def test_replan_creates_new_revision_and_keeps_same_plan(self):
        task_service.create_task(self.db, user_id=self.user.id, title="First task")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="New urgent task",
            priority=1,
            deadline=self.plan_date + timedelta(days=1),
        )

        replanned = planning_service.replan_today(
            self.db,
            user_id=self.user.id,
            plan_date=self.plan_date,
            reason="New task arrived",
        )

        self.assertEqual(replanned["daily_plan_id"], today["daily_plan_id"])
        self.assertEqual(replanned["plan_version"], 2)
        self.assertEqual(replanned["sections"]["pinned_tasks"][0]["title"], "New urgent task")

    def test_update_item_complete_syncs_task_progress_and_events(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Finish from Today")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        updated_item = planning_service.update_item_status(
            self.db,
            item_id=item_id,
            user_id=self.user.id,
            status=DailyPlanItemStatus.COMPLETED,
        )
        refreshed_task = self.db.get(Task, task.id)
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(updated_item["item_status"], DailyPlanItemStatus.COMPLETED)
        self.assertEqual(refreshed_task.status, TaskStatus.COMPLETED)
        self.assertEqual(refreshed_today["progress"]["completed_count"], 1)
        self.assertEqual(refreshed_today["progress"]["completion_rate"], 1.0)
        self.assertIn("TASK_COMPLETED", {event.event_type for event in events})
        self.assertIn("DAILY_PLAN_ITEM_UPDATED", {event.event_type for event in events})


if __name__ == "__main__":
    unittest.main()
