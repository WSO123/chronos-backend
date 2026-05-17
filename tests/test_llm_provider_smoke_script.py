import json
import subprocess
import sys
import unittest

from scripts import smoke_llm_provider
from app.core.config import settings


class LLMProviderSmokeScriptTests(unittest.TestCase):
    def test_script_skips_without_explicit_real_llm_flag(self):
        result = subprocess.run(
            [sys.executable, "scripts/smoke_llm_provider.py"],
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "skipped")
        self.assertIn("--allow-real-llm", payload["reason"])

    def test_validate_real_llm_config_requires_explicit_settings(self):
        original = {
            "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "LLM_MODEL": settings.LLM_MODEL,
            "LLM_API_KEY": settings.LLM_API_KEY,
            "LLM_ALLOWED_PROVIDERS": settings.LLM_ALLOWED_PROVIDERS,
            "LLM_ALLOWED_MODELS": settings.LLM_ALLOWED_MODELS,
            "LLM_MAX_OUTPUT_TOKENS": settings.LLM_MAX_OUTPUT_TOKENS,
        }
        try:
            settings.AI_ENABLE_REAL_LLM = False
            settings.LLM_PROVIDER = "openai"
            settings.LLM_MODEL = "gpt-4.1-mini"
            settings.LLM_API_KEY = "test"
            settings.LLM_ALLOWED_PROVIDERS = "openai,openai-compatible"
            settings.LLM_ALLOWED_MODELS = "gpt-4.1-mini"
            settings.LLM_MAX_OUTPUT_TOKENS = 800
            with self.assertRaisesRegex(RuntimeError, "AI_ENABLE_REAL_LLM"):
                smoke_llm_provider._validate_real_llm_config()

            settings.AI_ENABLE_REAL_LLM = True
            settings.LLM_PROVIDER = "mock"
            with self.assertRaisesRegex(RuntimeError, "LLM_PROVIDER"):
                smoke_llm_provider._validate_real_llm_config()

            settings.LLM_PROVIDER = "openai"
            settings.LLM_API_KEY = None
            with self.assertRaisesRegex(RuntimeError, "LLM_API_KEY"):
                smoke_llm_provider._validate_real_llm_config()

            settings.LLM_API_KEY = "test"
            settings.LLM_MODEL = "structured-mock-v1"
            with self.assertRaisesRegex(RuntimeError, "LLM_MODEL"):
                smoke_llm_provider._validate_real_llm_config()

            settings.LLM_MODEL = "expensive-model"
            with self.assertRaisesRegex(RuntimeError, "LLM_ALLOWED_MODELS"):
                smoke_llm_provider._validate_real_llm_config()

            settings.LLM_MODEL = "gpt-4.1-mini"
            settings.LLM_MAX_OUTPUT_TOKENS = 0
            with self.assertRaisesRegex(RuntimeError, "LLM_MAX_OUTPUT_TOKENS"):
                smoke_llm_provider._validate_real_llm_config()
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_PROVIDER = original["LLM_PROVIDER"]
            settings.LLM_MODEL = original["LLM_MODEL"]
            settings.LLM_API_KEY = original["LLM_API_KEY"]
            settings.LLM_ALLOWED_PROVIDERS = original["LLM_ALLOWED_PROVIDERS"]
            settings.LLM_ALLOWED_MODELS = original["LLM_ALLOWED_MODELS"]
            settings.LLM_MAX_OUTPUT_TOKENS = original["LLM_MAX_OUTPUT_TOKENS"]

    def test_task_id_preservation_summary_accepts_exact_match(self):
        summary = smoke_llm_provider.task_id_preservation_summary(
            expected=["task-1", "task-2"],
            actual=["task-1", "task-2"],
        )

        self.assertTrue(summary["task_ids_preserved"])
        self.assertTrue(summary["task_id_set_preserved"])
        self.assertTrue(summary["task_count_preserved"])
        self.assertEqual(summary["missing_task_ids"], [])
        self.assertEqual(summary["unexpected_task_ids"], [])

    def test_task_id_preservation_summary_reports_reorder_and_membership_changes(self):
        reordered = smoke_llm_provider.task_id_preservation_summary(
            expected=["task-1", "task-2"],
            actual=["task-2", "task-1"],
        )
        changed = smoke_llm_provider.task_id_preservation_summary(
            expected=["task-1", "task-2"],
            actual=["task-2", "task-3"],
        )

        self.assertFalse(reordered["task_ids_preserved"])
        self.assertTrue(reordered["task_id_set_preserved"])
        self.assertTrue(reordered["task_count_preserved"])
        self.assertFalse(changed["task_ids_preserved"])
        self.assertFalse(changed["task_id_set_preserved"])
        self.assertEqual(changed["missing_task_ids"], ["task-1"])
        self.assertEqual(changed["unexpected_task_ids"], ["task-3"])


if __name__ == "__main__":
    unittest.main()
