import unittest

from app.services.scheduler_service import scheduler_service


class SchedulerServiceTests(unittest.TestCase):
    def test_reminder_schedule_plan_documents_required_workers(self):
        plan = scheduler_service.reminder_schedule_plan()
        entries = {entry["task_name"]: entry for entry in plan["entries"]}

        self.assertEqual(plan["timezone"], "UTC")
        self.assertIn("reminder.generate_deadline", entries)
        self.assertIn("reminder.generate_execution", entries)
        self.assertIn("reminder.dispatch_due", entries)
        self.assertIn("reminder.cleanup_delivery_attempts", entries)
        self.assertEqual(entries["reminder.generate_execution"]["scope"], "per_user_with_active_today_plan")
        self.assertTrue(
            any(
                "Does not lazy create Today plan" in guardrail
                for guardrail in entries["reminder.generate_execution"]["guardrails"]
            )
        )
        self.assertTrue(
            any(
                "cooldown" in guardrail
                for guardrail in entries["reminder.dispatch_due"]["guardrails"]
            )
        )
        self.assertTrue(
            any(
                "never deletes reminders" in guardrail
                for guardrail in entries["reminder.cleanup_delivery_attempts"]["guardrails"]
            )
        )


if __name__ == "__main__":
    unittest.main()
