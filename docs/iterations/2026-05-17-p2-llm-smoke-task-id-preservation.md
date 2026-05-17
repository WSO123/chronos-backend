# Iteration: P2 LLM Smoke Task ID Preservation

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

增强真实 provider smoke 输出，把 task id preservation 从隐式运行时校验变成结构化验收证据，供 LLM provider acceptance record 自动引用。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [LLM Provider Acceptance Template](../llm-provider-acceptance/TEMPLATE.md)
- [x] [P2 LLM Acceptance Record Generator](./2026-05-17-p2-llm-acceptance-record-generator.md)

### 背景

真实 provider smoke 已经会校验 provider 返回的 task ids 是否与 synthetic 输入一致。如果不一致，脚本会失败。但成功输出里没有把 expected / actual task ids 作为结构化字段返回，导致验收记录生成器只能留下“需要人工核对”的 checkbox。

Chronos 的 AI 边界要求 LLM 不直接改写业务实体。Task id preservation 是 Daily Planner Agent 接真实 provider 时最关键的硬约束之一，本轮把它变成可记录、可复查的证据。

### 目标

- `scripts/smoke_llm_provider.py` 输出 `expected_task_ids` 和 `output_task_ids`。
- 输出 `task_ids_preserved`、`task_id_set_preserved`、`task_count_preserved`。
- 输出 `missing_task_ids` 和 `unexpected_task_ids`。
- task id 不一致时，smoke 仍失败，但失败 JSON 保留 preservation 明细。
- `scripts/generate_llm_acceptance_record.py` 自动展示并使用这些字段。
- 更新真实 provider 验收文档和测试。

### 非目标

- 不调用真实 provider。
- 不改变 Daily Planner Agent prompt。
- 不改变 structured output schema。
- 不新增数据库表或 API。

---

## 3. 产品约束对齐

### 核心路径

```text
Daily Planner Agent -> Real Provider Smoke -> Task ID Preservation Evidence -> Acceptance Record
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

这轮不增加用户侧复杂度，而是加强后台可信度。Provider 可以参与编排解释，但不能改变任务身份和任务集合。

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
| Preservation summary | expected / actual task ids 对比 | Must | pure helper |
| Smoke output fields | 输出 preservation 明细 | Must | 成功路径 |
| Failed smoke evidence | task id 不一致时失败 JSON 仍带明细 | Must | 便于验收排障 |
| Acceptance rendering | 验收记录展示 task id preservation | Must | 自动勾选 |
| Docs update | 模板 / README / 架构 / 规范同步 | Should | 防漂移 |
| Tests | 覆盖 exact match、reorder、membership change、record rendering | Must | 不调用真实 provider |

### 用户故事

```text
作为验收负责人，
我希望真实 provider smoke 输出 expected / actual task ids，
以便确认 provider 没有改写、删除或新增任务。
```

```text
作为后端开发者，
我希望验收记录生成器能自动读取 task id preservation，
以便减少人工 checkbox 和主观判断。
```

```text
作为 Chronos 用户的代理人，
我希望 AI 只能建议排序与解释，
以便业务任务身份仍由系统保护。
```

### 主要流程

```text
run real provider smoke
-> collect output task ids
-> compare expected vs actual
-> output preservation summary
-> fail if exact order is not preserved
-> acceptance generator renders evidence
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

### Smoke 输出新增字段

```json
{
  "expected_task_ids": ["manual-smoke-task-1", "manual-smoke-task-2"],
  "output_task_ids": ["manual-smoke-task-1", "manual-smoke-task-2"],
  "task_ids_preserved": true,
  "task_id_set_preserved": true,
  "task_count_preserved": true,
  "missing_task_ids": [],
  "unexpected_task_ids": []
}
```

### 状态规则

- `task_ids_preserved=true`：exact order 保持一致。
- `task_id_set_preserved=true`：没有新增 / 删除 task id。
- `task_count_preserved=true`：任务数量保持一致。
- 任一 task id exact order 不一致时，真实 provider smoke 失败。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

- Agent 名称：Daily Planner Agent
- 输入对象：synthetic candidates
- 输出对象：DailyPlannerOutput + smoke evidence
- Pydantic schema：不变
- fallback 策略：不变
- 是否需要用户确认：不涉及用户确认

### LLM 安全边界

- [x] LLM 不直接写业务表。
- [x] task id 不一致会阻断 smoke。
- [x] failure payload 只包含 synthetic ids，不包含真实用户数据。
- [x] 真实 provider 调用仍必须显式 `--allow-real-llm`。

---

## 7. 验收标准

### 功能验收

- [x] exact match 时 `task_ids_preserved=true`。
- [x] reorder 时 `task_ids_preserved=false`，但 `task_id_set_preserved=true`。
- [x] membership change 时输出 missing / unexpected ids。
- [x] 验收记录生成器展示 preservation 字段。
- [x] 验收记录生成器根据 preservation 自动勾选 task id 检查。

### 数据验收

- [x] 不新增 migration。
- [x] 不写业务表。
- [x] 不调用真实 provider。
- [x] 不提交生成的验收实例。

### 体验验收

- [x] 真实 provider 验收记录减少人工核对项。
- [x] Today 首屏和用户体验不变。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_llm_provider_smoke_script`
- [x] `tests.test_llm_acceptance_record_generator`
- [x] `tests.test_llm_provider_acceptance_template`

### 集成测试

- [x] `scripts/verify_local.py --planner-eval --all-smoke`

### 手动验证

```bash
uv run python -m unittest tests.test_llm_provider_smoke_script tests.test_llm_acceptance_record_generator tests.test_llm_provider_acceptance_template
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| order 变化但集合不变 | Today 执行顺序可能被 provider 改写 | exact order 不一致直接失败 |
| failure JSON 泄露真实数据 | 安全风险 | smoke 使用 synthetic ids |
| 字段过多 | 验收记录变长 | 字段只出现在验收层，不进用户界面 |

### 关键取舍

- 取舍 1：exact order preservation 是硬约束，不只检查集合。
- 取舍 2：失败时也输出 preservation 明细，便于排障。
- 取舍 3：不改变 DailyPlannerOutput schema，避免为验收工具污染业务 schema。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | task ids exact order 不一致即失败 | Provider 不应重排 v1 输出 | 保护业务层排序权 |
| 2026-05-17 | 输出 set / count / missing / unexpected | 方便区分重排、删除、新增 | 验收记录更可诊断 |
| 2026-05-17 | 不改 structured output schema | 验收证据属于 smoke 层 | 业务 schema 保持稳定 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | smoke preservation helper | `scripts/smoke_llm_provider.py` | task id summary |
| 2026-05-17 | acceptance rendering | `scripts/generate_llm_acceptance_record.py` | 自动展示 / 勾选 |
| 2026-05-17 | smoke tests | `tests/test_llm_provider_smoke_script.py` | exact / reorder / membership |
| 2026-05-17 | generator tests | `tests/test_llm_acceptance_record_generator.py` | mismatch rendering |
| 2026-05-17 | docs update | LLM acceptance / guidelines / architecture | 验收口径 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_llm_provider_smoke_script tests.test_llm_acceptance_record_generator tests.test_llm_provider_acceptance_template`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未调用真实 provider。

### 已知问题

- fallback 检查仍是人工 checkbox，后续可以增加 synthetic fallback smoke 或 failure-path evidence。

---

## 13. 后续迭代建议

1. 为 Daily Planner Agent fallback 增加手动 / 自动 smoke evidence，减少验收记录中 fallback 人工核对。
2. 为 Today Strategy Detail 增加更清晰的 goal-aware explanation 文案，但仍不进入 Today 首屏。
3. 增加 planner eval 数值阈值 policy，例如 selected minutes、over capacity 和关键 score signal 的允许范围。
