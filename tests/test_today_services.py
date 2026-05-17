import unittest
from datetime import date, timedelta
from types import SimpleNamespace
import uuid

from app.ai.schemas.planning import DailyPlannerOutput
from app.core.config import settings
from app.models.activity_event import ActivityEvent
from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus, AIJobType, DailyPlanItemStatus, EntityType, TaskStatus, ValueLevel
from app.models.task import Task
from app.services.energy_service import energy_service
from app.services.planning_service import PlanningService, planning_service
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
        self.assertGreater(today["sections"]["pinned_tasks"][0]["score_breakdown"]["total_score"], 0)
        self.assertEqual(today["sections"]["pinned_tasks"][0]["score_breakdown"]["selected_for_today"], True)
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
        self.assertEqual(strategy["factors"]["daily_capacity_minutes"], 150)
        self.assertEqual(strategy["factors"]["selected_estimated_minutes"], 65)
        self.assertEqual(strategy["factors"]["over_capacity_minutes"], 0)
        self.assertEqual(strategy["factors"]["capacity_status"], "within_capacity")
        self.assertEqual(strategy["factors"]["energy_applied"], False)
        self.assertIsNotNone(strategy["factors"]["planner_agent_latency_ms"])
        self.assertEqual(strategy["factors"]["planner_agent_failure_type"], None)
        self.assertEqual(len(strategy["task_rationales"]), 2)
        self.assertEqual(strategy["task_rationales"][0]["title"], "Protect strategy task")
        self.assertIn("value_score", strategy["task_rationales"][0]["score_breakdown"])
        self.assertTrue(strategy["explanation"])
        self.assertEqual(strategy["source"]["model_name"], "planning-engine-v1")
        self.assertIsNotNone(strategy["source"]["ai_job_id"])
        planner_job = self.db.get(AIJob, uuid.UUID(strategy["source"]["ai_job_id"]))
        self.assertIsNotNone(planner_job)
        self.assertEqual(planner_job.job_type, AIJobType.DAILY_PLANNER)
        self.assertEqual(planner_job.status, AIJobStatus.SUCCEEDED)
        self.assertEqual(planner_job.provider, "mock")
        self.assertEqual(planner_job.result_entity_id, strategy["daily_plan_id"])
        self.assertEqual(planner_job.job_metadata["output_applied"], True)
        self.assertEqual(planner_job.prompt_version, "p2-daily-planner-agent-v1")
        self.assertEqual(len(planner_job.job_metadata["prompt_checksum"]), 64)
        self.assertIsNotNone(planner_job.latency_ms)
        self.assertGreaterEqual(planner_job.latency_ms, 0)
        self.assertEqual(planner_job.job_metadata["provider_latency_ms"], planner_job.latency_ms)
        self.assertEqual(planner_job.job_metadata["provider_observability_version"], "v1")
        self.assertEqual(planner_job.job_metadata["usage"]["total_tokens"], None)
        self.assertEqual(planner_job.job_metadata["usage"]["cost_usd"], None)

    def test_daily_planner_agent_failure_falls_back_to_planning_engine(self):
        class FailingPlannerAgent:
            prompt_version = "test-failing-planner"

            def run(self, **kwargs):
                raise RuntimeError("planner unavailable")

        service = PlanningService(planner_agent=FailingPlannerAgent())
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Fallback protected task",
            estimated_duration_min=30,
            priority=1,
            value_level=ValueLevel.HIGH,
        )

        strategy = service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(strategy["task_rationales"][0]["title"], "Fallback protected task")
        planner_job = self.db.get(AIJob, uuid.UUID(strategy["source"]["ai_job_id"]))
        self.assertEqual(planner_job.status, AIJobStatus.SUCCEEDED_WITH_FALLBACK)
        self.assertEqual(planner_job.job_metadata["output_applied"], False)
        self.assertEqual(planner_job.job_metadata["fallback_reason"], "daily_planner_agent_failed")
        self.assertEqual(planner_job.job_metadata["fallback_error_type"], "RuntimeError")
        self.assertEqual(planner_job.job_metadata["fallback_root_error_type"], "RuntimeError")
        self.assertEqual(planner_job.job_metadata["failure_type"], "agent_error")
        self.assertIsNotNone(planner_job.latency_ms)
        self.assertEqual(strategy["factors"]["planner_agent_failure_type"], "agent_error")

    def test_daily_planner_agent_invalid_output_falls_back_to_planning_engine(self):
        class InvalidPlannerAgent:
            prompt_version = "test-invalid-planner"

            def run(self, **kwargs):
                candidates = kwargs["candidates"]
                strategy_seed = kwargs["strategy_seed"]
                return SimpleNamespace(
                    output=DailyPlannerOutput(
                        mode=strategy_seed["mode"],
                        strategy_summary=strategy_seed["summary"],
                        primary_reason=strategy_seed["primary_reason"],
                        items=[
                            {
                                "task_id": candidate["task_id"],
                                "section": candidate["section"],
                                "sort_order": candidate["sort_order"],
                                "recommendation_reason": candidate["recommendation_reason"],
                            }
                            for candidate in candidates
                        ]
                        + [
                            {
                                "task_id": candidates[0]["task_id"],
                                "section": candidates[0]["section"],
                                "sort_order": candidates[0]["sort_order"],
                                "recommendation_reason": candidates[0]["recommendation_reason"],
                            }
                        ],
                        confidence=0.3,
                    ),
                    provider="test",
                    model="test-model",
                    prompt_version="test-invalid-planner",
                )

        service = PlanningService(planner_agent=InvalidPlannerAgent())
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Invalid output fallback task",
            estimated_duration_min=30,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Second invalid output fallback task",
            estimated_duration_min=20,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        strategy = service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(strategy["task_rationales"][0]["title"], "Invalid output fallback task")
        planner_job = self.db.get(AIJob, uuid.UUID(strategy["source"]["ai_job_id"]))
        self.assertEqual(planner_job.status, AIJobStatus.SUCCEEDED_WITH_FALLBACK)
        self.assertEqual(planner_job.provider, "test")
        self.assertEqual(planner_job.job_metadata["output_applied"], False)
        self.assertEqual(planner_job.job_metadata["fallback_reason"], "daily_planner_agent_invalid_output")
        self.assertEqual(planner_job.job_metadata["fallback_error_type"], "ValueError")
        self.assertEqual(planner_job.job_metadata["fallback_root_error_type"], "ValueError")
        self.assertEqual(planner_job.job_metadata["failure_type"], "invalid_output")
        self.assertEqual(strategy["factors"]["planner_agent_failure_type"], "invalid_output")

    def test_real_llm_provider_failure_records_provider_and_falls_back(self):
        original = {
            "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "LLM_MODEL": settings.LLM_MODEL,
            "LLM_API_KEY": settings.LLM_API_KEY,
        }
        try:
            settings.AI_ENABLE_REAL_LLM = True
            settings.LLM_PROVIDER = "openai"
            settings.LLM_MODEL = "gpt-test"
            settings.LLM_API_KEY = None
            task_service.create_task(
                self.db,
                user_id=self.user.id,
                title="Real provider fallback task",
                estimated_duration_min=30,
                priority=1,
                value_level=ValueLevel.HIGH,
            )

            strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

            planner_job = self.db.get(AIJob, uuid.UUID(strategy["source"]["ai_job_id"]))
            self.assertEqual(planner_job.status, AIJobStatus.SUCCEEDED_WITH_FALLBACK)
            self.assertEqual(planner_job.provider, "openai")
            self.assertEqual(planner_job.model, "gpt-test")
            self.assertEqual(planner_job.job_metadata["output_applied"], False)
            self.assertEqual(planner_job.job_metadata["fallback_reason"], "daily_planner_agent_failed")
            self.assertEqual(planner_job.job_metadata["failure_type"], "provider_error")
            self.assertEqual(planner_job.job_metadata["fallback_root_error_type"], "LLMProviderError")
            self.assertEqual(planner_job.job_metadata["provider_latency_ms"], planner_job.latency_ms)
            self.assertEqual(strategy["factors"]["planner_agent_failure_type"], "provider_error")
            self.assertIn("LLM_API_KEY", planner_job.error_message)
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_PROVIDER = original["LLM_PROVIDER"]
            settings.LLM_MODEL = original["LLM_MODEL"]
            settings.LLM_API_KEY = original["LLM_API_KEY"]

    def test_planning_engine_rolls_over_work_beyond_today_capacity(self):
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Protected deep work",
            estimated_duration_min=90,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        medium_tasks = []
        for index in range(3):
            medium_tasks.append(
                task_service.create_task(
                    self.db,
                    user_id=self.user.id,
                    title=f"Medium task {index}",
                    estimated_duration_min=60,
                    priority=3,
                    value_level=ValueLevel.MEDIUM,
                )
            )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(today["progress"]["total_count"], 2)
        self.assertEqual(len(today["sections"]["rolled_over_tasks"]), 2)
        rolled = today["sections"]["rolled_over_tasks"][0]
        self.assertEqual(rolled["item_status"], DailyPlanItemStatus.PLANNED)
        self.assertEqual(rolled["task_status"], TaskStatus.ACTIVE)
        self.assertEqual(self.db.get(Task, medium_tasks[-1].id).status, TaskStatus.ACTIVE)
        self.assertEqual(rolled["score_breakdown"]["selected_for_today"], False)
        self.assertEqual(rolled["score_breakdown"]["rollover_reason"], "capacity")
        self.assertEqual(strategy["factors"]["daily_capacity_minutes"], 150)
        self.assertEqual(strategy["factors"]["selected_estimated_minutes"], 150)
        self.assertEqual(strategy["factors"]["rolled_over_estimated_minutes"], 120)
        self.assertEqual(strategy["factors"]["over_capacity_minutes"], 0)
        self.assertEqual(strategy["factors"]["capacity_status"], "within_capacity")

    def test_planning_engine_warns_when_protected_work_exceeds_capacity(self):
        for index in range(3):
            task_service.create_task(
                self.db,
                user_id=self.user.id,
                title=f"Protected overload task {index}",
                estimated_duration_min=70,
                priority=1,
                value_level=ValueLevel.HIGH,
            )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(today["progress"]["total_count"], 3)
        self.assertFalse(today["sections"]["rolled_over_tasks"])
        self.assertEqual(today["insights_preview"]["risk_alerts"][0]["key"], "main_sequence_over_capacity")
        self.assertEqual(strategy["factors"]["daily_capacity_minutes"], 150)
        self.assertEqual(strategy["factors"]["selected_estimated_minutes"], 210)
        self.assertEqual(strategy["factors"]["over_capacity_minutes"], 60)
        self.assertEqual(strategy["factors"]["capacity_status"], "overloaded")
        self.assertIn("超过容量", strategy["explanation"][1])

    def test_planning_engine_keeps_user_postponed_tasks_out_of_main_sequence(self):
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Already postponed task",
            estimated_duration_min=30,
            priority=2,
            value_level=ValueLevel.HIGH,
        )
        task_service.postpone_task(self.db, task_id=task.id, user_id=self.user.id)

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(today["progress"]["total_count"], 0)
        rolled = today["sections"]["rolled_over_tasks"][0]
        self.assertEqual(rolled["task_id"], task.id)
        self.assertEqual(rolled["item_status"], DailyPlanItemStatus.POSTPONED)
        self.assertEqual(rolled["task_status"], TaskStatus.POSTPONED)
        self.assertEqual(rolled["score_breakdown"]["rollover_reason"], "postponed")

    def test_planning_engine_behavior_feedback_penalizes_repeated_interruptions(self):
        stable_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Stable task",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        interrupted_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Frequently interrupted task",
            estimated_duration_min=30,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        self.db.add_all(
            [
                ActivityEvent(
                    user_id=self.user.id,
                    entity_type=EntityType.TASK,
                    entity_id=interrupted_task.id,
                    event_type="FOCUS_SESSION_INTERRUPTED",
                    related_task_id=interrupted_task.id,
                ),
                ActivityEvent(
                    user_id=self.user.id,
                    entity_type=EntityType.TASK,
                    entity_id=interrupted_task.id,
                    event_type="FOCUS_SESSION_INTERRUPTED",
                    related_task_id=interrupted_task.id,
                ),
            ]
        )
        self.db.commit()

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        recommended = today["sections"]["recommended_tasks"]

        self.assertEqual(recommended[0]["task_id"], stable_task.id)
        self.assertEqual(recommended[1]["task_id"], interrupted_task.id)
        self.assertLess(recommended[1]["score_breakdown"]["behavior_feedback_score"], 0)

    def test_planning_engine_high_energy_prioritizes_deeper_work_without_expanding_capacity(self):
        energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={"metric_date": self.plan_date, "energy_score": 90},
        )
        small_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Small shallow task",
            estimated_duration_min=20,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        deep_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Deep high-energy task",
            estimated_duration_min=60,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        first_item = today["sections"]["recommended_tasks"][0]
        self.assertEqual(first_item["task_id"], deep_task.id)
        self.assertEqual(today["sections"]["recommended_tasks"][1]["task_id"], small_task.id)
        self.assertGreater(first_item["score_breakdown"]["energy_fit_score"], 0)
        self.assertEqual(strategy["factors"]["daily_capacity_minutes"], 150)
        self.assertEqual(strategy["factors"]["selected_estimated_minutes"], 80)
        self.assertEqual(strategy["factors"]["energy_applied"], True)

    def test_planning_engine_applies_low_energy_to_capacity_and_score(self):
        energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={"metric_date": self.plan_date, "energy_score": 35},
        )
        light_task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Small admin step",
            estimated_duration_min=20,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )
        task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Long writing block",
            estimated_duration_min=75,
            priority=3,
            value_level=ValueLevel.MEDIUM,
        )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        first_item = today["sections"]["recommended_tasks"][0]
        self.assertEqual(first_item["task_id"], light_task.id)
        self.assertGreater(first_item["score_breakdown"]["energy_fit_score"], 0)
        self.assertEqual(first_item["score_breakdown"]["energy_applied"], True)
        self.assertEqual(strategy["factors"]["daily_capacity_minutes"], 90)
        self.assertEqual(strategy["factors"]["energy_level"], "low")
        self.assertEqual(strategy["energy"]["applied_to_plan"], True)

    def test_today_planner_orders_prerequisites_before_dependent_tasks(self):
        prerequisite = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Draft source outline",
            estimated_duration_min=30,
            priority=4,
            value_level=ValueLevel.LOW,
        )
        dependent = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Write final proposal",
            estimated_duration_min=60,
            priority=1,
            value_level=ValueLevel.HIGH,
        )
        task_service.add_task_dependency(
            self.db,
            task_id=dependent.id,
            user_id=self.user.id,
            prerequisite_task_id=prerequisite.id,
            reason="Proposal needs the outline first",
        )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)
        ordered_titles = [item["title"] for item in today["sections"]["pinned_tasks"]]

        self.assertEqual(ordered_titles[:2], ["Draft source outline", "Write final proposal"])
        self.assertEqual(today["sections"]["pinned_tasks"][0]["task_id"], prerequisite.id)
        self.assertIn("unlocks another planned task", today["sections"]["pinned_tasks"][0]["recommendation_reason"])
        self.assertIn("after its prerequisite", today["sections"]["pinned_tasks"][1]["recommendation_reason"])
        self.assertEqual(strategy["factors"]["dependency_protected_count"], 1)

    def test_today_planner_uses_user_priority_adjustment_signal(self):
        task = task_service.create_task(
            self.db,
            user_id=self.user.id,
            title="Promote important follow-up",
            estimated_duration_min=35,
            priority=5,
            value_level=ValueLevel.LOW,
        )
        task_service.adjust_task_priority(
            self.db,
            task_id=task.id,
            user_id=self.user.id,
            priority=1,
            value_level=ValueLevel.HIGH,
            reason="This became important today",
        )

        today = planning_service.get_today(self.db, user_id=self.user.id, plan_date=self.plan_date)
        strategy = planning_service.get_strategy_detail(self.db, user_id=self.user.id, plan_date=self.plan_date)

        self.assertEqual(today["sections"]["pinned_tasks"][0]["task_id"], task.id)
        self.assertIn("Adjusted by you", today["sections"]["pinned_tasks"][0]["recommendation_reason"])
        self.assertEqual(strategy["factors"]["user_adjusted_count"], 1)

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
