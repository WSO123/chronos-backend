import unittest

from scripts.smoke_p1_mainline_contract import build_p1_contract_payload, validate_p1_contract_payload


class P1MainlineContractSmokeScriptTests(unittest.TestCase):
    def test_build_payload_marks_required_contract_checks(self):
        payload = build_p1_contract_payload(
            user_id="user-1",
            auth_me_email="p1@example.com",
            registered_email="p1@example.com",
            focus_capture_id="capture-focus",
            focus_inbox_item_id="inbox-focus",
            focus_task_id="task-focus",
            focus_confirm_plan_exists=False,
            focus_confirm_replanned=False,
            postpone_capture_id="capture-postpone",
            postpone_inbox_item_id="inbox-postpone",
            postpone_task_id="task-postpone",
            postpone_confirm_plan_exists=False,
            postpone_confirm_replanned=False,
            daily_plan_id="plan-1",
            today_plan_version=1,
            final_plan_version=1,
            today_total_count=2,
            today_focus_minutes=18,
            today_completion_rate=0.5,
            today_can_replan=True,
            today_can_capture=True,
            today_can_view_report=True,
            task_detail_context_matches=True,
            focus_session_id="focus-1",
            focus_completed_status="completed",
            focus_daily_plan_item_id="item-focus",
            expected_focus_daily_plan_item_id="item-focus",
            task_detail_during_focus_session_id="focus-1",
            task_detail_after_focus_status="completed",
            task_detail_after_focus_progress="1.00",
            today_focus_item_status="completed",
            postponed_today_item_status="postponed",
            task_detail_after_postpone_status="postponed",
            today_postpone_item_status="postponed",
            daily_report_id="report-1",
            report_daily_plan_id="plan-1",
            report_completed_task_count=1,
            report_postponed_task_count=1,
            report_focus_minutes=18,
            report_completion_rate=0.5,
            me_daily_report_id="report-1",
            me_daily_report_available=True,
            me_today_completed_task_count=1,
            me_today_focus_minutes=18,
            me_tasks_completed_task_count=1,
            me_tasks_postponed_task_count=1,
        )

        validate_p1_contract_payload(payload)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scenario"], "p1_mainline_contract")
        self.assertTrue(all(payload["contract_checks"].values()))

    def test_validate_payload_rejects_contract_mismatch(self):
        payload = build_p1_contract_payload(
            user_id="user-1",
            auth_me_email="other@example.com",
            registered_email="p1@example.com",
            focus_capture_id="capture-focus",
            focus_inbox_item_id="inbox-focus",
            focus_task_id="task-focus",
            focus_confirm_plan_exists=True,
            focus_confirm_replanned=False,
            postpone_capture_id="capture-postpone",
            postpone_inbox_item_id="inbox-postpone",
            postpone_task_id="task-postpone",
            postpone_confirm_plan_exists=False,
            postpone_confirm_replanned=False,
            daily_plan_id="plan-1",
            today_plan_version=1,
            final_plan_version=1,
            today_total_count=2,
            today_focus_minutes=18,
            today_completion_rate=0.5,
            today_can_replan=True,
            today_can_capture=True,
            today_can_view_report=True,
            task_detail_context_matches=True,
            focus_session_id="focus-1",
            focus_completed_status="completed",
            focus_daily_plan_item_id="item-focus",
            expected_focus_daily_plan_item_id="item-focus",
            task_detail_during_focus_session_id="focus-1",
            task_detail_after_focus_status="completed",
            task_detail_after_focus_progress="1.00",
            today_focus_item_status="completed",
            postponed_today_item_status="postponed",
            task_detail_after_postpone_status="active",
            today_postpone_item_status="postponed",
            daily_report_id="report-1",
            report_daily_plan_id="plan-1",
            report_completed_task_count=1,
            report_postponed_task_count=1,
            report_focus_minutes=18,
            report_completion_rate=0.5,
            me_daily_report_id="report-1",
            me_daily_report_available=True,
            me_today_completed_task_count=1,
            me_today_focus_minutes=18,
            me_tasks_completed_task_count=1,
            me_tasks_postponed_task_count=1,
        )

        with self.assertRaises(RuntimeError) as raised:
            validate_p1_contract_payload(payload)

        self.assertIn("auth_me_matches_registered", str(raised.exception))
        self.assertIn("captures_confirm_without_hidden_today", str(raised.exception))
        self.assertIn("today_quick_postpone_updates_task", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
