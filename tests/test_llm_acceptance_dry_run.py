import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from scripts.generate_llm_acceptance_dry_run import build_dry_run_payloads, generate_dry_run


class LLMProviderAcceptanceDryRunTests(unittest.TestCase):
    def test_build_dry_run_payloads_are_acceptance_ready(self):
        payloads = build_dry_run_payloads()

        self.assertEqual(set(payloads), {"smoke", "fallback", "compare", "policy"})
        self.assertEqual(payloads["smoke"]["status"], "ok")
        self.assertEqual(payloads["smoke"]["task_ids_preserved"], True)
        self.assertEqual(payloads["fallback"]["fallback_verified"], True)
        self.assertEqual(payloads["fallback"]["planner_agent_status"], "succeeded_with_fallback")
        self.assertEqual(payloads["compare"]["status"], "ok")
        self.assertEqual(payloads["policy"]["status"], "ok")

    def test_generate_dry_run_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            result = generate_dry_run(
                json_dir=tmp_path / "json",
                output=tmp_path / "acceptance.md",
                record_date="2026-05-17",
            )

            self.assertEqual(result["status"], "ok")
            markdown = Path(result["output"]).read_text(encoding="utf-8")
            self.assertIn("> 状态：Accepted", markdown)
            self.assertIn("daily-planner-provider-acceptance-dry-run", markdown)
            self.assertIn("| Fallback verified | True |", markdown)
            self.assertIn("<redacted-present>", markdown)
            self.assertNotIn("dry-run-response-id", markdown)
            self.assertEqual(json.loads(Path(result["smoke_json"]).read_text(encoding="utf-8"))["status"], "ok")
            self.assertEqual(
                json.loads(Path(result["fallback_json"]).read_text(encoding="utf-8"))["fallback_verified"],
                True,
            )

    def test_cli_generates_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_llm_acceptance_dry_run.py",
                    "--json-dir",
                    str(tmp_path / "json"),
                    "--output",
                    str(tmp_path / "acceptance.md"),
                    "--date",
                    "2026-05-17",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(Path(payload["output"]).exists())


if __name__ == "__main__":
    unittest.main()
