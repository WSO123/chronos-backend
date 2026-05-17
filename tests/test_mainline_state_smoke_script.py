import unittest

from scripts.smoke_mainline_state_consistency import build_mainline_state_payload, validate_mainline_state_payload


class MainlineStateSmokeScriptTests(unittest.TestCase):
    def test_build_payload_marks_required_state_checks(self):
        payload = build_mainline_state_payload(
            user_id="user-1",
            goal_id="goal-1",
            prerequisite_task_id="task-prerequisite",
            dependent_task_id="task-dependent",
            capture_id="capture-1",
            inbox_item_id="inbox-1",
            captured_task_id="task-captured",
            daily_plan_id="plan-1",
            initial_plan_version=1,
            dependency_plan_version=2,
            confirm_plan_version=3,
            priority_plan_version=4,
            final_plan_version=4,
            focus_session_id="focus-1",
            daily_report_id="report-1",
            report_focus_minutes=17,
            report_completed_task_count=1,
            strategy_user_adjusted_count=1,
            strategy_dependency_protected_count=1,
            focus_auto_linked=True,
            report_reused=True,
        )

        validate_mainline_state_payload(payload)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scenario"], "mainline_state_consistency")
        self.assertTrue(all(payload["state_checks"].values()))
        self.assertEqual(payload["today_versions"]["after_priority_adjustment"], 4)
        self.assertEqual(payload["today_versions"]["final"], 4)

    def test_validate_payload_rejects_failed_state_check(self):
        payload = build_mainline_state_payload(
            user_id="user-1",
            goal_id="goal-1",
            prerequisite_task_id="task-prerequisite",
            dependent_task_id="task-dependent",
            capture_id="capture-1",
            inbox_item_id="inbox-1",
            captured_task_id="task-captured",
            daily_plan_id="plan-1",
            initial_plan_version=1,
            dependency_plan_version=1,
            confirm_plan_version=2,
            priority_plan_version=3,
            final_plan_version=4,
            focus_session_id="focus-1",
            daily_report_id="report-1",
            report_focus_minutes=17,
            report_completed_task_count=1,
            strategy_user_adjusted_count=1,
            strategy_dependency_protected_count=1,
            focus_auto_linked=True,
            report_reused=True,
        )

        with self.assertRaises(RuntimeError) as raised:
            validate_mainline_state_payload(payload)

        self.assertIn("dependency_refresh", str(raised.exception))
        self.assertIn("focus_did_not_replan_today", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
