import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.activity_event import ActivityEvent
from app.models.enums import DailyPlanItemStatus
from app.models.report import DailyReport
from app.services.focus_service import focus_service
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


if __name__ == "__main__":
    unittest.main()
