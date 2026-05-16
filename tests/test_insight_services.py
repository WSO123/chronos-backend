import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.enums import ValueLevel
from app.services.focus_service import focus_service
from app.services.goal_service import goal_service
from app.services.insight_service import insight_service
from app.services.planning_service import planning_service
from app.services.task_service import task_service
from tests.db import TestingSessionLocal, reset_database
from tests.factories import create_user


class InsightServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.db = TestingSessionLocal()
        self.user = create_user(self.db)
        self.anchor_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()

    def tearDown(self):
        self.db.close()

    def test_insight_detail_summarizes_behavior_patterns_and_recommendations(self):
        goal = goal_service.create_goal(
            self.db,
            user_id=self.user.id,
            title="Insight goal",
            deadline=self.anchor_date,
            value_level=ValueLevel.HIGH,
        )
        high_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Complete valuable task",
            deadline=self.anchor_date,
            value_level=ValueLevel.HIGH,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            goal_id=goal.id,
            title="Still overdue task",
            deadline=self.anchor_date - timedelta(days=2),
            value_level=ValueLevel.HIGH,
        )
        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.anchor_date)
        high_item = self._item_for_task(today, high_task.id)

        session = focus_service.start_session(
            self.db,
            user_id=self.user.id,
            task_id=high_task.id,
            daily_plan_item_id=high_item["daily_plan_item_id"],
        )
        focus_service.complete_session(self.db, session_id=session.id, user_id=self.user.id, actual_duration_min=30)

        insight = insight_service.get_detail(self.db, user_id=self.user.id, anchor_date=self.anchor_date)
        pattern_keys = {pattern["key"] for pattern in insight["behavior_patterns"]}

        self.assertEqual(insight["anchor_date"], self.anchor_date)
        self.assertEqual(insight["overview"]["total_completed_task_count"], 1)
        self.assertEqual(insight["overview"]["high_value_completed_task_count"], 1)
        self.assertEqual(insight["overview"]["total_focus_minutes"], 30)
        self.assertEqual(insight["overview"]["overdue_task_count"], 1)
        self.assertIn("high_value_progress", pattern_keys)
        self.assertIn("lagging_tasks", pattern_keys)
        self.assertTrue(insight["efficiency_windows"])
        self.assertTrue(insight["recommendations"])
        self.assertTrue(insight["strategy_notes"])
        self.assertEqual(insight["source"]["generated_by"], "rule-insight-v1")

    def _item_for_task(self, today: dict, task_id) -> dict:
        for section_items in today["sections"].values():
            for item in section_items:
                if item["task_id"] == task_id:
                    return item
        raise AssertionError(f"Task {task_id} not found in Today items")


if __name__ == "__main__":
    unittest.main()
