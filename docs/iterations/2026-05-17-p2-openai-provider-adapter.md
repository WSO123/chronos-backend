# Iteration: P2 OpenAI-Compatible Provider Adapter

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Daily Planner Agent 增加最小 OpenAI-compatible provider adapter，支持真实 structured output 调用边界、超时、重试、base_url 配置和 deterministic fallback；默认仍关闭真实 LLM，保证本地和 CI 稳定。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Daily Planner Agent Shell](./2026-05-17-p2-daily-planner-agent-shell.md)
- [x] [P2 Daily Planner Prompt Registry](./2026-05-17-p2-daily-planner-prompt-registry.md)

### 背景

Daily Planner Agent shell 和 prompt registry 已经落地，但真实 provider 尚未进入工程边界。为了后续验证真正的 LLM 编排质量，需要先把 provider adapter 做成可开关、可 fallback、可测试的最小实现。

这轮只接 provider 边界，不改变 Today 的产品体验和排序权力分配：Planning Engine v1 仍是 deterministic core；LLM 只返回结构化建议；PlanningService 仍负责校验和落库。

### 目标

- 新增 `OpenAICompatibleProvider`。
- 使用 OpenAI SDK `responses.parse(..., text_format=PydanticSchema)` 生成 structured output。
- 支持 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`、`LLM_MAX_RETRIES`。
- Provider registry 注册 `openai` 和 `openai-compatible`。
- `AI_ENABLE_REAL_LLM=false` 时始终使用 mock provider。
- 真实 provider 缺 key、网络失败或返回非法结构时，Daily Planner fallback 到 Planning Engine v1。
- AIJob 记录实际选中的 provider / model，而不是失败时误写 mock。
- 测试覆盖 provider 调用、metadata 过滤、错误包装、registry 选择和 PlanningService fallback trace。

### 非目标

- 不在默认环境开启真实 LLM。
- 不发真实网络请求。
- 不实现多 provider 自动路由。
- 不做成本统计、token 统计或限流。
- 不让 LLM 改变任务集合、排序或 section。

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

真实 provider 的引入不改变用户可见复杂度。用户看到的仍是清晰的 Today 顺序；provider、错误、fallback 和 prompt checksum 留在 `AIJob` 里，只用于解释和排障。

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
| OpenAI-compatible provider | 封装 Responses structured output | Must | `responses.parse` |
| Lazy client | 只有 provider 被使用时才创建 client | Must | 默认不触发真实调用 |
| Metadata filtering | 发送给真实 LLM 时过滤 `mock_output` 和内部 prompt trace | Must | 避免测试数据污染 |
| Registry selection | `AI_ENABLE_REAL_LLM=false` 强制 mock；true 时按 `LLM_PROVIDER` 选择 | Must | fallback provider 可配置 |
| AIJob trace | 记录实际 provider / model / fallback error | Must | Strategy Detail 可追踪 |
| Provider tests | 不发网络请求，用 fake client 验证调用参数 | Must | CI 稳定 |

### 用户故事

```text
作为 Chronos 用户，
我希望真实 AI 能逐步增强每日编排，但即使 AI 服务不可用，Today 仍然可靠，
以便我不会因为模型失败而失去当天行动入口。
```

```text
作为后端开发者，
我希望 provider adapter 有明确的开关、错误包装和 fallback，
以便后续接真实 LLM 时不会破坏 Planning Engine 的可控性。
```

```text
作为系统模块，
我希望 AIJob 记录实际 provider 和 model，
以便排查一次 planner 输出到底来自 mock、openai 还是 fallback。
```

### 主要流程

```text
PlanningService
-> llm_provider_registry.current_provider()
-> DailyPlannerAgent.run(provider=selected_provider)
-> OpenAICompatibleProvider.generate_structured()
-> provider returns Pydantic output
-> PlanningService validates and applies
```

Fallback 流程：

```text
AI_ENABLE_REAL_LLM=true + LLM_PROVIDER=openai
-> missing key / provider error / invalid output
-> LLMProviderError or validation error
-> AIJob.status=succeeded_with_fallback
-> Today keeps Planning Engine v1 output
```

---

## 5. 配置

默认本地：

```env
AI_ENABLE_REAL_LLM=false
LLM_PROVIDER=mock
LLM_MODEL=structured-mock-v1
LLM_FALLBACK_PROVIDER=mock
```

真实 provider 示例：

```env
AI_ENABLE_REAL_LLM=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=...
LLM_BASE_URL=
LLM_FALLBACK_PROVIDER=mock
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

OpenAI-compatible base_url 示例：

```env
AI_ENABLE_REAL_LLM=true
LLM_PROVIDER=openai-compatible
LLM_MODEL=<provider-model>
LLM_API_KEY=...
LLM_BASE_URL=https://...
```

---

## 6. 验收标准

- [x] `AI_ENABLE_REAL_LLM=false` 时 registry 返回 mock provider。
- [x] `AI_ENABLE_REAL_LLM=true` 且 `LLM_PROVIDER=openai` 时 registry 返回 openai provider。
- [x] OpenAI provider 调用 `responses.parse` 并传入 Pydantic schema。
- [x] OpenAI provider 不把 `mock_output` 和内部 prompt trace 发给真实模型。
- [x] provider 错误统一包装为 `LLMProviderError`。
- [x] PlanningService 在真实 provider 失败时 fallback，并记录 `provider=openai`。
- [x] Today / Strategy Detail / smoke 主路径不受影响。

---

## 7. 验证计划

```bash
uv run python -m unittest tests.test_llm_providers tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 8. Review Checklist

- [x] 是否默认不启用真实 LLM。
- [x] 是否没有真实网络测试。
- [x] 是否没有让 LLM 直接写业务表。
- [x] 是否记录实际 provider / model。
- [x] 是否保留 Planning Engine v1 fallback。

---

## 9. 后续迭代建议

1. 增加 provider smoke 手动脚本，只有显式传 env 时才发真实请求。
2. 增加 token / latency / cost observability。
3. 增加 planner agent 离线评估，把真实 provider 输出与 Planning Engine baseline 对比。
