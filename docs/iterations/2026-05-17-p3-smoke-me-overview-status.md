# Iteration: P3 Smoke Me Overview Status

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 Me Overview 的 P3 数据源和提醒入口状态纳入 P3 natural growth smoke，确保自然生长链路的端到端验证覆盖 Me 这个收敛入口。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P3 Frontend API Contract](../chronos-p3-frontend-api-contract.md)

### 背景

P3 已在 `/api/v1/me/overview` 增加 `data_sources` 和 `reminders` 入口摘要。此前 P3 smoke 覆盖数据源、Energy、外部 Capture、Reminder 和 Scheduler，但没有在端到端链路中验证 Me 的收敛入口。

### 目标

- P3 smoke 在数据源连接、提醒生成之后读取 Me Overview。
- 校验 Me Overview 的数据源连接数、attention 数、提醒 pending / unseen / due 数。
- 保持 smoke 只验证入口状态，不展开完整二级页。

### 非目标

- 不新增 API。
- 不新增业务模型。
- 不在 smoke 中直接写业务状态。
- 不把 Me Overview 当作完整数据源或提醒列表验证工具。

---

## 3. 产品约束对齐

### 核心路径

```text
Calendar / Email / Health -> Capture / Inbox / Energy
Reminder -> Me Overview status
Me -> Data Source / Reminder 二级入口
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [x] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Smoke 只要求 Me 暴露“有没有需要关注”的轻量状态，继续保持轻盈、克制、清澈。

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
| Me status smoke assertion | P3 smoke 校验 `/me/overview` 的 `data_sources` / `reminders` | Must | 端到端防回归 |
| README 更新 | 说明 P3 smoke 覆盖 Me 入口状态 | Should | 开发入口 |
| Engineering Guidelines 更新 | 验证梯度加入 Me 入口状态 | Should | 规范入口 |

### 用户故事

```text
作为后端开发者，
我希望 P3 smoke 能覆盖 Me 的自然生长入口状态，
以便后续改 Reminder 或 Data Source 时不会悄悄破坏 Me 首页契约。
```

```text
作为前端开发者，
我希望 smoke 明确验证 Me 只返回入口级 counts，
以便我可以放心用它展示二级页入口状态。
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [ ] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Scripts
- [x] Docs

### 主要流程

```text
P3 smoke
-> connect Health / Calendar / Email
-> import external item
-> create Today
-> generate execution reminder
-> GET /me/overview
-> assert data_sources + reminders counts
```

---

## 6. AI / LLM 影响

- [x] 不涉及 LLM。
- [x] 不涉及 Prompt。
- [x] 不涉及 AIJob 状态。

---

## 7. 验收标准

### 功能验收

- [x] P3 smoke 校验 `me_overview.data_sources.connected_count == 3`。
- [x] P3 smoke 校验 `attention_count == 0`。
- [x] P3 smoke 校验 `reminders.pending_count >= 1`。
- [x] P3 smoke 校验 `reminders.unseen_count >= 1`。
- [x] P3 smoke 校验 `reminders.due_count >= 1`。
- [x] Smoke 返回结果包含 Me 入口状态摘要，便于人工看结果。

### 体验验收

- [x] 只验证入口状态，不验证完整列表。
- [x] 不触发 sync、生成或 dispatch 的额外副作用。

---

## 8. 测试计划

- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Smoke 过重 | 本地验证变慢 | 复用既有 P3 smoke 数据，不新增外部依赖 |
| due count 时间不稳定 | 端到端偶发失败 | 在生成提醒后立即用同一个 `now` 前后窗口验证 |
| Me 被误解为列表接口 | 前端接入复杂化 | 文档明确完整列表仍走二级接口 |
