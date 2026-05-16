from __future__ import annotations


class SchedulerService:
    def reminder_schedule_plan(self) -> dict:
        return {
            "timezone": "UTC",
            "entries": [
                {
                    "task_name": "reminder.generate_deadline",
                    "cadence": "daily",
                    "schedule_hint": "Run once every morning after local-day rollover fanout.",
                    "scope": "all_active_users",
                    "enabled": True,
                    "payload_template": {
                        "user_id": None,
                        "target_date": "<today>",
                        "window_days": 1,
                        "reminder_hour": None,
                    },
                    "guardrails": [
                        "Uses UserSettings.deadline_reminder_hour when reminder_hour is null.",
                        "Skips users with notification or deadline reminders disabled.",
                        "Creates scheduled reminders only; does not dispatch.",
                    ],
                },
                {
                    "task_name": "reminder.generate_execution",
                    "cadence": "daily_after_today_plan",
                    "schedule_hint": "Fan out per active user after Today active plan exists.",
                    "scope": "per_user_with_active_today_plan",
                    "enabled": True,
                    "payload_template": {
                        "user_id": "<user_id>",
                        "plan_date": "<today>",
                        "limit": None,
                        "start_hour": None,
                        "spacing_minutes": None,
                    },
                    "guardrails": [
                        "Reads existing Today active plan only.",
                        "Does not lazy create Today plan and does not replan.",
                        "Uses UserSettings execution defaults when params are null.",
                    ],
                },
                {
                    "task_name": "reminder.dispatch_due",
                    "cadence": "every_5_minutes",
                    "schedule_hint": "Scan due reminders frequently with delivery cooldown protection.",
                    "scope": "scheduled_due_reminders",
                    "enabled": True,
                    "payload_template": {
                        "limit": 50,
                        "channel": None,
                        "now": None,
                    },
                    "guardrails": [
                        "Only scans status=scheduled reminders with scheduled_for <= now.",
                        "Marks sent only when delivery provider returns sent.",
                        "Honors ReminderDeliveryAttempt cooldown for skipped external channels.",
                    ],
                },
                {
                    "task_name": "reminder.cleanup_delivery_attempts",
                    "cadence": "daily",
                    "schedule_hint": "Remove old delivery attempts after retention window.",
                    "scope": "old_delivery_attempts",
                    "enabled": True,
                    "payload_template": {
                        "retention_days": 30,
                        "now": None,
                        "limit": 500,
                    },
                    "guardrails": [
                        "Deletes delivery attempts only; never deletes reminders.",
                        "Clamps retention_days to 1..365 and limit to 1..1000.",
                        "Run during low-traffic windows.",
                    ],
                },
            ],
            "notes": [
                "This is a scheduler contract, not an active Celery Beat configuration.",
                "Real deployment should wire these entries into the chosen scheduler explicitly.",
                "Execution reminders require active Today plans and should not create plans implicitly.",
            ],
        }

    def reminder_celery_beat_schedule(self) -> dict:
        return {
            "timezone": "UTC",
            "entries": [
                {
                    "name": "reminder-generate-deadline-daily",
                    "task": "reminder.generate_deadline",
                    "schedule": {
                        "type": "crontab",
                        "minute": 30,
                        "hour": 23,
                    },
                    "kwargs": {
                        "user_id": None,
                        "target_date": None,
                        "window_days": 1,
                        "reminder_hour": None,
                    },
                },
                {
                    "name": "reminder-dispatch-due-every-5-minutes",
                    "task": "reminder.dispatch_due",
                    "schedule": {
                        "type": "interval",
                        "seconds": 300,
                    },
                    "kwargs": {
                        "limit": 50,
                        "channel": None,
                        "now": None,
                    },
                },
                {
                    "name": "reminder-cleanup-delivery-attempts-daily",
                    "task": "reminder.cleanup_delivery_attempts",
                    "schedule": {
                        "type": "crontab",
                        "minute": 10,
                        "hour": 3,
                    },
                    "kwargs": {
                        "retention_days": 30,
                        "now": None,
                        "limit": 500,
                    },
                },
            ],
            "excluded_entries": [
                {
                    "task_name": "reminder.generate_execution",
                    "reason": "Requires per-user fanout after an active Today plan exists.",
                }
            ],
            "notes": [
                "This is a JSON-friendly Celery Beat proposal, not a running scheduler.",
                "Crontab entries are expressed in UTC.",
                "Execution reminder fanout should be implemented as a separate worker before Beat wiring.",
            ],
        }


scheduler_service = SchedulerService()
