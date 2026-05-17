# LLM Provider Acceptance: <provider> / <model> / <purpose>

> 状态：Draft / Accepted / Accepted with Notes / Rejected / Blocked
> 日期：YYYY-MM-DD
> 负责人：
> Commit：
> 关联迭代：

---

## 1. 验收摘要

一句话说明本次真实 provider 验收要确认什么。

```text
示例：验证 openai / gpt-4.1-mini 能稳定返回 Daily Planner structured output，且不会改变 task ids、排序和业务边界。
```

### 最终结论

- [ ] Accepted
- [ ] Accepted with Notes
- [ ] Rejected
- [ ] Blocked

结论说明：

```text
填写是否可以进入后续开发 / 小流量 / 继续观察，以及原因。
```

---

## 2. 验收范围

### 本次验证对象

| 字段 | 值 |
| --- | --- |
| Provider | `<openai / openai-compatible>` |
| Model | `<model>` |
| Base URL | `<default / provider base url, no secrets>` |
| Agent | `Daily Planner Agent` |
| Prompt version | `<prompt_version>` |
| Prompt checksum | `<prompt_checksum>` |
| Structured schema | `DailyPlannerOutput` |
| Environment | `local / staging / other` |

### 本次改动

- 改动 1：
- 改动 2：
- 改动 3：

### 非目标

- 不验证真实用户数据。
- 不把真实 provider smoke 纳入默认 CI。
- 不允许 LLM 直接写业务表。
- 不绕过 Planning Engine / Service 校验。

---

## 3. 安全检查

### 配置检查

| 项 | 结果 | 备注 |
| --- | --- | --- |
| `AI_ENABLE_REAL_LLM=true` | Pass / Fail |  |
| `LLM_PROVIDER` 在 allowlist 内 | Pass / Fail |  |
| `LLM_MODEL` 在 allowlist 内 | Pass / Fail |  |
| `LLM_API_KEY` 已配置且未写入文档 | Pass / Fail | 仅记录 `<redacted>` |
| `LLM_MAX_OUTPUT_TOKENS` 为正且受控 | Pass / Fail |  |
| 默认 `uv run python scripts/smoke_llm_provider.py` 仍为 skipped | Pass / Fail |  |

### 产品 / 系统边界

- [ ] LLM 不直接写业务表。
- [ ] LLM 输出经过 structured schema validation。
- [ ] task ids 未被 provider 改写。
- [ ] task 集合未被 provider 增删。
- [ ] sort order / section 边界仍由业务层保护。
- [ ] 失败时 Today 仍可走 Planning Engine fallback。
- [ ] 没有提交 API key、真实用户输入或 provider 原始敏感响应。

---

## 4. 执行命令

### 默认安全检查

```bash
uv run python scripts/smoke_llm_provider.py
```

结果摘要：

```json
{
  "status": "skipped",
  "reason": "..."
}
```

### 真实 provider smoke

```bash
AI_ENABLE_REAL_LLM=true \
LLM_PROVIDER=<provider> \
LLM_MODEL=<model> \
LLM_ALLOWED_PROVIDERS=<provider> \
LLM_ALLOWED_MODELS=<model> \
LLM_MAX_OUTPUT_TOKENS=800 \
LLM_API_KEY=<redacted> \
uv run python scripts/smoke_llm_provider.py --allow-real-llm
```

结果摘要：

```json
{
  "status": "ok",
  "provider": "<provider>",
  "model": "<model>",
  "prompt_version": "<prompt_version>",
  "prompt_checksum": "<prompt_checksum>",
  "latency_ms": 0,
  "mode": "<mode>",
  "confidence": 0.0,
  "item_count": 2,
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "total_tokens": null,
    "cost_usd": null
  },
  "provider_response_id": "<id-or-redacted>"
}
```

### Planner eval baseline / candidate

```bash
uv run python scripts/evaluate_planning_engine.py --run-id <baseline-run-id> --jsonl-output /tmp/chronos-planner-baseline.jsonl
uv run python scripts/evaluate_planning_engine.py --run-id <candidate-run-id> --jsonl-output /tmp/chronos-planner-candidate.jsonl
```

### JSONL compare

```bash
uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-baseline.jsonl /tmp/chronos-planner-candidate.jsonl
```

结果摘要：

```json
{
  "status": "ok",
  "regression_count": 0,
  "improvement_count": 0,
  "changed_count": 0,
  "regressions": [],
  "scenario_diffs": []
}
```

---

## 5. 观测结果

### Smoke output

| 项 | 值 |
| --- | --- |
| Status |  |
| Provider |  |
| Model |  |
| Prompt version |  |
| Prompt checksum |  |
| Latency ms |  |
| Confidence |  |
| Item count |  |
| Input tokens |  |
| Output tokens |  |
| Total tokens |  |
| Cost USD |  |
| Provider response id |  |

### Planner compare output

| 项 | 值 |
| --- | --- |
| Baseline run id |  |
| Candidate run id |  |
| Comparison status |  |
| Regression count |  |
| Improvement count |  |
| Changed count |  |
| Missing scenarios |  |
| Added scenarios |  |

### Scenario diffs

| Scenario | Change type | Detail | Decision |
| --- | --- | --- | --- |
|  |  |  | Accept / Investigate / Reject |

---

## 6. 判断标准

### 必须通过

- [ ] Smoke `status=ok`。
- [ ] Provider / model 与本次验收目标一致。
- [ ] Prompt version / checksum 与预期一致。
- [ ] task ids 未变化。
- [ ] `compare_planner_eval_jsonl.py` 没有 regression。
- [ ] Fallback 仍可用。

### 可以接受但需要记录

- [ ] usage 为空，但 provider 确认不返回 token usage。
- [ ] latency 偏高，但仍在本阶段手动验收可接受范围。
- [ ] compare 出现 `changed`，但原因来自预期 prompt / model 差异。

### 必须拒绝

- [ ] Provider 返回非法 JSON 或 schema validation 失败。
- [ ] Provider 改写 task id、删除任务或新增任务。
- [ ] Provider 输出绕过业务层边界。
- [ ] 出现未解释的 planner regression。
- [ ] 真实 provider 失败会阻塞 Today 主链路。

---

## 7. 风险与后续

### 风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
|  |  |  |

### 后续动作

- [ ] 后续动作 1：
- [ ] 后续动作 2：
- [ ] 后续动作 3：

---

## 8. Review

### Review 结论

```text
填写 review 人对本次验收记录的判断。
```

### 是否允许进入下一步

- [ ] 是
- [ ] 否

原因：

```text
填写原因。
```
