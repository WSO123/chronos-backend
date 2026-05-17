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
        }
        try:
            settings.AI_ENABLE_REAL_LLM = False
            settings.LLM_PROVIDER = "openai"
            settings.LLM_MODEL = "gpt-test"
            settings.LLM_API_KEY = "test"
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
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_PROVIDER = original["LLM_PROVIDER"]
            settings.LLM_MODEL = original["LLM_MODEL"]
            settings.LLM_API_KEY = original["LLM_API_KEY"]


if __name__ == "__main__":
    unittest.main()
