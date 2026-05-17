# Iteration: P2 Daily Planner Fallback Smoke Evidence

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Daily Planner Agent 增加 fallback smoke 证据链，并让真实 provider acceptance record 自动读取该证据，证明 provider 失败时 Today / Strategy 仍能走 Planning Engine fallback。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [LLM Provider Acceptance Template](../llm-provider-acceptance/TEMPLATE.md)
- [x] [P2 LLM Smoke Task ID Preservation](./2026-05-17-p2-llm-smoke-task-id-preservation.md)

### 背景

真实 provider smoke 已经能验证 structured output、task id preservation、planner eval compare 和 golden policy。但验收记录中仍有一个关键安全项依赖人工确认：真实 provider 或 guard 失败时，Today 是否还能返回 Planning Engine fallback。

Chronos 的核心原则是 AI 可以增强编排，但不能阻断执行闭环。本轮把 fallback 可用性从手工 checkbox 转为结构化 smoke JSON。

### 目标

- 新增 `scripts/smoke_daily_planner_fallback.py`。
- smoke 不调用真实 provider，不产生网络或费用。
- smoke 强制 real-provider 配置失败，验证 Today / Strategy 仍返回可用结果。
- 输出 `fallback_verified`、`planning_engine_used`、`planner_agent_status`、`planner_agent_failure_type`、`planner_agent_output_applied` 等字段。
- `scripts/generate_llm_acceptance_record.py` 新增 `--fallback-json`。
- acceptance record 在缺少 fallback JSON 时进入 `Blocked`，fallback 失败时进入 `Rejected`。
- 更新 README、工程规范、LLM 架构和真实 provider 验收模板。

### 非目标

- 不调用真实 LLM。
- 不改变 Daily Planner Agent prompt。
- 不改变 Planning Engine 排序逻辑。
- 不新增数据库表、API 或 migration。
- 不把真实 provider smoke 放入默认 CI。

---

## 3. 产品约束对齐

### 核心路径

```text
Provider failure / guard failure
-> Daily Planner Agent fails
-> PlanningService marks AIJob succeeded_with_fallback
-> Today / Strategy still return Planning Engine plan
-> Acceptance Record records fallback evidence
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [x] AI Agent

### 产品人格

这轮属于后台可信度建设。用户仍只看到可执行的 Today，不看到 provider 失败细节；复杂度留在系统背后，验收记录负责证明系统没有把 AI 的不稳定性传递给用户。

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
| Fallback smoke | 强制 provider guard 失败并验证 Today fallback | Must | 不发网络请求 |
| Evidence payload | 输出 fallback_verified / planning_engine_used 等字段 | Must | 供 acceptance 使用 |
| Acceptance input | generator 新增 `--fallback-json` | Must | 生成草稿必填 |
| Conclusion gate | 缺少 fallback 证据 Blocked，fallback 失败 Rejected | Must | 防止误接 provider |
| Verify runner | `--smoke llm-fallback` 支持显式运行 | Should | 不进入 `--all-smoke` |
| Docs update | README / TEMPLATE / LLM / Engineering 同步 | Should | 防漂移 |
| Tests | 覆盖 payload 和 acceptance 判断 | Must | 不调用真实 provider |

### 用户故事

```text
作为验收负责人，
我希望真实 provider 验收记录自动展示 fallback smoke 结果，
以便判断 provider 失败是否会阻断 Today 主链路。
```

```text
作为后端开发者，
我希望 fallback smoke 不依赖真实 LLM 和 API key，
以便本地可重复验证 AI 安全边界。
```

```text
作为 Chronos 用户的代理人，
我希望 AI 不可用时系统仍给出今天能做的计划，
以便 Chronos 的执行入口保持可信。
```

### 主要流程

```text
run smoke_daily_planner_fallback.py
-> set AI_ENABLE_REAL_LLM=true with missing API key
-> create synthetic task
-> call Today Strategy
-> provider guard fails
-> PlanningService falls back
-> fetch AIJob
-> output fallback evidence JSON
-> generate acceptance record with --fallback-json
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [ ] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests
- [x] Scripts
- [x] Docs

### 数据模型变更

无。

### 新增 smoke 输出

```json
{
  "status": "ok",
  "scenario": "daily_planner_provider_failure",
  "fallback_verified": true,
  "today_available": true,
  "planning_engine_used": true,
  "planner_agent_status": "succeeded_with_fallback",
  "planner_agent_provider": "openai",
  "planner_agent_model": "gpt-4.1-mini",
  "planner_agent_failure_type": "provider_error",
  "planner_agent_output_applied": false,
  "fallback_reason": "daily_planner_agent_failed",
  "fallback_root_error_type": "LLMProviderError"
}
```

### Acceptance 判断规则

- `fallback` 缺失：`Blocked`。
- `fallback.status != ok`：`Rejected`。
- `fallback_verified=false`：`Rejected`。
- `planner_agent_status != succeeded_with_fallback`：`Rejected`。
- `planner_agent_output_applied != false`：`Rejected`。
- `planner_agent_failure_type != provider_error`：`Rejected`。
- 上述规则与 provider smoke / compare / policy 一起决定最终结论。

### Verify runner

新增显式入口：

```bash
uv run python scripts/verify_local.py --smoke llm-fallback
```

`--all-smoke` 仍只代表 P1 / P2 / P3 主路径 smoke，不默认加入 LLM fallback。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [x] 修改 fallback 验收证据

### Agent 设计

- Agent 名称：Daily Planner Agent
- 输入对象：synthetic task / Today Strategy request
- 输出对象：fallback evidence JSON
- Pydantic schema：不变
- fallback 策略：不变，仅新增证据化 smoke
- 是否需要用户确认：不涉及用户确认

### LLM 安全边界

- [x] 不调用真实 LLM。
- [x] 不提交 API key。
- [x] provider guard 失败不能阻断 Today。
- [x] LLM 不直接写业务表。
- [x] fallback 结果仍来自 Planning Engine v1。

---

## 7. 验收标准

### 功能验收

- [x] `scripts/smoke_daily_planner_fallback.py` 输出 `fallback_verified=true`。
- [x] 输出 `planning_engine_used=true`。
- [x] 输出 `planner_agent_status=succeeded_with_fallback`。
- [x] 输出 `planner_agent_failure_type=provider_error`。
- [x] acceptance generator 新增 `--fallback-json`。
- [x] acceptance generator 缺少 fallback JSON 时 `Blocked`。
- [x] acceptance generator fallback 失败时 `Rejected`。

### 数据验收

- [x] 不新增 migration。
- [x] 不写真实用户数据。
- [x] smoke 使用 synthetic task。
- [x] 不提交生成的验收实例。

### 体验验收

- [x] Today 用户体验不变。
- [x] Provider 失败细节只进入后台 AIJob / 验收记录。
- [x] 验收流程减少人工 checkbox。

---

## 8. 测试与验证

### 单元测试

- [x] `tests.test_llm_fallback_smoke_script`
- [x] `tests.test_llm_acceptance_record_generator`
- [x] `tests.test_llm_provider_acceptance_template`

### 本地验证

- [x] `uv run python -m unittest tests.test_llm_fallback_smoke_script tests.test_llm_acceptance_record_generator tests.test_llm_provider_acceptance_template`
- [x] `uv run python scripts/smoke_daily_planner_fallback.py`
- [x] `uv run python scripts/verify_local.py --smoke llm-fallback`
- [x] `uv run python scripts/verify_local.py --planner-eval-policy`
- [x] `git diff --check`

---

## 9. 风险与边界

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| fallback smoke 被误解为真实 provider smoke | 验收含义混淆 | 文档说明该脚本不发网络，只验证失败路径 |
| generator 强制 fallback JSON 后旧命令失败 | 使用者需要更新命令 | README / TEMPLATE / 测试同步新增 `--fallback-json` |
| smoke 依赖本地开发数据库 | 无 DB 时无法运行 | 不进入默认 CI，只作为显式验收 smoke |

---

## 10. Review

### 自查结论

- 符合 Chronos “核心闭环不能依赖 LLM 成功”的约束。
- 没有改变用户可见 Today 复杂度。
- 没有让 LLM 获得写业务表权限。
- acceptance record 的安全判断更严格：没有 fallback 证据不能 Accepted。

### 后续建议

- 已在后续 [P2 LLM Acceptance Dry Run](./2026-05-17-p2-llm-acceptance-dry-run.md) 中补充真实 provider acceptance dry-run 文档和生成脚本，展示四份 JSON 如何串成一份最终验收记录。

---

## 11. 变更记录

| 日期 | 变更 | 文件 | 说明 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 fallback smoke | `scripts/smoke_daily_planner_fallback.py` | 不发网络，验证 provider failure fallback |
| 2026-05-17 | acceptance generator 接入 fallback JSON | `scripts/generate_llm_acceptance_record.py` | 缺失 Blocked，失败 Rejected |
| 2026-05-17 | 补测试 | `tests/test_llm_fallback_smoke_script.py`、`tests/test_llm_acceptance_record_generator.py` | 证据 payload 与验收判断 |
| 2026-05-17 | 更新文档 | README / Engineering / LLM / Acceptance | 运行入口和验收约束 |
