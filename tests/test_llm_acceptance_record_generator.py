import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from scripts.generate_llm_acceptance_record import generate_acceptance_markdown, load_json_payload


class LLMProviderAcceptanceRecordGeneratorTests(unittest.TestCase):
    def test_generate_acceptance_record_accepts_clean_inputs_and_redacts_response_id(self):
        markdown = generate_acceptance_markdown(
            smoke=_smoke(status="ok", provider_response_id="resp_secret_123"),
            fallback=_fallback(status="ok"),
            compare=_compare(status="ok"),
            policy=_policy(status="ok"),
            purpose="daily-planner-smoke",
            owner="Codex",
            commit="abc123",
            iteration="docs/iterations/test.md",
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Accepted", markdown)
        self.assertIn("- [x] Accepted", markdown)
        self.assertIn("| Provider | `openai` |", markdown)
        self.assertIn("| Model | `gpt-4.1-mini` |", markdown)
        self.assertIn("<redacted-present>", markdown)
        self.assertNotIn("resp_secret_123", markdown)
        self.assertIn("scripts/check_planner_eval_policy.py", markdown)
        self.assertIn("| Task ids preserved | True |", markdown)
        self.assertIn("| Fallback verified | True |", markdown)
        self.assertIn("- [x] task ids 未被 provider 改写且顺序保持一致。", markdown)
        self.assertIn("- [x] task 集合未被 provider 增删。", markdown)
        self.assertIn("- [x] 失败时 Today 仍可走 Planning Engine fallback。", markdown)

    def test_generate_acceptance_record_marks_changed_as_notes(self):
        markdown = generate_acceptance_markdown(
            smoke=_smoke(status="ok"),
            fallback=_fallback(status="ok"),
            compare=_compare(status="changed", changed_count=2),
            policy=_policy(status="changed", change_count=1),
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Accepted with Notes", markdown)
        self.assertIn("- [x] Accepted with Notes", markdown)
        self.assertIn("changed", markdown)

    def test_generate_acceptance_record_rejects_regression(self):
        markdown = generate_acceptance_markdown(
            smoke={**_smoke(status="ok"), "error": "raw provider response should not appear"},
            fallback=_fallback(status="ok"),
            compare=_compare(status="regressed", regression_count=1),
            policy=_policy(status="ok"),
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Rejected", markdown)
        self.assertIn("- [x] Rejected", markdown)
        self.assertIn("Planner compare reported a regression", markdown)
        self.assertNotIn("raw provider response should not appear", markdown)

    def test_generate_acceptance_record_blocks_skipped_smoke(self):
        markdown = generate_acceptance_markdown(
            smoke={"status": "skipped", "reason": "safe default"},
            fallback=_fallback(status="ok"),
            compare=_compare(status="ok"),
            policy=_policy(status="ok"),
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Blocked", markdown)
        self.assertIn("- [x] Blocked", markdown)

    def test_generate_acceptance_record_surfaces_task_id_mismatch(self):
        smoke = {
            **_smoke(status="ok"),
            "task_ids_preserved": False,
            "task_id_set_preserved": False,
            "task_count_preserved": True,
            "missing_task_ids": ["manual-smoke-task-1"],
            "unexpected_task_ids": ["other-task"],
        }

        markdown = generate_acceptance_markdown(
            smoke=smoke,
            fallback=_fallback(status="ok"),
            compare=_compare(status="ok"),
            policy=_policy(status="ok"),
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Rejected", markdown)
        self.assertIn("| Task ids preserved | False |", markdown)
        self.assertIn("| Missing task ids | [\"manual-smoke-task-1\"] |", markdown)
        self.assertIn("| Unexpected task ids | [\"other-task\"] |", markdown)
        self.assertIn("- [ ] task ids 未被 provider 改写且顺序保持一致。", markdown)

    def test_generate_acceptance_record_blocks_missing_fallback_evidence(self):
        markdown = generate_acceptance_markdown(
            smoke=_smoke(status="ok"),
            compare=_compare(status="ok"),
            policy=_policy(status="ok"),
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Blocked", markdown)
        self.assertIn("Fallback smoke JSON is missing", markdown)
        self.assertIn("- [ ] 失败时 Today 仍可走 Planning Engine fallback。", markdown)

    def test_generate_acceptance_record_rejects_failed_fallback_evidence(self):
        fallback = {
            **_fallback(status="failed"),
            "fallback_verified": False,
            "planner_agent_status": "failed",
        }

        markdown = generate_acceptance_markdown(
            smoke=_smoke(status="ok"),
            fallback=fallback,
            compare=_compare(status="ok"),
            policy=_policy(status="ok"),
            record_date="2026-05-17",
        )

        self.assertIn("> 状态：Rejected", markdown)
        self.assertIn("Fallback smoke status is failed", markdown)
        self.assertIn("| Fallback verified | False |", markdown)

    def test_load_json_payload_extracts_json_from_command_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "output.txt"
            path.write_text("prefix\n{\"status\":\"ok\",\"value\":1}\n", encoding="utf-8")

            payload = load_json_payload(path)

        self.assertEqual(payload, {"status": "ok", "value": 1})

    def test_generate_acceptance_record_renders_empty_diff_details(self):
        markdown = generate_acceptance_markdown(
            smoke=_smoke(status="ok"),
            fallback=_fallback(status="ok"),
            compare=_compare(status="changed", changed_count=1),
            policy=_policy(status="ok"),
            record_date="2026-05-17",
        )

        self.assertIn("No detailed diff fields reported", markdown)

    def test_cli_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            smoke_path = tmp_path / "smoke.json"
            compare_path = tmp_path / "compare.json"
            fallback_path = tmp_path / "fallback.json"
            policy_path = tmp_path / "policy.json"
            output_path = tmp_path / "acceptance.md"
            smoke_path.write_text(json.dumps(_smoke(status="ok")), encoding="utf-8")
            fallback_path.write_text(json.dumps(_fallback(status="ok")), encoding="utf-8")
            compare_path.write_text(json.dumps(_compare(status="ok")), encoding="utf-8")
            policy_path.write_text(json.dumps(_policy(status="ok")), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_llm_acceptance_record.py",
                    "--smoke-json",
                    str(smoke_path),
                    "--fallback-json",
                    str(fallback_path),
                    "--compare-json",
                    str(compare_path),
                    "--policy-json",
                    str(policy_path),
                    "--output",
                    str(output_path),
                    "--date",
                    "2026-05-17",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertIn("> 状态：Accepted", output_path.read_text(encoding="utf-8"))


def _smoke(*, status: str, provider_response_id: str | None = "resp_123") -> dict:
    return {
        "status": status,
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "prompt_version": "p2-daily-planner-agent-v1",
        "prompt_checksum": "test-checksum",
        "latency_ms": 1200,
        "mode": "normal",
        "confidence": 0.8,
        "item_count": 2,
        "expected_task_ids": ["manual-smoke-task-1", "manual-smoke-task-2"],
        "output_task_ids": ["manual-smoke-task-1", "manual-smoke-task-2"],
        "task_ids_preserved": True,
        "task_id_set_preserved": True,
        "task_count_preserved": True,
        "missing_task_ids": [],
        "unexpected_task_ids": [],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.001,
        },
        "provider_response_id": provider_response_id,
    }


def _fallback(*, status: str) -> dict:
    return {
        "status": status,
        "scenario": "daily_planner_provider_failure",
        "fallback_verified": status == "ok",
        "today_available": status == "ok",
        "planning_engine_used": status == "ok",
        "daily_plan_id": "daily-plan-1",
        "ai_job_id": "ai-job-1",
        "planner_agent_status": "succeeded_with_fallback" if status == "ok" else "failed",
        "planner_agent_provider": "openai",
        "planner_agent_model": "gpt-4.1-mini",
        "planner_agent_failure_type": "provider_error",
        "planner_agent_output_applied": False,
        "fallback_reason": "daily_planner_agent_failed",
        "fallback_error_type": "LLMProviderError",
        "fallback_root_error_type": "LLMProviderError",
        "provider_observability_version": "v1",
        "latency_ms": 5,
        "task_count": 1,
        "task_titles": ["Fallback protected task"],
    }


def _compare(*, status: str, regression_count: int = 0, changed_count: int = 0) -> dict:
    return {
        "comparison_version": "p2-planner-eval-compare-v1",
        "status": status,
        "baseline": {"run_id": "baseline"},
        "candidate": {"run_id": "candidate"},
        "missing_in_candidate": [],
        "added_in_candidate": [],
        "regression_count": regression_count,
        "improvement_count": 0,
        "changed_count": changed_count,
        "regressions": ["scenario"] if regression_count else [],
        "improvements": [],
        "scenario_diffs": [] if not changed_count else [{"scenario_name": "scenario", "field_changes": []}],
    }


def _policy(*, status: str, regression_count: int = 0, change_count: int = 0) -> dict:
    return {
        "check_version": "p2-planner-eval-policy-check-v1",
        "status": status,
        "policy": {
            "policy_version": "p2-planner-eval-policy-v3",
            "evaluator_version": "p2-planning-engine-eval-v6",
            "required_scenario_count": 11,
        },
        "eval_run": {
            "run_id": "candidate",
            "evaluator_version": "p2-planning-engine-eval-v6",
            "scenario_count": 11,
        },
        "regression_count": regression_count,
        "change_count": change_count,
        "regression_issues": [],
        "change_issues": [],
    }


if __name__ == "__main__":
    unittest.main()
