import unittest

from app.services.scheduler_service import scheduler_service


class SchedulerServiceTests(unittest.TestCase):
    def test_data_source_schedule_plan_documents_required_workers(self):
        plan = scheduler_service.data_source_schedule_plan()
        entries = {entry["task_name"]: entry for entry in plan["entries"]}

        self.assertEqual(plan["timezone"], "UTC")
        self.assertIn("data_source.sync_ready_connections", entries)
        self.assertIn("health.sync_ready_energy_connections", entries)
        self.assertEqual(
            entries["data_source.sync_ready_connections"]["scope"],
            "connected_calendar_email_sources",
        )
        self.assertTrue(
            any(
                "Capture / Inbox" in guardrail
                for guardrail in entries["data_source.sync_ready_connections"]["guardrails"]
            )
        )
        self.assertTrue(
            any(
                "Does not create tasks" in guardrail
                for guardrail in entries["health.sync_ready_energy_connections"]["guardrails"]
            )
        )

    def test_data_source_celery_beat_schedule_excludes_single_connection_workers(self):
        schedule = scheduler_service.data_source_celery_beat_schedule()
        tasks = {entry["task"] for entry in schedule["entries"]}
        excluded = {entry["task_name"]: entry for entry in schedule["excluded_entries"]}

        self.assertEqual(schedule["timezone"], "UTC")
        self.assertIn("data_source.sync_ready_connections", tasks)
        self.assertIn("health.sync_ready_energy_connections", tasks)
        self.assertIn("data_source.sync_connection", excluded)
        self.assertIn("health.sync_energy_connection", excluded)
        self.assertIn("explicitly", excluded["data_source.sync_connection"]["reason"])

    def test_reminder_schedule_plan_documents_required_workers(self):
        plan = scheduler_service.reminder_schedule_plan()
        entries = {entry["task_name"]: entry for entry in plan["entries"]}

        self.assertEqual(plan["timezone"], "UTC")
        self.assertIn("reminder.generate_deadline", entries)
        self.assertIn("reminder.generate_execution_for_active_users", entries)
        self.assertIn("reminder.dispatch_due", entries)
        self.assertIn("reminder.cleanup_delivery_attempts", entries)
        self.assertEqual(
            entries["reminder.generate_execution_for_active_users"]["scope"],
            "per_user_with_active_today_plan",
        )
        self.assertTrue(
            any(
                "Does not lazy create Today plan" in guardrail
                for guardrail in entries["reminder.generate_execution_for_active_users"]["guardrails"]
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

    def test_reminder_celery_beat_schedule_excludes_execution_fanout(self):
        schedule = scheduler_service.reminder_celery_beat_schedule()
        tasks = {entry["task"] for entry in schedule["entries"]}
        excluded = {entry["task_name"]: entry for entry in schedule["excluded_entries"]}

        self.assertEqual(schedule["timezone"], "UTC")
        self.assertIn("reminder.generate_deadline", tasks)
        self.assertIn("reminder.generate_execution_for_active_users", tasks)
        self.assertIn("reminder.dispatch_due", tasks)
        self.assertIn("reminder.cleanup_delivery_attempts", tasks)
        self.assertNotIn("reminder.generate_execution", tasks)
        self.assertIn("reminder.generate_execution", excluded)
        self.assertIn("safe fanout", excluded["reminder.generate_execution"]["reason"])


if __name__ == "__main__":
    unittest.main()
