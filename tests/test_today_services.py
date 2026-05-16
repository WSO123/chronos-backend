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
        self.assertEqual(today["insights_preview"]["source"], "rule-today-insights-v1")
        self.assertEqual(today["insights_preview"]["risk_alerts"][0]["key"], "high_value_due_today")
        self.assertEqual(today["insights_preview"]["remaining_time_suggestion"]["key"], "remaining_time")
        self.assertTrue(today["insights_preview"]["adjustment_suggestions"])

    def test_today_insights_preview_flags_overdue_and_heavy_work(self):
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Recover overdue milestone",
            estimated_duration_min=120,
            priority=1,
            value_level=ValueLevel.HIGH,
            deadline=self.plan_date - timedelta(days=1),
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Heavy remaining work",
            estimated_duration_min=90,
            priority=2,
            value_level=ValueLevel.HIGH,
        )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        preview = today["insights_preview"]

        self.assertEqual(preview["risk_alerts"][0]["key"], "overdue_task")
        self.assertEqual(preview["remaining_time_suggestion"]["signal"], "risk")
        self.assertEqual(preview["adjustment_suggestions"][0]["key"], "protect_risk_task")

    def test_strategy_detail_explains_current_plan_without_changing_state(self):
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Protect strategy task",
            estimated_duration_min=45,
            priority=2,
            value_level=ValueLevel.HIGH,
            deadline=self.plan_date,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Keep lightweight admin visible",
            estimated_duration_min=20,
            priority=5,
            value_level=ValueLevel.LOW,
        )

        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)
        same_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(strategy["daily_plan_id"], same_today["daily_plan_id"])
        self.assertEqual(strategy["plan_version"], 1)
        self.assertEqual(strategy["revision"]["version"], 1)
        self.assertEqual(strategy["factors"]["task_count"], 2)
        self.assertEqual(strategy["factors"]["high_value_task_count"], 1)
        self.assertEqual(strategy["factors"]["pinned_count"], 1)
        self.assertEqual(strategy["factors"]["low_priority_count"], 1)
        self.assertEqual(strategy["factors"]["total_estimated_minutes"], 65)
        self.assertEqual(len(strategy["task_rationales"]), 2)
        self.assertEqual(strategy["task_rationales"][0]["title"], "Protect strategy task")
        self.assertTrue(strategy["explanation"])
        self.assertEqual(strategy["source"]["model_name"], "rule-planner")

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

    def test_replan_preserves_completed_today_progress(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Already done today")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        planning_service.update_item_status(
            self.db,
            item_id=item_id,
            user_id=self.user.id,
            status=DailyPlanItemStatus.COMPLETED,
        )

        replanned = planning_service.replan_today(
            self.db,
            user_id=self.user.id,
            plan_date=self.plan_date,
            reason="Keep progress stable",
        )

        self.assertEqual(replanned["progress"]["completed_count"], 1)
        self.assertEqual(replanned["progress"]["total_count"], 1)
        self.assertEqual(replanned["progress"]["completion_rate"], 1.0)
        self.assertEqual(replanned["sections"]["recommended_tasks"][0]["task_id"], task.id)
        self.assertEqual(replanned["sections"]["recommended_tasks"][0]["item_status"], DailyPlanItemStatus.COMPLETED)

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

    def test_update_item_planned_reactivates_postponed_task(self):
        task = task_service.create_task(self.db, user_id=self.user.id, title="Bring back today")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        planning_service.update_item_status(
            self.db,
            item_id=item_id,
            user_id=self.user.id,
            status=DailyPlanItemStatus.POSTPONED,
        )

        updated_item = planning_service.update_item_status(
            self.db,
            item_id=item_id,
            user_id=self.user.id,
            status=DailyPlanItemStatus.PLANNED,
        )
        refreshed_task = self.db.get(Task, task.id)
        refreshed_today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(updated_item["item_status"], DailyPlanItemStatus.PLANNED)
        self.assertEqual(refreshed_task.status, TaskStatus.ACTIVE)
        self.assertEqual(refreshed_today["sections"]["recommended_tasks"][0]["item_status"], DailyPlanItemStatus.PLANNED)
        self.assertIn("TASK_ACTIVATED", {event.event_type for event in events})


if __name__ == "__main__":
    unittest.main()
