import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.activity_event import ActivityEvent
from app.models.enums import DailyPlanItemStatus, ValueLevel
from app.models.report import DailyReport
from app.services.focus_service import focus_service
from app.services.goal_service import goal_service
from app.services.me_service import me_service
from app.services.planning_service import planning_service
from app.services.report_service import report_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class ReportAndMeServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.report_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()

    def tearDown(self):
        self.db.close()

    def test_weekly_report_aggregates_trends_focus_and_lagging_tasks(self):
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Ship valuable work",
            deadline=self.report_date,
            value_level=ValueLevel.HIGH,
        )
        high_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Finish high-value task",
            value_level=ValueLevel.HIGH,
            deadline=self.report_date,
        )
        lagging_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Unblock overdue task",
            value_level=ValueLevel.HIGH,
            deadline=self.report_date - timedelta(days=2),
        )
        low_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Light admin task",
            value_level=ValueLevel.LOW,
        )
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.report_date)
        today_items = self._today_items(today)
        high_item = self._item_for_task(today_items, high_task.id)
        low_item = self._item_for_task(today_items, low_task.id)

        focus_session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=high_task.id,
            daily_plan_item_id=high_item["daily_plan_item_id"],
        )
        focus_service.complete_session(
            self.db,
            session_id=focus_session.id,
            user_id=self.user.id,
            actual_duration_min=30,
        )
        planning_service.update_item_status(
            self.db,
            item_id=low_item["daily_plan_item_id"],
            user_id=self.user.id,
            status=DailyPlanItemStatus.POSTPONED,
        )

        week_start = self.report_date - timedelta(days=self.report_date.weekday())
        report = report_service.get_weekly_report(self.db, user_id=self.user.id, week_start=week_start)
        today_trend = next(day for day in report["daily_trends"] if day["report_date"] == self.report_date)

        self.assertEqual(report["week_start"], week_start)
        self.assertEqual(report["week_end"], week_start + timedelta(days=6))
        self.assertEqual(report["summary"]["total_completed_task_count"], 1)
        self.assertEqual(report["summary"]["total_postponed_task_count"], 1)
        self.assertEqual(report["summary"]["total_focus_minutes"], 30)
        self.assertEqual(report["summary"]["high_value_completed_task_count"], 1)
        self.assertEqual(report["summary"]["active_goal_count"], 1)
        self.assertEqual(report["summary"]["at_risk_goal_count"], 1)
        self.assertEqual(report["summary"]["overdue_task_count"], 1)
        self.assertEqual(report["focus"]["best_focus_date"], self.report_date)
        self.assertEqual(report["focus"]["best_focus_minutes"], 30)
        self.assertEqual(today_trend["completed_task_count"], 1)
        self.assertEqual(today_trend["high_value_completed_task_count"], 1)
        self.assertEqual(report["lagging_tasks"][0]["id"], lagging_task.id)
        self.assertTrue(report["ai_suggestions"])

    def test_monthly_report_aggregates_daily_and_weekly_trends(self):
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Monthly goal",
            deadline=self.report_date,
            value_level=ValueLevel.HIGH,
        )
        high_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Monthly high-value task",
            value_level=ValueLevel.HIGH,
            deadline=self.report_date,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Monthly overdue task",
            value_level=ValueLevel.HIGH,
            deadline=self.report_date - timedelta(days=2),
        )
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.report_date)
        high_item = self._item_for_task(self._today_items(today), high_task.id)
        focus_session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=high_task.id,
            daily_plan_item_id=high_item["daily_plan_item_id"],
        )
        focus_service.complete_session(
            self.db,
            session_id=focus_session.id,
            user_id=self.user.id,
            actual_duration_min=40,
        )

        report = report_service.get_monthly_report(self.db, user_id=self.user.id, month=self.report_date)
        today_trend = next(day for day in report["daily_trends"] if day["report_date"] == self.report_date)

        self.assertEqual(report["month_start"], self.report_date.replace(day=1))
        self.assertEqual(report["summary"]["total_completed_task_count"], 1)
        self.assertEqual(report["summary"]["high_value_completed_task_count"], 1)
        self.assertEqual(report["summary"]["total_focus_minutes"], 40)
        self.assertEqual(report["summary"]["overdue_task_count"], 1)
        self.assertEqual(today_trend["completed_task_count"], 1)
        self.assertEqual(today_trend["high_value_completed_task_count"], 1)
        self.assertTrue(report["weekly_trends"])
        self.assertTrue(report["ai_suggestions"])

    def test_generate_daily_report_summarizes_today_focus_and_events(self):
        task_service.create_task(self.db, user_id=self.user.id, title="Finish important work")
        task_service.create_task(self.db, user_id=self.user.id, title="Interruptible work")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.report_date)
        first_item = today["sections"]["recommended_tasks"][0]
        second_item = today["sections"]["recommended_tasks"][1]

        first_session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=first_item["task_id"],
            daily_plan_item_id=first_item["daily_plan_item_id"],
        )
        focus_service.complete_session(self.db, session_id=first_session.id, user_id=self.user.id, actual_duration_min=30)
        second_session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=second_item["task_id"],
            daily_plan_item_id=second_item["daily_plan_item_id"],
        )
        focus_service.interrupt_session(
            self.db,
            session_id=second_session.id,
            user_id=self.user.id,
            actual_duration_min=5,
            interruption_reason="Need to switch",
        )
        planning_service.update_item_status(
            self.db,
            item_id=second_item["daily_plan_item_id"],
            user_id=self.user.id,
            status=DailyPlanItemStatus.POSTPONED,
        )

        report = report_service.generate_daily_report(self.db, user_id=self.user.id, report_date=self.report_date)
        events = self.db.query(ActivityEvent).filter(ActivityEvent.user_id == self.user.id).all()

        self.assertEqual(report.completed_task_count, 1)
        self.assertEqual(report.postponed_task_count, 1)
        self.assertEqual(report.interrupted_count, 1)
        self.assertEqual(report.focus_minutes, 35)
        self.assertEqual(report.completion_rate, 0.5)
        self.assertEqual(report.generated_from_plan_version, 1)
        self.assertTrue(report.ai_summary)
        self.assertTrue(report.ai_suggestions)
        self.assertIn("DAILY_REPORT_GENERATED", {event.event_type for event in events})

    def test_get_or_generate_daily_report_is_idempotent_until_refresh(self):
        task_service.create_task(self.db, user_id=self.user.id, title="Report task")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.report_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        planning_service.update_item_status(
            self.db,
            item_id=item_id,
            user_id=self.user.id,
            status=DailyPlanItemStatus.COMPLETED,
        )

        first = report_service.get_or_generate_daily_report(self.db, user_id=self.user.id, report_date=self.report_date)
        second = report_service.get_or_generate_daily_report(self.db, user_id=self.user.id, report_date=self.report_date)
        refreshed = report_service.generate_daily_report(self.db, user_id=self.user.id, report_date=self.report_date)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.id, refreshed.id)
        self.assertEqual(self.db.query(DailyReport).filter(DailyReport.user_id == self.user.id).count(), 1)

    def test_me_overview_returns_basic_feedback_without_generating_report(self):
        task_service.create_task(self.db, user_id=self.user.id, title="Overview task")
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.report_date)
        item_id = today["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        planning_service.update_item_status(
            self.db,
            item_id=item_id,
            user_id=self.user.id,
            status=DailyPlanItemStatus.COMPLETED,
        )

        overview = me_service.get_overview(self.db, user_id=self.user.id, today=self.report_date)

        self.assertEqual(overview["profile"]["user_id"], self.user.id)
        self.assertEqual(overview["today"]["completed_task_count"], 1)
        self.assertEqual(overview["today"]["completion_rate"], 1.0)
        self.assertEqual(overview["tasks"]["completed_task_count"], 1)
        self.assertEqual(overview["reports"]["daily_report_available"], False)

    def _today_items(self, today: dict) -> list[dict]:
        items: list[dict] = []
        for section_items in today["sections"].values():
            items.extend(section_items)
        return items

    def _item_for_task(self, items: list[dict], task_id) -> dict:
        for item in items:
            if item["task_id"] == task_id:
                return item
        raise AssertionError(f"Task {task_id} not found in Today items")


if __name__ == "__main__":
    unittest.main()
