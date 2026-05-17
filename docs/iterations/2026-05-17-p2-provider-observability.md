# Iteration: P2 Provider Observability v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Daily Planner Agent 的 provider 调用补齐第一版观测字段：记录调用耗时、失败分类、root error 类型和 token/cost 占位，让后续真实 LLM 接入后可以排障和评估，而不改变 Today 用户体验。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Daily Planner Agent Shell](./2026-05-17-p2-daily-planner-agent-shell.md)
- [x] [P2 OpenAI-Compatible Provider Adapter](./2026-05-17-p2-openai-provider-adapter.md)

### 背景

OpenAI-compatible provider adapter 已经接入，但 AIJob 对 provider 调用的观测仍然偏薄：只有 provider、model、status 和 error message。真实 LLM 接入后，如果缺少 latency、失败分类和 usage 结构，排障会变成读日志和猜测。

本轮补第一版轻量观测，不新增数据库字段，不改变 Today / Strategy Detail 的展示复杂度；所有新增信息都写入已有的 `AIJob.latency_ms` 和 `AIJob.job_metadata`。

### 目标

- Daily Planner Agent 调用记录 `AIJob.latency_ms`。
- `job_metadata.provider_latency_ms` 与 `AIJob.latency_ms` 对齐。
- `job_metadata.provider_observability_version = v1`。
- fallback 时记录 `failure_type`：`provider_error` / `invalid_output` / `agent_error`。
- fallback 时记录 `fallback_root_error_type`，便于区分包装错误和底层错误。
- 预留 `usage.input_tokens`、`usage.output_tokens`、`usage.total_tokens`、`usage.cost_usd`。
- Strategy factors 暴露轻量 `planner_agent_latency_ms` 和 `planner_agent_failure_type`，只供 Strategy Detail / 调试使用。

### 非目标

- 不新增 migration。
- 不接真实 usage / token 统计。
- 不做成本计算。
- 不把 latency / failure_type 展示到 Today 首屏。
- 不改变 provider adapter 的网络行为。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [x] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

观测信息服务“可信”，但不抢走“行动感”。用户仍然看到简洁的 Today 计划；开发者和后续 Strategy Detail 可以用 AIJob trace 解释“AI 是否参与、是否 fallback、失败在哪里”。

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

---

## 4. 需求范围

### 功能清单

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Provider latency | 记录 Daily Planner Agent 调用耗时 | Must | `AIJob.latency_ms` |
| Observability metadata | `provider_latency_ms`、`provider_observability_version` | Must | 不新增表 |
| Failure type | 分类 provider / invalid output / agent error | Must | fallback 排障 |
| Root error type | 记录底层异常类型 | Should | 兼容包装异常 |
| Usage placeholder | 预留 token / cost 字段 | Should | 后续真实 provider 接入 |
| Strategy factors | 暴露轻量 latency / failure type | Could | 不放 Today 首屏 |

### 用户故事

```text
作为 Chronos 用户，
我希望即使 AI provider 偶尔失败，Today 仍然稳定可用，
以便我不会被技术错误打断当天行动。
```

```text
作为后端开发者，
我希望每次 planner provider 调用都有 latency 和失败分类，
以便真实 LLM 接入后能快速定位是 provider、输出校验还是 Agent 自身问题。
```

```text
作为系统模块，
我希望 token / cost 字段先有稳定结构，
以便后续接入 usage 统计时不需要再改变 AIJob trace 的形状。
```

### 主要流程

```text
PlanningService selects provider
-> start perf_counter
-> DailyPlannerAgent.run
-> success or fallback
-> job.latency_ms = elapsed
-> job_metadata.provider_latency_ms = elapsed
-> job_metadata.failure_type = provider_error / invalid_output / agent_error when fallback
```

---

## 5. AIJob Metadata v1

成功：

```json
{
  "output_applied": true,
  "provider_latency_ms": 12,
  "provider_observability_version": "v1",
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "total_tokens": null,
    "cost_usd": null
  }
}
```

Fallback：

```json
{
  "output_applied": false,
  "fallback_reason": "daily_planner_agent_failed",
  "fallback_error_type": "LLMProviderError",
  "fallback_root_error_type": "LLMProviderError",
  "failure_type": "provider_error",
  "provider_latency_ms": 2,
  "provider_observability_version": "v1",
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "total_tokens": null,
    "cost_usd": null
  }
}
```

失败分类：

| failure_type | 含义 |
| --- | --- |
| `provider_error` | Provider / SDK / key / 网络 / structured parse 调用失败 |
| `invalid_output` | Provider 返回结构存在，但业务层校验不通过 |
| `agent_error` | Agent function 自身异常 |

---

## 6. 验收标准

- [x] 成功调用记录 `AIJob.latency_ms`。
- [x] 成功调用记录 `provider_latency_ms`、`provider_observability_version` 和稳定 usage 空结构。
- [x] Agent runtime error fallback 记录 `failure_type=agent_error`。
- [x] invalid output fallback 记录 `failure_type=invalid_output`。
- [x] provider fallback 记录 `failure_type=provider_error`。
- [x] Strategy factors 记录 `planner_agent_latency_ms` 和 `planner_agent_failure_type`。
- [x] P1/P2/P3 smoke 不受影响。

---

## 7. 验证计划

```bash
uv run python -m unittest tests.test_today_services tests.test_llm_providers tests.test_daily_planner_agent tests.test_today_api
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 8. Review Checklist

- [x] 是否没有新增用户可见复杂度。
- [x] 是否没有新增数据库 migration。
- [x] 是否没有真实网络请求测试。
- [x] 是否没有让 provider 写业务表。
- [x] 是否为后续 token / cost 统计预留稳定结构。

---

## 9. 后续迭代建议

1. 增加真实 provider 手动 smoke 脚本，只在显式 env 下发请求。
2. 接入 Responses usage 字段，填充 token 统计。已由 [P2 Provider Usage Metadata](./2026-05-17-p2-provider-usage-metadata.md) 承接。
3. 增加 planner agent 离线评估结果表或 JSONL 输出，用于对比不同 provider / prompt。
