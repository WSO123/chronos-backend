# Iteration: P2 Provider Usage Metadata

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Daily Planner Agent 的 LLM provider 返回值增加结构化 generation envelope，把 provider response id 和 token usage 透传到 `AIJob.job_metadata`，让真实 LLM 编排具备成本与排障观测基础，同时不改变 Today 用户体验。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Provider Observability v1](./2026-05-17-p2-provider-observability.md)
- [x] [P2 Real LLM Provider Manual Smoke](./2026-05-17-p2-real-llm-smoke-script.md)

### 背景

上一轮已经补了真实 provider 的手动 smoke，但 `AIJob.job_metadata.usage` 仍然只是空占位。真实 LLM 接入后，如果不能把 provider response usage 记录下来，后续就无法做模型成本评估、prompt 对比和线上排障。

本轮把 usage 提取放在 provider adapter，Agent 只透传，PlanningService 只落入 `AIJob.metadata`。这样不让 LLM 直接写业务表，也不把 token 信息放到 Today 首屏。

### 目标

- 新增 `LLMStructuredGeneration`，让 provider 返回 `output + usage + response_id`。
- Mock provider 返回稳定空 usage 结构。
- OpenAI-compatible provider 从 response 中提取 `input_tokens`、`output_tokens`、`total_tokens` 和 response id。
- Daily Planner Agent result 透传 usage 和 response id。
- PlanningService 将 usage 和 `provider_response_id` 写入 `AIJob.job_metadata`。
- 保持 fallback 时 usage 结构稳定。
- 补测试覆盖 provider usage 提取、Agent 透传和 AIJob metadata 回填。

### 非目标

- 不新增数据库字段或 migration。
- 不做价格表和 cost 计算，`cost_usd` 继续为 `null`。
- 不把 token usage 暴露到 Today 首屏。
- 不改变 Planning Engine 排序、容量或 fallback 规则。
- 不新增真实网络测试。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> AIJob trace
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

本轮增强“可信”，但不增加用户可见复杂度。用户仍然只看到清晰的 Today 编排；provider response id 和 usage 留在 AIJob trace，服务开发者排障、成本控制和后续策略评估。

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
| Generation envelope | Provider 返回 output、usage、response_id | Must | `LLMStructuredGeneration` |
| Usage extraction | OpenAI-compatible response usage 归一化 | Must | 支持 attribute / dict |
| Mock usage | mock provider 返回空 usage 结构 | Must | 保持默认测试稳定 |
| Agent passthrough | DailyPlannerAgentResult 透传 usage 和 response_id | Must | 不直接落库 |
| AIJob metadata | PlanningService 写入 `usage` 和 `provider_response_id` | Must | 不新增表 |
| Smoke output | 手动 provider smoke 输出 usage | Should | 默认仍 skipped |

### 用户故事

```text
作为 Chronos 用户，
我希望 AI 编排能力逐步接入真实模型时仍然稳定克制，
以便 Today 不因为技术观测信息而变得复杂。
```

```text
作为后端开发者，
我希望每次真实 provider 调用都能记录 token usage 和 response id，
以便后续评估模型成本、定位 provider 问题和比较 prompt 版本。
```

```text
作为系统模块，
我希望 mock、真实 provider 和 fallback 都保持相同 usage 结构，
以便 AIJob trace 的消费方不需要为不同 provider 写分支。
```

### 主要流程

```text
OpenAI-compatible provider calls responses.parse
-> extracts output_parsed, usage, response id
-> returns LLMStructuredGeneration
-> DailyPlannerAgentResult carries usage
-> PlanningService validates output
-> AIJob.job_metadata.usage / provider_response_id are persisted
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无数据库模型变更。复用 `AIJob.job_metadata`：

```json
{
  "provider_response_id": "resp_xxx",
  "usage": {
    "input_tokens": 111,
    "output_tokens": 22,
    "total_tokens": 133,
    "cost_usd": null
  }
}
```

### 状态机变更

无。

### 事件变更

无。

### API 变更

无新增 API。`GET /api/v1/ai-jobs/{job_id}` 会通过既有 `job_metadata` 返回 usage。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [x] 修改 Structured Output provider wrapper
- [ ] 修改 fallback

### Agent 设计

- Agent 名称：Daily Planner Agent
- 输入对象：deterministic candidates、strategy seed、plan context
- 输出对象：`DailyPlannerAgentResult`
- Pydantic schema：`DailyPlannerOutput`
- fallback 策略：不变，失败或业务校验不通过时使用 Planning Engine v1
- 是否需要用户确认：不需要，本轮只记录后台观测

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] Mock provider 返回空 usage 结构。
- [x] OpenAI-compatible provider 可从 response usage 提取 token 数。
- [x] DailyPlannerAgentResult 包含 usage 和 response id。
- [x] PlanningService 将 usage 写入 `AIJob.job_metadata.usage`。
- [x] PlanningService 将 response id 写入 `AIJob.job_metadata.provider_response_id`。
- [x] Strategy factors 不暴露 token usage，避免 Today / Strategy 过载。

### 数据验收

- [x] `AIJob.status=succeeded` 时 usage 可记录真实 token。
- [x] fallback 路径 usage 仍保持空结构。
- [x] 不新增 migration。
- [x] 不改变 ActivityEvent。

### 体验验收

- [x] 用户能清楚知道下一步。
- [x] 页面默认信息不过载。
- [x] AI 解释克制可信。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Provider usage extraction
- [x] DailyPlannerAgent passthrough
- [x] PlanningService AIJob metadata

### API 测试

- [ ] 本轮不新增 API。

### 集成测试

- [x] Default local verify
- [x] P1 / P2 / P3 smoke
- [x] Planner eval

### 手动验证

```bash
uv run python -m unittest tests.test_llm_providers tests.test_daily_planner_agent tests.test_today_services tests.test_llm_provider_smoke_script
uv run python scripts/smoke_llm_provider.py
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 不同 provider usage 字段命名不一致 | token 统计缺失 | adapter 内兼容 `input_tokens` / `prompt_tokens` 等常见字段 |
| token 信息进入用户主界面 | Today 变复杂 | 只写 AIJob metadata，不进入 Strategy factors |
| cost 计算过早 | 价格表维护复杂 | 本轮只保留 `cost_usd=null` |

### 关键取舍

- 取舍 1：修改 provider 返回 envelope，而不是让 Agent 读取 SDK response，保持 provider 差异封装在 adapter。
- 取舍 2：不新增 DB 字段，先使用 `AIJob.job_metadata` 保持迭代轻量。
- 取舍 3：Strategy factors 不增加 token 字段，避免解释层变成技术控制台。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Provider 返回 `LLMStructuredGeneration` | 同时承载结构化 output 和运行观测 | Agent / tests 需要按 envelope 读取 |
| 2026-05-17 | usage 只落入 AIJob metadata | 保护 Today 轻量体验 | 前端可通过 AIJob 深层查看 |
| 2026-05-17 | cost 暂不计算 | 模型价格和 provider 差异后续再定 | `cost_usd` 继续为 null |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 provider generation envelope | `app/ai/providers/base.py` | output + usage + response_id |
| 2026-05-17 | Mock / OpenAI-compatible provider 适配 | `app/ai/providers/*` | usage 提取 |
| 2026-05-17 | Agent / PlanningService 透传和落库 | `app/ai/agents/daily_planner.py`, `app/services/planning_service.py` | AIJob metadata |
| 2026-05-17 | 补测试 | `tests/test_llm_providers.py`, `tests/test_daily_planner_agent.py`, `tests/test_today_services.py` | provider / agent / service |
| 2026-05-17 | 更新 LLM / 架构 / 前端契约文档 | `docs/*` | usage 不进 Today 首屏 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_llm_providers tests.test_daily_planner_agent tests.test_today_services tests.test_llm_provider_smoke_script`
- [x] `uv run python scripts/smoke_llm_provider.py`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未执行真实 provider 网络调用；仍需使用 `--allow-real-llm` 和真实 key 手动验证。

### 已知问题

- `cost_usd` 暂不计算。

---

## 13. 后续迭代建议

1. 增加 planner offline eval JSONL 输出，用于对比不同 provider / prompt 的计划质量。
2. 增加 provider allowlist / cost guard，避免误用高成本模型。
3. 将真实 provider smoke 的 usage 输出纳入人工验收记录，但继续不进默认 CI。
