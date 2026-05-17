# LLM Provider Acceptance Dry Run

这个文档用于演练真实 provider 验收流程，但不调用真实 LLM，不需要 API key，也不代表某个 provider 已被接受。

dry-run 的目标是确认四份 JSON 如何进入最终验收记录：

```text
provider smoke JSON
-> fallback smoke JSON
-> planner compare JSON
-> golden policy JSON
-> acceptance Markdown draft
```

## 推荐命令

```bash
uv run python scripts/generate_llm_acceptance_dry_run.py --date 2026-05-17
```

默认输出：

```text
/tmp/chronos-llm-acceptance-dry-run/smoke.json
/tmp/chronos-llm-acceptance-dry-run/fallback.json
/tmp/chronos-llm-acceptance-dry-run/compare.json
/tmp/chronos-llm-acceptance-dry-run/policy.json
/tmp/chronos-llm-acceptance-dry-run/dry-run-openai-gpt-4-1-mini-daily-planner.md
```

如需指定输出路径：

```bash
uv run python scripts/generate_llm_acceptance_dry_run.py \
  --date 2026-05-17 \
  --json-dir /tmp/chronos-llm-acceptance-dry-run \
  --output /tmp/chronos-llm-acceptance-dry-run/dry-run-acceptance.md
```

## 四份 JSON 的角色

| JSON | 来源 | 证明什么 |
| --- | --- | --- |
| `smoke.json` | synthetic provider smoke payload | provider 返回 structured output，task ids 未被改写、删除或新增 |
| `fallback.json` | synthetic fallback smoke payload | provider 失败时 Today / Strategy 仍走 Planning Engine fallback |
| `compare.json` | synthetic planner eval compare payload | candidate 没有相对 baseline 产生 regression |
| `policy.json` | synthetic golden policy payload | candidate 满足 planner eval golden baseline |

## dry-run 的预期结论

生成的 Markdown 草稿应包含：

```text
> 状态：Accepted
```

同时应能看到这些自动勾选项：

```text
- [x] task ids 未被 provider 改写且顺序保持一致。
- [x] task 集合未被 provider 增删。
- [x] 失败时 Today 仍可走 Planning Engine fallback。
- [x] Fallback 仍可用。
```

provider response id 会被生成器脱敏为：

```text
<redacted-present>
```

## 切换到真实 provider 验收

dry-run 通过后，真实 provider 验收需要替换四份 JSON：

```bash
AI_ENABLE_REAL_LLM=true \
LLM_PROVIDER=openai \
LLM_MODEL=gpt-4.1-mini \
LLM_ALLOWED_PROVIDERS=openai \
LLM_ALLOWED_MODELS=gpt-4.1-mini \
LLM_MAX_OUTPUT_TOKENS=800 \
LLM_API_KEY=<redacted> \
uv run python scripts/smoke_llm_provider.py --allow-real-llm > /tmp/chronos-llm-smoke.json

uv run python scripts/smoke_daily_planner_fallback.py > /tmp/chronos-llm-fallback.json

uv run python scripts/evaluate_planning_engine.py --run-id baseline --jsonl-output /tmp/chronos-planner-baseline.jsonl
uv run python scripts/evaluate_planning_engine.py --run-id candidate --jsonl-output /tmp/chronos-planner-candidate.jsonl
uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-baseline.jsonl /tmp/chronos-planner-candidate.jsonl > /tmp/chronos-planner-compare.json
uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-candidate.jsonl > /tmp/chronos-planner-policy.json

uv run python scripts/generate_llm_acceptance_record.py \
  --smoke-json /tmp/chronos-llm-smoke.json \
  --fallback-json /tmp/chronos-llm-fallback.json \
  --compare-json /tmp/chronos-planner-compare.json \
  --policy-json /tmp/chronos-planner-policy.json \
  --provider openai \
  --model gpt-4.1-mini \
  --purpose daily-planner-provider-acceptance \
  --output docs/llm-provider-acceptance/YYYY-MM-DD-openai-gpt-4-1-mini-daily-planner.md
```

## 边界

- dry-run 不证明真实 provider 可用。
- dry-run 不允许写入 API key、真实用户输入或 provider 原始响应。
- dry-run 只验证验收流程本身能跑通。
- 真实 provider 记录仍必须人工 review 后才能从 Draft 变成最终结论。
