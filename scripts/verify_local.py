from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import time


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class VerificationStep:
    name: str
    command: list[str]


def main() -> None:
    args = _parse_args()
    steps = _build_steps(args)

    print(f"Chronos local verification: {len(steps)} steps", flush=True)
    for index, step in enumerate(steps, start=1):
        _run_step(index=index, total=len(steps), step=step)
    print("Chronos local verification passed.", flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Chronos local verification ladder.")
    parser.add_argument(
        "--alembic",
        action="store_true",
        help="Run alembic upgrade head before tests. Use when migrations or models changed.",
    )
    parser.add_argument(
        "--smoke",
        action="append",
        choices=("p1", "p2", "p3", "llm-fallback"),
        default=[],
        help="Run a smoke script after the base checks. Can be repeated.",
    )
    parser.add_argument(
        "--all-smoke",
        action="store_true",
        help="Run P1, P2, and P3 smoke scripts after the base checks.",
    )
    parser.add_argument(
        "--planner-eval",
        action="store_true",
        help="Run deterministic Planning Engine evaluation scenarios.",
    )
    parser.add_argument(
        "--planner-eval-policy",
        action="store_true",
        help="Run Planning Engine evaluation JSONL and check it against the golden baseline policy.",
    )
    return parser.parse_args()


def _build_steps(args: argparse.Namespace) -> list[VerificationStep]:
    steps: list[VerificationStep] = []
    if args.alembic:
        steps.append(VerificationStep("alembic upgrade head", ["alembic", "upgrade", "head"]))

    steps.extend(
        [
            VerificationStep("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]),
            VerificationStep(
                "compile app tests scripts",
                [sys.executable, "-m", "compileall", "app", "tests", "scripts"],
            ),
            VerificationStep("diff whitespace check", ["git", "diff", "--check"]),
        ]
    )

    selected_smoke = ["p1", "p2", "p3"] if args.all_smoke else args.smoke
    for smoke in _unique_preserving_order(selected_smoke):
        steps.append(_smoke_step(smoke))
    if args.planner_eval_policy:
        policy_eval_path = "/tmp/chronos-planner-eval-policy.jsonl"
        steps.extend(
            [
                VerificationStep(
                    "Planning Engine evaluation JSONL",
                    [
                        sys.executable,
                        "scripts/evaluate_planning_engine.py",
                        "--run-id",
                        "policy-check",
                        "--jsonl-output",
                        policy_eval_path,
                    ],
                ),
                VerificationStep(
                    "Planning Engine golden policy check",
                    [sys.executable, "scripts/check_planner_eval_policy.py", policy_eval_path],
                ),
            ]
        )
    elif args.planner_eval:
        steps.append(
            VerificationStep(
                "Planning Engine evaluation",
                [sys.executable, "scripts/evaluate_planning_engine.py"],
            )
        )
    return steps


def _smoke_step(smoke: str) -> VerificationStep:
    scripts = {
        "p1": "scripts/smoke_p1_execution_loop.py",
        "p2": "scripts/smoke_p2_goal_insight_loop.py",
        "p3": "scripts/smoke_p3_natural_growth_loop.py",
        "llm-fallback": "scripts/smoke_daily_planner_fallback.py",
    }
    return VerificationStep(f"{smoke.upper()} smoke", [sys.executable, scripts[smoke]])


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        unique.append(value)
        seen.add(value)
    return unique


def _run_step(*, index: int, total: int, step: VerificationStep) -> None:
    started = time.monotonic()
    print(f"\n[{index}/{total}] {step.name}", flush=True)
    print("$ " + " ".join(step.command), flush=True)
    subprocess.run(step.command, cwd=ROOT_DIR, check=True)
    elapsed = time.monotonic() - started
    print(f"[{index}/{total}] passed in {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
