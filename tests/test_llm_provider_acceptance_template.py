from pathlib import Path
import unittest


class LLMProviderAcceptanceTemplateTests(unittest.TestCase):
    def test_template_includes_required_acceptance_fields(self):
        template = Path("docs/llm-provider-acceptance/TEMPLATE.md").read_text(encoding="utf-8")

        required_terms = [
            "Provider",
            "Model",
            "Base URL",
            "Prompt version",
            "Prompt checksum",
            "Structured schema",
            "LLM_MAX_OUTPUT_TOKENS=800",
            "LLM_API_KEY=<redacted>",
            "scripts/smoke_llm_provider.py --allow-real-llm",
            "scripts/compare_planner_eval_jsonl.py",
            "scripts/check_planner_eval_policy.py",
            "scripts/generate_llm_acceptance_record.py",
            "Input tokens",
            "Output tokens",
            "Total tokens",
            "expected_task_ids",
            "output_task_ids",
            "task_ids_preserved",
            "task_id_set_preserved",
            "Task ids preserved",
            "Provider response id",
            "Fallback",
            "Accepted",
            "Rejected",
            "Blocked",
        ]

        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, template)

    def test_readme_documents_secret_boundaries(self):
        readme = Path("docs/llm-provider-acceptance/README.md").read_text(encoding="utf-8")

        self.assertIn("不要提交 API key", readme)
        self.assertIn("LLM_API_KEY", readme)
        self.assertIn("<redacted>", readme)
        self.assertIn("真实 provider 验收只能使用 synthetic / demo 输入", readme)


if __name__ == "__main__":
    unittest.main()
