import unittest

from scripts.smoke_core_ai_mainline import (
    EXPECTED_AI_JOB_TYPES,
    build_core_ai_evidence_payload,
    validate_ai_job_statuses,
)


class CoreAIMainlineSmokeScriptTests(unittest.TestCase):
    def test_validate_ai_job_statuses_accepts_success_and_controlled_fallback(self):
        ai_jobs = _ai_jobs(status="succeeded")
        ai_jobs["daily_report_generator"]["status"] = "succeeded_with_fallback"

        validate_ai_job_statuses(ai_jobs)

    def test_validate_ai_job_statuses_rejects_missing_job(self):
        ai_jobs = _ai_jobs(status="succeeded")
        ai_jobs["capture_parser"] = None

        with self.assertRaises(RuntimeError) as raised:
            validate_ai_job_statuses(ai_jobs)

        self.assertIn("capture_parser", str(raised.exception))

    def test_validate_ai_job_statuses_rejects_failed_job(self):
        ai_jobs = _ai_jobs(status="succeeded")
        ai_jobs["strategy_explanation"]["status"] = "failed"

        with self.assertRaises(RuntimeError) as raised:
            validate_ai_job_statuses(ai_jobs)

        self.assertIn("strategy_explanation", str(raised.exception))
        self.assertIn("failed", str(raised.exception))

    def test_build_core_ai_evidence_payload_is_structured_for_artifact_review(self):
        payload = build_core_ai_evidence_payload(
            user_id="user-1",
            capture_id="capture-1",
            inbox_item_id="inbox-1",
            task_id="task-1",
            daily_plan_id="plan-1",
            daily_plan_item_id="plan-item-1",
            focus_session_id="focus-1",
            daily_report_id="report-1",
            insight_anchor_date="2026-05-17",
            strategy_source={
                "ai_job_id": "daily-planner-job",
                "explanation_ai_job_id": "strategy-explanation-job",
            },
            planner_review={
                "source": "daily_planner_agent_v1",
                "suggestions": [{"key": "start_with_first_task"}],
            },
            ai_jobs=_ai_jobs(status="succeeded"),
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scenario"], "core_ai_mainline")
        self.assertEqual(payload["strategy"]["daily_planner_ai_job_id"], "daily-planner-job")
        self.assertEqual(payload["strategy"]["strategy_explanation_ai_job_id"], "strategy-explanation-job")
        self.assertEqual(payload["strategy"]["planner_review_source"], "daily_planner_agent_v1")
        self.assertEqual(payload["strategy"]["planner_suggestion_count"], 1)
        self.assertEqual(set(payload["ai_jobs"].keys()), set(EXPECTED_AI_JOB_TYPES))


def _ai_jobs(*, status: str) -> dict[str, dict | None]:
    return {
        job_type: {
            "id": f"{job_type}-job",
            "job_type": job_type,
            "status": status,
            "provider": "mock",
            "model": "mock-model",
            "prompt_version": "test",
            "latency_ms": 1,
            "fallback_reason": None,
            "failure_type": None,
        }
        for job_type in EXPECTED_AI_JOB_TYPES
    }


if __name__ == "__main__":
    unittest.main()
