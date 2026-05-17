from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


REDACTED_PRESENT = "<redacted-present>"


def load_json_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = _extract_first_json_object(text, path=path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def generate_acceptance_markdown(
    *,
    smoke: dict[str, Any],
    fallback: dict[str, Any] | None = None,
    compare: dict[str, Any],
    policy: dict[str, Any],
    provider: str | None = None,
    model: str | None = None,
    purpose: str = "daily-planner-provider-acceptance",
    owner: str = "",
    commit: str = "",
    iteration: str = "",
    environment: str = "local",
    base_url: str = "default / provider base url, no secrets",
    record_date: str | None = None,
    notes: str = "",
) -> str:
    record_date = record_date or date.today().isoformat()
    fallback = fallback or {}
    resolved_provider = provider or _text(smoke.get("provider"), "<provider>")
    resolved_model = model or _text(smoke.get("model"), "<model>")
    conclusion, conclusion_reason = _infer_conclusion(
        smoke=smoke,
        fallback=fallback,
        compare=compare,
        policy=policy,
    )
    prompt_version = _text(smoke.get("prompt_version"), "<prompt_version>")
    prompt_checksum = _text(smoke.get("prompt_checksum"), "<prompt_checksum>")

    return "\n".join(
        [
            f"# LLM Provider Acceptance: {resolved_provider} / {resolved_model} / {purpose}",
            "",
            f"> 状态：{conclusion}",
            f"> 日期：{record_date}",
            f"> 负责人：{owner}",
            f"> Commit：{commit}",
            f"> 关联迭代：{iteration}",
            "",
            "---",
            "",
            "## 1. 验收摘要",
            "",
            "自动生成的 LLM provider 验收草稿，用于汇总 provider smoke、fallback smoke、planner eval compare 和 golden policy check 结果。",
            "",
            "### 最终结论",
            "",
            _decision_checkboxes(conclusion),
            "",
            "结论说明：",
            "",
            "```text",
            conclusion_reason,
            "```",
            "",
            "---",
            "",
            "## 2. 验收范围",
            "",
            "### 本次验证对象",
            "",
            "| 字段 | 值 |",
            "| --- | --- |",
            f"| Provider | `{resolved_provider}` |",
            f"| Model | `{resolved_model}` |",
            f"| Base URL | `{base_url}` |",
            "| Agent | `Daily Planner Agent` |",
            f"| Prompt version | `{prompt_version}` |",
            f"| Prompt checksum | `{prompt_checksum}` |",
            "| Structured schema | `DailyPlannerOutput` |",
            f"| Environment | `{environment}` |",
            "",
            "### 本次改动",
            "",
            "- 自动汇总真实 provider smoke / planner eval compare / golden policy check。",
            "- 默认隐藏 provider response id，避免验收记录泄露可追踪原始标识。",
            "- 本草稿仍需人工 review 后再标记为最终 Accepted / Rejected。",
            "",
            "### 非目标",
            "",
            "- 不验证真实用户数据。",
            "- 不把真实 provider smoke 纳入默认 CI。",
            "- 不允许 LLM 直接写业务表。",
            "- 不绕过 Planning Engine / Service 校验。",
            "",
            "---",
            "",
            "## 3. 安全检查",
            "",
            "### 配置检查",
            "",
            "| 项 | 结果 | 备注 |",
            "| --- | --- | --- |",
            f"| Smoke status | `{_text(smoke.get('status'), 'unknown')}` | 来自 smoke JSON |",
            f"| Provider / model | `{resolved_provider}` / `{resolved_model}` | 来自参数或 smoke JSON |",
            f"| Compare status | `{_text(compare.get('status'), 'unknown')}` | regression_count=`{_number(compare.get('regression_count'))}` |",
            f"| Policy status | `{_text(policy.get('status'), 'unknown')}` | regression_count=`{_number(policy.get('regression_count'))}` |",
            "| `LLM_API_KEY` 未写入文档 | Pass | 仅允许记录 `<redacted>` |",
            "| Provider response id | Redacted | 默认记录 `<redacted-present>` 或空值 |",
            "",
            "### 产品 / 系统边界",
            "",
            _checkbox(smoke.get("status") == "ok", "LLM smoke 成功返回结构化结果。"),
            _checkbox(compare.get("status") != "regressed", "`compare_planner_eval_jsonl.py` 没有 regression。"),
            _checkbox(policy.get("status") != "regressed", "`check_planner_eval_policy.py` 没有 regression。"),
            _checkbox(smoke.get("task_ids_preserved") is True, "task ids 未被 provider 改写且顺序保持一致。"),
            _checkbox(
                smoke.get("task_id_set_preserved") is True and smoke.get("task_count_preserved") is True,
                "task 集合未被 provider 增删。",
            ),
            _checkbox(_fallback_verified(fallback), "失败时 Today 仍可走 Planning Engine fallback。"),
            "- [x] 没有在本草稿中写入 API key、真实用户输入或 provider 原始敏感响应。",
            "",
            "---",
            "",
            "## 4. 执行命令",
            "",
            "### 默认安全检查",
            "",
            "```bash",
            "uv run python scripts/smoke_llm_provider.py",
            "```",
            "",
            "### 真实 provider smoke",
            "",
            "```bash",
            "AI_ENABLE_REAL_LLM=true \\",
            f"LLM_PROVIDER={resolved_provider} \\",
            f"LLM_MODEL={resolved_model} \\",
            f"LLM_ALLOWED_PROVIDERS={resolved_provider} \\",
            f"LLM_ALLOWED_MODELS={resolved_model} \\",
            "LLM_MAX_OUTPUT_TOKENS=800 \\",
            "LLM_API_KEY=<redacted> \\",
            "uv run python scripts/smoke_llm_provider.py --allow-real-llm",
            "```",
            "",
            "### Daily Planner fallback smoke",
            "",
            "```bash",
            "uv run python scripts/smoke_daily_planner_fallback.py",
            "```",
            "",
            "### Planner eval baseline / candidate",
            "",
            "```bash",
            "uv run python scripts/evaluate_planning_engine.py --run-id <baseline-run-id> --jsonl-output /tmp/chronos-planner-baseline.jsonl",
            "uv run python scripts/evaluate_planning_engine.py --run-id <candidate-run-id> --jsonl-output /tmp/chronos-planner-candidate.jsonl",
            "```",
            "",
            "### JSONL compare",
            "",
            "```bash",
            "uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-baseline.jsonl /tmp/chronos-planner-candidate.jsonl",
            "```",
            "",
            "### Golden policy check",
            "",
            "```bash",
            "uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-candidate.jsonl",
            "```",
            "",
            "---",
            "",
            "## 5. 观测结果",
            "",
            "### Smoke output",
            "",
            _smoke_table(smoke),
            "",
            "Smoke JSON 摘要：",
            "",
            _json_block(_safe_summary(smoke, fields=_smoke_summary_fields())),
            "",
            "### Fallback smoke output",
            "",
            _fallback_table(fallback),
            "",
            "Fallback JSON 摘要：",
            "",
            _json_block(_safe_summary(fallback, fields=_fallback_summary_fields())),
            "",
            "### Planner compare output",
            "",
            _compare_table(compare),
            "",
            "Compare JSON 摘要：",
            "",
            _json_block(_safe_summary(compare, fields=_compare_summary_fields())),
            "",
            "### Golden policy output",
            "",
            _policy_table(policy),
            "",
            "Policy JSON 摘要：",
            "",
            _json_block(_safe_summary(policy, fields=_policy_summary_fields())),
            "",
            "### Scenario diffs",
            "",
            _scenario_diff_table(compare),
            "",
            "---",
            "",
            "## 6. 判断标准",
            "",
            "### 必须通过",
            "",
            _checkbox(smoke.get("status") == "ok", "Smoke `status=ok`。"),
            _checkbox(_matches(smoke.get("provider"), resolved_provider), "Provider 与本次验收目标一致。"),
            _checkbox(_matches(smoke.get("model"), resolved_model), "Model 与本次验收目标一致。"),
            _checkbox(bool(prompt_version) and prompt_version != "<prompt_version>", "Prompt version 已记录。"),
            _checkbox(bool(prompt_checksum) and prompt_checksum != "<prompt_checksum>", "Prompt checksum 已记录。"),
            _checkbox(smoke.get("task_ids_preserved") is True, "task ids 未变化。"),
            _checkbox(compare.get("status") != "regressed", "`compare_planner_eval_jsonl.py` 没有 regression。"),
            _checkbox(policy.get("status") != "regressed", "`check_planner_eval_policy.py` 没有 regression。"),
            _checkbox(_fallback_verified(fallback), "Fallback 仍可用。"),
            "",
            "### 可以接受但需要记录",
            "",
            _checkbox(_usage_is_empty(smoke.get("usage")), "usage 为空，但 provider 确认不返回 token usage。"),
            _checkbox(compare.get("status") == "changed" or policy.get("status") == "changed", "compare / policy 出现 `changed`，且原因已记录。"),
            "",
            "### 必须拒绝",
            "",
            _checkbox(smoke.get("status") == "failed", "Provider 返回非法 JSON 或 schema validation 失败。"),
            _checkbox(compare.get("status") == "regressed", "出现 planner compare regression。"),
            _checkbox(policy.get("status") == "regressed", "出现 planner golden policy regression。"),
            "",
            "---",
            "",
            "## 7. 风险与后续",
            "",
            "### 风险",
            "",
            "| 风险 | 影响 | 应对 |",
            "| --- | --- | --- |",
            _risk_row(fallback=fallback, compare=compare, policy=policy),
            "",
            "### 后续动作",
            "",
            "- [ ] 人工 review 本草稿中的结论、diff 和 checklist。",
            "- [ ] 如 compare / policy 为 `changed`，补充变化原因和最终判断。",
            "- [ ] 如结论为 Rejected / Blocked，补充修复计划或重跑条件。",
            "",
            "---",
            "",
            "## 8. Review",
            "",
            "### Review 结论",
            "",
            "```text",
            notes or "待人工 review。",
            "```",
            "",
            "### 是否允许进入下一步",
            "",
            _checkbox(conclusion in {"Accepted", "Accepted with Notes"}, "是"),
            _checkbox(conclusion not in {"Accepted", "Accepted with Notes"}, "否"),
            "",
            "原因：",
            "",
            "```text",
            conclusion_reason,
            "```",
            "",
        ]
    )


def _infer_conclusion(
    *,
    smoke: dict[str, Any],
    fallback: dict[str, Any],
    compare: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[str, str]:
    smoke_status = smoke.get("status")
    fallback_status = fallback.get("status")
    compare_status = compare.get("status")
    policy_status = policy.get("status")
    if smoke_status == "skipped":
        return "Blocked", "Smoke was skipped, so this record is not enough to accept a real provider."
    if smoke_status != "ok":
        return "Rejected", f"Smoke status is {smoke_status or 'unknown'}."
    if smoke.get("task_ids_preserved") is False:
        return "Rejected", "Smoke reported task id preservation failure."
    if smoke.get("task_id_set_preserved") is False or smoke.get("task_count_preserved") is False:
        return "Rejected", "Smoke reported task set preservation failure."
    if not fallback:
        return "Blocked", "Fallback smoke JSON is missing, so this record cannot prove Today fallback behavior."
    if fallback_status != "ok":
        return "Rejected", f"Fallback smoke status is {fallback_status or 'unknown'}."
    if not _fallback_verified(fallback):
        return "Rejected", "Fallback smoke did not verify Planning Engine fallback."
    if compare_status == "regressed" or _number(compare.get("regression_count")) > 0:
        return "Rejected", "Planner compare reported a regression."
    if policy_status == "regressed" or _number(policy.get("regression_count")) > 0:
        return "Rejected", "Planner golden policy check reported a regression."
    if compare_status == "changed" or policy_status == "changed":
        return "Accepted with Notes", "Smoke passed and no regression was found, but compare / policy changes need review notes."
    return "Accepted", "Smoke, planner compare and golden policy check all passed without regression."


def _decision_checkboxes(conclusion: str) -> str:
    return "\n".join(
        [
            _checkbox(conclusion == "Accepted", "Accepted"),
            _checkbox(conclusion == "Accepted with Notes", "Accepted with Notes"),
            _checkbox(conclusion == "Rejected", "Rejected"),
            _checkbox(conclusion == "Blocked", "Blocked"),
        ]
    )


def _smoke_table(smoke: dict[str, Any]) -> str:
    usage = smoke.get("usage") or {}
    rows = [
        ("Status", smoke.get("status")),
        ("Provider", smoke.get("provider")),
        ("Model", smoke.get("model")),
        ("Prompt version", smoke.get("prompt_version")),
        ("Prompt checksum", smoke.get("prompt_checksum")),
        ("Latency ms", smoke.get("latency_ms")),
        ("Confidence", smoke.get("confidence")),
        ("Item count", smoke.get("item_count")),
        ("Expected task ids", smoke.get("expected_task_ids")),
        ("Output task ids", smoke.get("output_task_ids")),
        ("Task ids preserved", smoke.get("task_ids_preserved")),
        ("Task id set preserved", smoke.get("task_id_set_preserved")),
        ("Task count preserved", smoke.get("task_count_preserved")),
        ("Missing task ids", smoke.get("missing_task_ids")),
        ("Unexpected task ids", smoke.get("unexpected_task_ids")),
        ("Input tokens", usage.get("input_tokens")),
        ("Output tokens", usage.get("output_tokens")),
        ("Total tokens", usage.get("total_tokens")),
        ("Cost USD", usage.get("cost_usd")),
        ("Provider response id", _redacted_response_id(smoke.get("provider_response_id"))),
    ]
    return _markdown_table(rows)


def _fallback_table(fallback: dict[str, Any]) -> str:
    rows = [
        ("Status", fallback.get("status")),
        ("Scenario", fallback.get("scenario")),
        ("Fallback verified", fallback.get("fallback_verified")),
        ("Today available", fallback.get("today_available")),
        ("Planning Engine used", fallback.get("planning_engine_used")),
        ("AI job id", fallback.get("ai_job_id")),
        ("Planner status", fallback.get("planner_agent_status")),
        ("Planner provider", fallback.get("planner_agent_provider")),
        ("Planner model", fallback.get("planner_agent_model")),
        ("Failure type", fallback.get("planner_agent_failure_type")),
        ("Output applied", fallback.get("planner_agent_output_applied")),
        ("Fallback reason", fallback.get("fallback_reason")),
        ("Fallback root error type", fallback.get("fallback_root_error_type")),
        ("Task count", fallback.get("task_count")),
    ]
    return _markdown_table(rows)


def _compare_table(compare: dict[str, Any]) -> str:
    rows = [
        ("Baseline run id", (compare.get("baseline") or {}).get("run_id")),
        ("Candidate run id", (compare.get("candidate") or {}).get("run_id")),
        ("Comparison status", compare.get("status")),
        ("Regression count", compare.get("regression_count")),
        ("Improvement count", compare.get("improvement_count")),
        ("Changed count", compare.get("changed_count")),
        ("Missing scenarios", compare.get("missing_in_candidate")),
        ("Added scenarios", compare.get("added_in_candidate")),
    ]
    return _markdown_table(rows)


def _policy_table(policy: dict[str, Any]) -> str:
    policy_meta = policy.get("policy") or {}
    eval_run = policy.get("eval_run") or {}
    rows = [
        ("Policy status", policy.get("status")),
        ("Policy version", policy_meta.get("policy_version")),
        ("Policy evaluator version", policy_meta.get("evaluator_version")),
        ("Eval run id", eval_run.get("run_id")),
        ("Eval evaluator version", eval_run.get("evaluator_version")),
        ("Required scenario count", policy_meta.get("required_scenario_count")),
        ("Regression count", policy.get("regression_count")),
        ("Change count", policy.get("change_count")),
    ]
    return _markdown_table(rows)


def _scenario_diff_table(compare: dict[str, Any]) -> str:
    diffs = compare.get("scenario_diffs") or []
    if not diffs:
        return "| Scenario | Change type | Detail | Decision |\n| --- | --- | --- | --- |\n| None | None | No scenario diffs reported. | Accept |"

    rows = ["| Scenario | Change type | Detail | Decision |", "| --- | --- | --- | --- |"]
    for diff in diffs[:20]:
        scenario = _text(diff.get("scenario_name"), "unknown")
        field_changes = diff.get("field_changes") or []
        signal_changes = diff.get("item_signal_changes") or []
        if not field_changes and not signal_changes:
            rows.append(f"| {_escape_cell(scenario)} | none | No detailed diff fields reported. | Review |")
        if field_changes:
            rows.append(
                f"| {_escape_cell(scenario)} | field_changes | {_escape_cell(_compact_json(field_changes[:3]))} | Investigate |"
            )
        if signal_changes:
            rows.append(
                f"| {_escape_cell(scenario)} | item_signal_changes | {_escape_cell(_compact_json(signal_changes[:3]))} | Investigate |"
            )
    return "\n".join(rows)


def _markdown_table(rows: list[tuple[str, Any]]) -> str:
    rendered = ["| 项 | 值 |", "| --- | --- |"]
    for key, value in rows:
        rendered.append(f"| {_escape_cell(key)} | {_escape_cell(_format_value(value))} |")
    return "\n".join(rendered)


def _safe_summary(payload: dict[str, Any], *, fields: list[str]) -> dict[str, Any]:
    summary = {}
    for field in fields:
        if field not in payload:
            continue
        if field in {"provider_response_id", "response_id"}:
            summary[field] = _redacted_response_id(payload.get(field))
        else:
            summary[field] = _redact_sensitive(payload.get(field))
    return summary


def _smoke_summary_fields() -> list[str]:
    return [
        "status",
        "provider",
        "model",
        "prompt_version",
        "prompt_checksum",
        "latency_ms",
        "mode",
        "confidence",
        "item_count",
        "expected_task_ids",
        "output_task_ids",
        "task_ids_preserved",
        "task_id_set_preserved",
        "task_count_preserved",
        "missing_task_ids",
        "unexpected_task_ids",
        "usage",
        "provider_response_id",
        "reason",
    ]


def _fallback_summary_fields() -> list[str]:
    return [
        "status",
        "scenario",
        "fallback_verified",
        "today_available",
        "planning_engine_used",
        "daily_plan_id",
        "ai_job_id",
        "planner_agent_status",
        "planner_agent_provider",
        "planner_agent_model",
        "planner_agent_failure_type",
        "planner_agent_output_applied",
        "fallback_reason",
        "fallback_error_type",
        "fallback_root_error_type",
        "provider_observability_version",
        "latency_ms",
        "task_count",
        "task_titles",
    ]


def _compare_summary_fields() -> list[str]:
    return [
        "comparison_version",
        "status",
        "baseline",
        "candidate",
        "regression_count",
        "improvement_count",
        "changed_count",
        "regressions",
        "improvements",
        "missing_in_candidate",
        "added_in_candidate",
    ]


def _policy_summary_fields() -> list[str]:
    return [
        "check_version",
        "status",
        "policy",
        "eval_run",
        "regression_count",
        "change_count",
        "regression_issues",
        "change_issues",
    ]


def _json_block(payload: dict[str, Any]) -> str:
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n```"


def _risk_row(*, fallback: dict[str, Any], compare: dict[str, Any], policy: dict[str, Any]) -> str:
    if not fallback or not _fallback_verified(fallback):
        return "| Fallback evidence missing | 真实 provider 失败时可能阻断 Today | 运行 `scripts/smoke_daily_planner_fallback.py` 并重生成验收记录 |"
    if compare.get("status") == "regressed" or policy.get("status") == "regressed":
        return "| Planner regression | 不能接受真实 provider / prompt 改动 | 修复后重跑 smoke、compare 和 policy check |"
    if compare.get("status") == "changed" or policy.get("status") == "changed":
        return "| Planner behavior changed | 可能影响 Today 编排信任 | 人工解释变化来源，必要时更新 baseline policy |"
    return "| 未发现自动化阻断项 | 仍需人工确认业务语义与 changed 原因 | 按模板完成 review |"


def _fallback_verified(fallback: dict[str, Any]) -> bool:
    return (
        fallback.get("status") == "ok"
        and fallback.get("fallback_verified") is True
        and fallback.get("today_available") is True
        and fallback.get("planning_engine_used") is True
        and fallback.get("planner_agent_status") == "succeeded_with_fallback"
        and fallback.get("planner_agent_output_applied") is False
        and fallback.get("planner_agent_failure_type") == "provider_error"
    )


def _extract_first_json_object(text: str, *, path: Path) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError(f"No JSON object found in {path}")


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key in {"provider_response_id", "response_id", "api_key", "LLM_API_KEY"}:
                redacted[key] = _redacted_response_id(item)
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _redacted_response_id(value: Any) -> str:
    if value in {None, ""}:
        return ""
    return REDACTED_PRESENT


def _usage_is_empty(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return True
    return all(item in {None, "", 0} for item in value.values())


def _matches(actual: Any, expected: str) -> bool:
    return actual == expected or expected.startswith("<")


def _checkbox(checked: bool, label: str) -> str:
    return f"- [{'x' if checked else ' '}] {label}"


def _number(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any, fallback: str) -> str:
    if value in {None, ""}:
        return fallback
    return str(value)


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _compact_json(_redact_sensitive(value))
    return str(value)


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown LLM provider acceptance draft.")
    parser.add_argument("--smoke-json", type=Path, required=True, help="Path to smoke_llm_provider.py JSON output.")
    parser.add_argument(
        "--fallback-json",
        type=Path,
        required=True,
        help="Path to smoke_daily_planner_fallback.py JSON output.",
    )
    parser.add_argument("--compare-json", type=Path, required=True, help="Path to planner eval compare JSON output.")
    parser.add_argument("--policy-json", type=Path, required=True, help="Path to planner eval policy check JSON output.")
    parser.add_argument("--output", type=Path, default=None, help="Optional Markdown output path. Defaults to stdout.")
    parser.add_argument("--provider", default=None, help="Provider override. Defaults to smoke JSON provider.")
    parser.add_argument("--model", default=None, help="Model override. Defaults to smoke JSON model.")
    parser.add_argument("--purpose", default="daily-planner-provider-acceptance", help="Acceptance purpose label.")
    parser.add_argument("--owner", default="", help="Record owner.")
    parser.add_argument("--commit", default="", help="Commit hash under validation.")
    parser.add_argument("--iteration", default="", help="Related iteration document or id.")
    parser.add_argument("--environment", default="local", help="Validation environment.")
    parser.add_argument("--base-url", default="default / provider base url, no secrets", help="Base URL label without secrets.")
    parser.add_argument("--date", default=None, help="Record date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--notes", default="", help="Optional review notes.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    markdown = generate_acceptance_markdown(
        smoke=load_json_payload(args.smoke_json),
        fallback=load_json_payload(args.fallback_json),
        compare=load_json_payload(args.compare_json),
        policy=load_json_payload(args.policy_json),
        provider=args.provider,
        model=args.model,
        purpose=args.purpose,
        owner=args.owner,
        commit=args.commit,
        iteration=args.iteration,
        environment=args.environment,
        base_url=args.base_url,
        record_date=args.date,
        notes=args.notes,
    )
    if args.output is None:
        print(markdown, end="")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
