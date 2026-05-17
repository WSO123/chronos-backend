import unittest

from scripts.smoke_daily_planner_fallback import fallback_evidence_payload


class DailyPlannerFallbackSmokeScriptTests(unittest.TestCase):
    def test_fallback_evidence_payload_accepts_provider_error_fallback(self):
        payload = fallback_evidence_payload(
            user_id="user-1",
            task_id="task-1",
            strategy=_strategy(),
            ai_job=_ai_job(),
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scenario"], "daily_planner_provider_failure")
        self.assertEqual(payload["fallback_verified"], True)
        self.assertEqual(payload["planning_engine_used"], True)
        self.assertEqual(payload["planner_agent_status"], "succeeded_with_fallback")
        self.assertEqual(payload["planner_agent_failure_type"], "provider_error")
        self.assertEqual(payload["planner_agent_output_applied"], False)

    def test_fallback_evidence_payload_rejects_applied_agent_output(self):
        ai_job = _ai_job()
        ai_job["job_metadata"] = {**ai_job["job_metadata"], "output_applied": True}

        payload = fallback_evidence_payload(
            user_id="user-1",
            task_id="task-1",
            strategy=_strategy(),
            ai_job=ai_job,
        )

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["fallback_verified"], False)


def _strategy() -> dict:
    return {
        "daily_plan_id": "daily-plan-1",
        "source": {
            "model_name": "planning-engine-v1",
        },
        "factors": {
            "planner_agent_failure_type": "provider_error",
        },
        "task_rationales": [
            {
                "title": "Fallback protected task",
            }
        ],
    }


def _ai_job() -> dict:
    return {
        "id": "ai-job-1",
        "status": "succeeded_with_fallback",
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "latency_ms": 5,
        "job_metadata": {
            "output_applied": False,
            "fallback_reason": "daily_planner_agent_failed",
            "failure_type": "provider_error",
            "fallback_error_type": "LLMProviderError",
            "fallback_root_error_type": "LLMProviderError",
            "provider_observability_version": "v1",
        },
    }


if __name__ == "__main__":
    unittest.main()
