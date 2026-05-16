from __future__ import annotations


class SchedulerService:
    def scheduler_overview(self) -> dict:
        data_source_plan = self.data_source_schedule_plan()
        data_source_beat = self.data_source_celery_beat_schedule()
        reminder_plan = self.reminder_schedule_plan()
        reminder_beat = self.reminder_celery_beat_schedule()

        return {
            "timezone": "UTC",
            "domains": [
                self._overview_domain(
                    domain="data_sources",
                    display_name="Data Sources",
                    plan_path="/api/v1/scheduler/data-sources",
                    beat_path="/api/v1/scheduler/data-sources/celery-beat",
                    plan=data_source_plan,
                    beat=data_source_beat,
                ),
                self._overview_domain(
                    domain="reminders",
                    display_name="Reminders",
                    plan_path="/api/v1/scheduler/reminders",
                    beat_path="/api/v1/scheduler/reminders/celery-beat",
                    plan=reminder_plan,
                    beat=reminder_beat,
                ),
            ],
            "notes": [
                "This is a read-only scheduler overview, not a running scheduler.",
                "Domain plans remain the source of truth for guardrails and payload templates.",
                "Celery Beat proposals are JSON-friendly deployment hints and do not mutate celery_app.conf.",
            ],
        }

    def data_source_schedule_plan(self) -> dict:
        return {
            "timezone": "UTC",
            "entries": [
                {
                    "task_name": "data_source.sync_ready_connections",
                    "cadence": "every_15_minutes",
                    "schedule_hint": "Pull calendar and email source items into Capture / Inbox through ready connections.",
                    "scope": "connected_calendar_email_sources",
                    "enabled": True,
                    "payload_template": {
                        "limit": 50,
                    },
                    "guardrails": [
                        "Only syncs source_type in calendar/email.",
                        "Skips paused, disconnected, or sync_disabled connections.",
                        "Imports into Capture / Inbox and does not auto-confirm tasks.",
                    ],
                },
                {
                    "task_name": "health.sync_ready_energy_connections",
                    "cadence": "hourly",
                    "schedule_hint": "Pull health metrics into Energy Dashboard for connected health sources.",
                    "scope": "connected_health_sources",
                    "enabled": True,
                    "payload_template": {
                        "limit": 50,
                    },
                    "guardrails": [
                        "Only syncs health source connections.",
                        "Writes EnergyDailyMetric through health sync service.",
                        "Does not create tasks, reminders, or Today plans.",
                    ],
                },
            ],
            "notes": [
                "This is a scheduler contract, not an active Celery Beat configuration.",
                "Calendar and email sync must enter Capture / Inbox before user confirmation.",
                "Health sync feeds Energy Dashboard and Today strategy context only.",
            ],
        }

    def data_source_celery_beat_schedule(self) -> dict:
        return {
            "timezone": "UTC",
            "entries": [
                {
                    "name": "data-source-sync-ready-every-15-minutes",
                    "task": "data_source.sync_ready_connections",
                    "schedule": {
                        "type": "interval",
                        "seconds": 900,
                    },
                    "kwargs": {
                        "limit": 50,
                    },
                },
                {
                    "name": "health-sync-ready-energy-hourly",
                    "task": "health.sync_ready_energy_connections",
                    "schedule": {
                        "type": "interval",
                        "seconds": 3600,
                    },
                    "kwargs": {
                        "limit": 50,
                    },
                },
            ],
            "excluded_entries": [
                {
                    "task_name": "data_source.sync_connection",
                    "reason": "Single-connection sync should be triggered explicitly for a selected connection.",
                },
                {
                    "task_name": "health.sync_energy_connection",
                    "reason": "Single health sync should be triggered explicitly for a selected connection.",
                },
            ],
            "notes": [
                "This is a JSON-friendly Celery Beat proposal, not a running scheduler.",
                "Interval entries are expressed in seconds.",
                "Single-connection workers remain excluded from automatic Beat fanout.",
            ],
        }

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
                    "task_name": "reminder.generate_execution_for_active_users",
                    "cadence": "hourly_morning_window",
                    "schedule_hint": "Fan out over active users and skip users without active Today plans.",
                    "scope": "per_user_with_active_today_plan",
                    "enabled": True,
                    "payload_template": {
                        "plan_date": "<today>",
                        "max_users": 100,
                        "limit": None,
                        "start_hour": None,
                        "spacing_minutes": None,
                    },
                    "guardrails": [
                        "Skips users without an existing Today active plan.",
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
                    "name": "reminder-generate-execution-fanout-hourly",
                    "task": "reminder.generate_execution_for_active_users",
                    "schedule": {
                        "type": "interval",
                        "seconds": 3600,
                    },
                    "kwargs": {
                        "plan_date": "<today>",
                        "max_users": 100,
                        "limit": None,
                        "start_hour": None,
                        "spacing_minutes": None,
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
                    "reason": "Use reminder.generate_execution_for_active_users for safe fanout.",
                }
            ],
            "notes": [
                "This is a JSON-friendly Celery Beat proposal, not a running scheduler.",
                "Crontab entries are expressed in UTC.",
                "Execution reminder fanout should be implemented as a separate worker before Beat wiring.",
            ],
        }

    def _overview_domain(
        self,
        *,
        domain: str,
        display_name: str,
        plan_path: str,
        beat_path: str,
        plan: dict,
        beat: dict,
    ) -> dict:
        entries = plan["entries"]
        beat_entries = beat["entries"]
        excluded_entries = beat.get("excluded_entries", [])
        return {
            "domain": domain,
            "display_name": display_name,
            "plan_path": plan_path,
            "beat_path": beat_path,
            "entry_count": len(entries),
            "enabled_entry_count": len([entry for entry in entries if entry["enabled"]]),
            "beat_entry_count": len(beat_entries),
            "excluded_entry_count": len(excluded_entries),
            "task_names": [entry["task_name"] for entry in entries],
            "beat_task_names": [entry["task"] for entry in beat_entries],
            "excluded_task_names": [entry["task_name"] for entry in excluded_entries],
            "guardrail_count": sum(len(entry["guardrails"]) for entry in entries),
        }


scheduler_service = SchedulerService()
