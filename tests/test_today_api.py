import unittest
from datetime import date

from fastapi.testclient import TestClient

from app.core.db import get_db
from main import app
from app.services.energy_service import energy_service
from tests.db import TestingSessionLocal, override_get_db, reset_database
from tests.factories import create_user


class TodayAPITests(unittest.TestCase):
    def setUp(self):
        reset_database()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        self.user = create_user(self.db, name="Alice")
        self.other_user = create_user(self.db, name="Bob")
        self.headers = {"X-User-Id": str(self.user.id)}
        self.other_headers = {"X-User-Id": str(self.other_user.id)}

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_get_today_lazy_creates_plan(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Do the important thing", "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)

        response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-05-16")
        self.assertEqual(body["plan_version"], 1)
        self.assertEqual(body["sections"]["pinned_tasks"][0]["title"], "Do the important thing")
        self.assertEqual(body["insights_preview"]["source"], "rule-today-insights-v1")
        self.assertEqual(body["insights_preview"]["remaining_time_suggestion"]["key"], "remaining_time")
        self.assertEqual(body["quick_actions"]["can_replan"], True)

    def test_get_strategy_detail_uses_current_user_only(self):
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Private strategy task", "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        other_task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Other strategy task", "priority": 1, "value_level": "high"},
            headers=self.other_headers,
        )
        self.assertEqual(task_response.status_code, 201)
        self.assertEqual(other_task_response.status_code, 201)

        response = self.client.get("/api/v1/today/strategy?plan_date=2026-05-16", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-05-16")
        self.assertEqual(body["plan_version"], 1)
        self.assertEqual(body["factors"]["task_count"], 1)
        self.assertEqual(body["factors"]["dependency_protected_count"], 0)
        self.assertEqual(body["factors"]["user_adjusted_count"], 0)
        self.assertEqual(body["factors"]["capacity_status"], "within_capacity")
        self.assertEqual(body["factors"]["over_capacity_minutes"], 0)
        self.assertIsNotNone(body["factors"]["planner_agent_latency_ms"])
        self.assertIsNone(body["factors"]["planner_agent_failure_type"])
        self.assertEqual(body["score_explanation"]["source"], "planning-engine-score-breakdown-v1")
        self.assertTrue(body["score_explanation"]["signals"])
        self.assertEqual(body["task_rationales"][0]["title"], "Private strategy task")
        self.assertTrue(body["task_rationales"][0]["dominant_factor"])
        self.assertTrue(body["task_rationales"][0]["dominant_reason"])
        self.assertTrue(body["task_rationales"][0]["score_signals"])
        self.assertNotIn("Other strategy task", {item["title"] for item in body["task_rationales"]})
        self.assertTrue(body["explanation"])
        self.assertEqual(body["energy"]["has_data"], False)
        self.assertEqual(body["energy"]["applied_to_plan"], False)
        self.assertEqual(body["energy"]["source"], "none")
        self.assertEqual(body["planner_review"]["source"], "daily_planner_agent_v1")
        self.assertTrue(body["planner_review"]["summary"])
        self.assertEqual(body["planner_review"]["suggestions"][0]["key"], "start_with_first_task")
        self.assertEqual(body["source"]["model_name"], "planning-engine-v1")
        self.assertIsNotNone(body["source"]["ai_job_id"])
        job_response = self.client.get(f"/api/v1/ai-jobs/{body['source']['ai_job_id']}", headers=self.headers)
        self.assertEqual(job_response.status_code, 200)
        self.assertEqual(job_response.json()["job_type"], "daily_planner")
        self.assertEqual(job_response.json()["status"], "succeeded")
        self.assertEqual(job_response.json()["provider"], "mock")
        self.assertEqual(job_response.json()["latency_ms"], body["factors"]["planner_agent_latency_ms"])
        self.assertEqual(job_response.json()["job_metadata"]["provider_observability_version"], "v1")

    def test_strategy_detail_returns_energy_explanation_with_planning_signal(self):
        energy_service.upsert_daily_metric(
            self.db,
            user_id=self.user.id,
            payload={"metric_date": date(2026, 5, 16), "energy_score": 88},
        )
        task_response = self.client.post(
            "/api/v1/tasks",
            json={"title": "Energy-aware but stable task", "priority": 1, "value_level": "high"},
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)

        response = self.client.get("/api/v1/today/strategy?plan_date=2026-05-16", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["energy"]["has_data"], True)
        self.assertEqual(body["energy"]["energy_level"], "high")
        self.assertEqual(body["energy"]["recommended_mode"], "deep_work")
        self.assertEqual(body["energy"]["source"], "energy_daily_metric")
        self.assertEqual(body["energy"]["applied_to_plan"], True)
        self.assertIn("Planning Engine", body["energy"]["explanation"])
        self.assertEqual(body["factors"]["energy_applied"], True)
        self.assertEqual(body["task_rationales"][0]["title"], "Energy-aware but stable task")
        self.assertEqual(body["task_rationales"][0]["score_breakdown"]["energy_applied"], True)

    def test_prepare_today_planning_signals_generates_missing_signals_and_replans(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Semantic Today Goal", "value_level": "high"},
            headers=self.headers,
        )
        task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "写一个能推进目标的今日方案",
                "goal_id": goal_response.json()["id"],
                "priority": 4,
                "value_level": "medium",
            },
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)

        response = self.client.post(
            "/api/v1/today/planning-signals?plan_date=2026-05-16",
            headers=self.headers,
        )
        body = response.json()
        today_item = body["today"]["sections"]["pinned_tasks"][0]
        second_response = self.client.post(
            "/api/v1/today/planning-signals?plan_date=2026-05-16",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["task_count"], 1)
        self.assertEqual(body["generated_count"], 1)
        self.assertEqual(body["existing_count"], 0)
        self.assertEqual(body["stale_count"], 0)
        self.assertEqual(body["replanned"], True)
        self.assertEqual(body["today"]["plan_version"], 2)
        self.assertEqual(today_item["task_id"], task_response.json()["id"])
        self.assertTrue(today_item["score_breakdown"]["semantic_signal_applied"])
        self.assertEqual(len(body["planning_signal_ids"]), 1)
        self.assertEqual(len(body["ai_job_ids"]), 1)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["generated_count"], 0)
        self.assertEqual(second_response.json()["existing_count"], 1)
        self.assertEqual(second_response.json()["stale_count"], 0)
        self.assertEqual(second_response.json()["replanned"], False)
        self.assertEqual(second_response.json()["today"]["plan_version"], 2)

    def test_prepare_today_planning_signals_refreshes_stale_signal_after_task_edit(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "Signal Refresh Goal", "value_level": "high"},
            headers=self.headers,
        )
        task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "写一个今日推进方案",
                "goal_id": goal_response.json()["id"],
                "priority": 4,
                "value_level": "medium",
            },
            headers=self.headers,
        )
        task_id = task_response.json()["id"]
        first_response = self.client.post(
            "/api/v1/today/planning-signals?plan_date=2026-05-16",
            headers=self.headers,
        )
        update_response = self.client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"title": "写一个今日推进方案并补充验收标准"},
            headers=self.headers,
        )
        second_response = self.client.post(
            "/api/v1/today/planning-signals?plan_date=2026-05-16",
            headers=self.headers,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["generated_count"], 1)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        body = second_response.json()
        self.assertEqual(body["task_count"], 1)
        self.assertEqual(body["generated_count"], 1)
        self.assertEqual(body["existing_count"], 0)
        self.assertEqual(body["stale_count"], 1)
        self.assertEqual(body["replanned"], True)
        self.assertEqual(body["today"]["plan_version"], 3)
        self.assertEqual(body["today"]["sections"]["pinned_tasks"][0]["title"], "写一个今日推进方案并补充验收标准")

    def test_replan_and_complete_today_item(self):
        self.client.post("/api/v1/tasks", json={"title": "First task"}, headers=self.headers)
        today_response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        plan_id = today_response.json()["daily_plan_id"]
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        replan_response = self.client.post(
            "/api/v1/today/replan?plan_date=2026-05-16",
            json={"reason": "Check ordering"},
            headers=self.headers,
        )
        updated_item_id = replan_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]
        complete_response = self.client.patch(
            f"/api/v1/today/items/{updated_item_id}",
            json={"status": "completed"},
            headers=self.headers,
        )
        refreshed_today = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        old_item_response = self.client.patch(
            f"/api/v1/today/items/{item_id}",
            json={"status": "completed"},
            headers=self.headers,
        )

        self.assertEqual(replan_response.status_code, 200)
        self.assertEqual(replan_response.json()["daily_plan_id"], plan_id)
        self.assertEqual(replan_response.json()["plan_version"], 2)
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["item_status"], "completed")
        self.assertEqual(refreshed_today.json()["progress"]["completion_rate"], 1.0)
        self.assertEqual(old_item_response.status_code, 404)

    def test_replan_accepts_manual_available_minutes(self):
        for index in range(2):
            self.client.post(
                "/api/v1/tasks",
                json={
                    "title": f"Manual API capacity task {index}",
                    "estimated_duration_min": 60,
                    "priority": 3,
                    "value_level": "medium",
                },
                headers=self.headers,
            )
        self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)

        replan_response = self.client.post(
            "/api/v1/today/replan?plan_date=2026-05-16",
            json={"reason": "Short day", "available_minutes": 60},
            headers=self.headers,
        )
        strategy_response = self.client.get("/api/v1/today/strategy?plan_date=2026-05-16", headers=self.headers)
        invalid_response = self.client.post(
            "/api/v1/today/replan?plan_date=2026-05-16",
            json={"available_minutes": 5},
            headers=self.headers,
        )

        self.assertEqual(replan_response.status_code, 200)
        self.assertEqual(replan_response.json()["plan_version"], 2)
        self.assertEqual(strategy_response.status_code, 200)
        factors = strategy_response.json()["factors"]
        self.assertEqual(factors["daily_capacity_minutes"], 60)
        self.assertEqual(factors["capacity_source"], "manual_today_override")
        self.assertEqual(factors["manual_available_minutes"], 60)
        self.assertEqual(factors["selected_estimated_minutes"], 60)
        self.assertEqual(invalid_response.status_code, 422)

    def test_complete_today_item_returns_goal_progress_feedback(self):
        goal_response = self.client.post(
            "/api/v1/goals",
            json={"title": "推进核心目标", "value_level": "high"},
            headers=self.headers,
        )
        self.assertEqual(goal_response.status_code, 201)
        task_response = self.client.post(
            "/api/v1/tasks",
            json={
                "title": "完成目标关键任务",
                "goal_id": goal_response.json()["id"],
                "priority": 1,
                "value_level": "high",
            },
            headers=self.headers,
        )
        self.assertEqual(task_response.status_code, 201)
        today_response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        item_id = today_response.json()["sections"]["pinned_tasks"][0]["daily_plan_item_id"]

        response = self.client.patch(
            f"/api/v1/today/items/{item_id}",
            json={"status": "completed"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["item_status"], "completed")
        self.assertEqual(body["goal_progress_feedback"]["goal_id"], goal_response.json()["id"])
        self.assertEqual(body["goal_progress_feedback"]["task_id"], task_response.json()["id"])
        self.assertEqual(body["goal_progress_feedback"]["progress_before"], 0.0)
        self.assertEqual(body["goal_progress_feedback"]["progress_after"], 1.0)
        self.assertEqual(body["goal_progress_feedback"]["progress_delta"], 1.0)

    def test_user_id_isolation_for_today_item(self):
        self.client.post("/api/v1/tasks", json={"title": "Private today task"}, headers=self.headers)
        today_response = self.client.get("/api/v1/today?plan_date=2026-05-16", headers=self.headers)
        item_id = today_response.json()["sections"]["recommended_tasks"][0]["daily_plan_item_id"]

        response = self.client.patch(
            f"/api/v1/today/items/{item_id}",
            json={"status": "completed"},
            headers=self.other_headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
