# LLM Provider Acceptance Records

这个目录用于沉淀真实 LLM provider 的手动验收记录。

真实 provider 验证不会进入默认 CI、`verify_local` 或本地 smoke 链路。每次需要实际调用外部模型时，必须显式开启环境变量、使用 `--allow-real-llm`，并用本目录的模板记录结论。

## 使用方式

1. 优先使用 `scripts/generate_llm_acceptance_record.py` 从 provider smoke / fallback smoke / compare / policy JSON 输出生成草稿；必要时从 [TEMPLATE.md](./TEMPLATE.md) 手动复制一份记录。
2. 文件命名建议：

```text
YYYY-MM-DD-<provider>-<model>-<purpose>.md
```

示例：

```text
2026-05-17-openai-gpt-4-1-mini-daily-planner-smoke.md
```

3. 记录必须包含：

- provider / model / base URL 类型。
- commit hash 和测试日期。
- `scripts/smoke_llm_provider.py` 的输出摘要。
- `scripts/smoke_daily_planner_fallback.py` 的输出摘要，用于证明 provider 失败时 Today 仍可走 Planning Engine。
- prompt version 和 prompt checksum。
- task id preservation 明细：`expected_task_ids`、`output_task_ids`、`task_ids_preserved`、`task_id_set_preserved`。
- usage / latency / response id 摘要。
- planner eval JSONL compare 结果。
- safety checklist 和最终结论。

## 安全边界

- 不要提交 API key、完整请求头、完整 provider 原始响应、用户隐私输入或生产数据。
- `LLM_API_KEY` 只能以 `<redacted>` 记录。
- `provider_response_id` 默认由生成脚本脱敏为 `<redacted-present>`；如需完整值，只能在确认 provider 规则允许后人工补充安全摘要。
- 真实 provider 验收只能使用 synthetic / demo 输入，不能使用真实用户数据。
- 真实 provider 调用失败不能阻塞核心闭环，必须确认 fallback 仍可用。

## 推荐命令

默认安全检查，不发网络请求：

```bash
uv run python scripts/smoke_llm_provider.py
```

真实 provider 手动 smoke：

```bash
AI_ENABLE_REAL_LLM=true \
LLM_PROVIDER=openai \
LLM_MODEL=gpt-4.1-mini \
LLM_ALLOWED_PROVIDERS=openai \
LLM_ALLOWED_MODELS=gpt-4.1-mini \
LLM_MAX_OUTPUT_TOKENS=800 \
LLM_API_KEY=<redacted> \
uv run python scripts/smoke_llm_provider.py --allow-real-llm
```

Daily Planner fallback smoke，不发网络请求：

```bash
uv run python scripts/smoke_daily_planner_fallback.py
```

Planner eval JSONL 对比：

```bash
uv run python scripts/evaluate_planning_engine.py --run-id baseline --jsonl-output /tmp/chronos-planner-baseline.jsonl
uv run python scripts/evaluate_planning_engine.py --run-id candidate --jsonl-output /tmp/chronos-planner-candidate.jsonl
uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-baseline.jsonl /tmp/chronos-planner-candidate.jsonl
uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-candidate.jsonl
```

生成验收草稿：

```bash
uv run python scripts/generate_llm_acceptance_record.py \
  --smoke-json /tmp/chronos-llm-smoke.json \
  --fallback-json /tmp/chronos-llm-fallback.json \
  --compare-json /tmp/chronos-planner-compare.json \
  --policy-json /tmp/chronos-planner-policy.json \
  --provider openai \
  --model gpt-4.1-mini \
  --purpose daily-planner-smoke \
  --output docs/llm-provider-acceptance/YYYY-MM-DD-openai-gpt-4-1-mini-daily-planner-smoke.md
```

脚本只生成草稿，不调用真实 provider，不代表免 review。生成后仍需人工核对 changed 原因和业务语义；task id preservation 与 fallback 可用性会优先使用 smoke JSON 中的结构化字段。
