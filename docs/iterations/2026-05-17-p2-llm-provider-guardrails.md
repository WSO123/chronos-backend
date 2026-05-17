# Iteration: P2 LLM Provider Guardrails

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为真实 LLM provider 增加 provider allowlist、model allowlist 和输出 token 上限，避免误用未批准 provider / 高成本模型，同时保证 guard 失败时 Today 仍走 Planning Engine fallback。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 OpenAI-Compatible Provider Adapter](./2026-05-17-p2-openai-provider-adapter.md)
- [x] [P2 Real LLM Provider Manual Smoke](./2026-05-17-p2-real-llm-smoke-script.md)
- [x] [P2 Provider Usage Metadata](./2026-05-17-p2-provider-usage-metadata.md)
- [x] [P2 Planner Offline Eval JSONL](./2026-05-17-p2-planner-offline-eval-jsonl.md)

### 背景

真实 provider 已经具备 adapter、手动 smoke、usage metadata 和离线评估输出。下一步风险不是“能不能调用”，而是“是否可控地调用”：如果开发或后续部署误把高成本模型配置进去，或者 openai-compatible 指向未审查 provider，可能带来费用、稳定性和产品信任风险。

本轮把 guard 放在 provider adapter 边界，让真实请求发出前完成 provider、model 和输出 token 上限校验。guard 失败会被 Daily Planner 的既有 fallback 捕获，不阻塞 Today。

### 目标

- 新增 `LLM_ALLOWED_PROVIDERS` 配置。
- 新增 `LLM_ALLOWED_MODELS` 配置。
- 新增 `LLM_MAX_OUTPUT_TOKENS` 配置。
- OpenAI-compatible provider 在真实模式下请求前执行 guard。
- OpenAI-compatible provider 调用 `responses.parse` 时传入 `max_output_tokens`。
- 手动 smoke 在真实请求前执行同一套 guard。
- guard 失败时 PlanningService 记录 `AIJob.status=succeeded_with_fallback` 和 `failure_type=provider_error`。
- 补测试覆盖 provider guard、smoke guard 和 Today fallback。

### 非目标

- 不接真实 provider 网络测试。
- 不做美元成本估算或价格表维护。
- 不做 per-user / per-org 配额系统。
- 不新增数据库字段。
- 不改变 Planning Engine 排序和 fallback 规则。

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

本轮服务“可信”和“克制”：真实 LLM 可以增强编排，但不能因为配置错误、模型过贵或 provider 未审查而打断用户行动。复杂度留在后台 guard 和 AIJob trace 里，Today 仍然保持清晰。

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
| Provider allowlist | `LLM_ALLOWED_PROVIDERS` | Must | 默认 `openai,openai-compatible` |
| Model allowlist | `LLM_ALLOWED_MODELS` | Must | 默认 `gpt-4.1-mini` |
| Output token guard | `LLM_MAX_OUTPUT_TOKENS` | Must | 默认 800 |
| Shared guard helper | provider 和 smoke 共用 | Must | `app/ai/providers/guard.py` |
| Provider request cap | `responses.parse(max_output_tokens=...)` | Must | 限制输出成本 |
| Fallback integration | disallowed model 不阻塞 Today | Must | AIJob provider_error |

### 用户故事

```text
作为 Chronos 用户，
我希望真实 AI 接入时也不会因为配置错误导致 Today 不可用，
以便每天的行动入口始终稳定可信。
```

```text
作为后端开发者，
我希望真实 provider 请求在发出前经过 provider、model 和输出 token guard，
以便避免误用未批准 provider 或高成本模型。
```

```text
作为系统模块，
我希望 guard 失败能进入 AIJob fallback trace，
以便排障时知道是 provider guard 拒绝，而不是 Planning Engine 退化。
```

### 主要流程

```text
AI_ENABLE_REAL_LLM=true
-> registry selects openai / openai-compatible provider
-> provider.generate_structured
-> validate_real_llm_request(provider, model)
-> if allowed: responses.parse(max_output_tokens=LLM_MAX_OUTPUT_TOKENS)
-> if rejected: LLMProviderError
-> PlanningService marks AIJob succeeded_with_fallback
-> Today still returns deterministic plan
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
- [x] Scripts

### 数据模型变更

无。

新增配置：

```env
LLM_ALLOWED_PROVIDERS=openai,openai-compatible
LLM_ALLOWED_MODELS=gpt-4.1-mini
LLM_MAX_OUTPUT_TOKENS=800
```

### 状态机变更

无。guard 失败沿用：

```text
running -> succeeded_with_fallback
```

### 事件变更

无。

### API 变更

无。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [x] 修改 fallback guard

### Agent 设计

- Agent 名称：Daily Planner Agent
- 输入对象：不变
- 输出对象：不变
- Pydantic schema：不变
- fallback 策略：guard 失败抛出 `LLMProviderError`，PlanningService 使用 Planning Engine v1 fallback
- 是否需要用户确认：不需要，本轮是后台安全边界

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 真实模式下 provider 不在 `LLM_ALLOWED_PROVIDERS` 时拒绝请求。
- [x] 真实模式下 model 不在 `LLM_ALLOWED_MODELS` 时拒绝请求。
- [x] `LLM_MAX_OUTPUT_TOKENS <= 0` 时拒绝请求。
- [x] OpenAI-compatible provider 调用时传入 `max_output_tokens`。
- [x] 手动 smoke 在真实请求前校验 allowlist / token guard。
- [x] disallowed model 不阻塞 Today，AIJob 进入 fallback。

### 数据验收

- [x] 不新增 migration。
- [x] guard 失败记录 `failure_type=provider_error`。
- [x] guard 失败记录 provider / model。

### 体验验收

- [x] Today 主路径不受真实 provider 配置错误阻塞。
- [x] 用户界面不增加 provider / model 技术噪音。
- [x] 开发者可从 AIJob trace 看到失败原因。

---

## 8. 测试计划

### 单元测试

- [x] provider guard 拒绝 disallowed model。
- [x] provider guard 拒绝无效 max output tokens。
- [x] smoke config guard 覆盖 allowlist / token guard。

### API 测试

- [ ] 本轮不涉及新 API。

### 集成测试

- [x] Today disallowed model fallback。
- [x] full local verify。

### 手动验证

```bash
uv run python -m unittest tests.test_llm_providers tests.test_llm_provider_smoke_script tests.test_today_services tests.test_daily_planner_agent
uv run python scripts/smoke_llm_provider.py
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 默认 allowlist 太窄 | openai-compatible 自定义模型会被拒绝 | 文档要求显式配置 `LLM_ALLOWED_MODELS` |
| guard 抛错位置过早 | 可能阻塞 Today | guard 放在 provider 调用内，由 PlanningService fallback 捕获 |
| token 上限过小 | structured output 可能截断 | 默认 800，后续按评估结果调优 |

### 关键取舍

- 取舍 1：默认只允许 `gpt-4.1-mini`，先保护成本，真实扩展时显式配置。
- 取舍 2：不把 provider allowlist 放进数据库，先用环境配置作为部署安全边界。
- 取舍 3：guard 失败走 fallback，而不是让接口失败，保持 Chronos 每日执行入口稳定。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | provider guard 放在 adapter 内 | 请求发出前拦截，同时保留 PlanningService fallback | 不改变业务 service 调用方式 |
| 2026-05-17 | `LLM_MAX_OUTPUT_TOKENS` 传给 Responses API | 控制 structured output 费用和异常输出长度 | provider 测试需要覆盖参数 |
| 2026-05-17 | openai-compatible 自定义模型必须显式 allow | 避免任意 base_url / model 被误用 | 文档增加配置说明 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 LLM guard 配置 | `app/core/config.py` | providers / models / max tokens |
| 2026-05-17 | 新增 guard helper | `app/ai/providers/guard.py` | 共享校验 |
| 2026-05-17 | provider adapter 接入 guard | `app/ai/providers/openai_compatible.py` | 请求前校验 |
| 2026-05-17 | smoke 脚本接入 guard | `scripts/smoke_llm_provider.py` | 手动真实调用前校验 |
| 2026-05-17 | 补测试 | `tests/*` | provider / smoke / Today |
| 2026-05-17 | 更新文档 | README / LLM / guidelines | 配置说明 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_llm_providers tests.test_llm_provider_smoke_script tests.test_today_services tests.test_daily_planner_agent`
- [x] `uv run python scripts/smoke_llm_provider.py`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未执行真实 provider 网络调用。

### 已知问题

- `LLM_MAX_OUTPUT_TOKENS=800` 是保守默认值，后续需要结合真实输出和 JSONL 评估调整。

---

## 13. 后续迭代建议

1. 增加 planner eval scenarios：依赖链、用户手动优先级、重复中断行为反馈。
2. 增加 JSONL 对比脚本，读取多次评估并输出 prompt / provider 差异摘要。
3. 增加真实 provider 手动验收记录模板，记录 model、usage、prompt checksum 和结论。
