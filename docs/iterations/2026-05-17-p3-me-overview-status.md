# Iteration: P3 Me Overview Status

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

在 Me Overview 中加入 P3 数据接入和提醒的轻量入口状态，让 Me 能收敛自然生长模块，但不变成复杂仪表盘。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

产品信息架构中 Me 收敛个人信息、数据反馈、洞察、Energy、Reports 和 Settings。P3 数据接入和 Reminder Center 已具备独立 API，但 Me Overview 仍只返回 P1/P2 基础状态，缺少进入这些二级模块的轻量信号。

### 目标

- Me Overview 增加 `data_sources` 摘要。
- Me Overview 增加 `reminders` 摘要。
- 摘要只返回 counts，不返回连接列表、sync run 列表或 reminder 列表。
- 保持用户隔离。

### 非目标

- 不把 Me 做成 dashboard。
- 不返回 Energy Dashboard 明细。
- 不返回完整 Reminder Center。
- 不触发同步或提醒派发。

---

## 3. 产品约束对齐

### 核心路径

```text
Me -> Data Source / Reminder Entry Status
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [x] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Me 只展示“入口级状态”，把复杂列表留在二级页，符合轻盈、克制和清澈的体验。

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
| Data source status | Me Overview 返回 connected / sync_enabled / attention counts | Must | 入口摘要 |
| Reminder status | Me Overview 返回 pending / unseen / due counts | Must | 入口摘要 |
| Tests | service / API 测试 | Must | 用户隔离 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Me 中看到数据接入和提醒是否有需要关注的状态，
以便我可以进入对应二级页处理，而不是被完整列表打扰。
```

```text
作为前端开发者，
我希望 Me Overview 给出 P3 模块入口摘要，
以便 Me 页面不用额外请求多个底层接口才能展示入口状态。
```

### 主要流程

```text
GET /me/overview
-> existing profile / today / reports / insights
-> add data source counts
-> add reminder counts
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/me/overview` | Me 聚合入口 | `today?` | 增加 `data_sources` / `reminders` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本轮只读聚合，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] Me Overview 返回 `data_sources.connected_count`。
- [x] Me Overview 返回 `data_sources.attention_count`。
- [x] Me Overview 返回 `reminders.pending_count`。
- [x] Me Overview 返回 `reminders.unseen_count`。
- [x] Me Overview 返回 `reminders.due_count`。
- [x] 不返回完整数据源或提醒列表。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 schema。
- [x] 用户隔离正确。

### 体验验收

- [x] Me 保持轻量入口，不变成复杂 dashboard。
- [x] P3 模块可以自然收敛到 Me。

---

## 8. 测试计划

### 单元测试

- [x] me service overview P3 status。

### API 测试

- [x] me overview P3 status。

### 集成测试

- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Me Overview 膨胀 | 页面变成 dashboard | 只返回 counts |
| 多 service 聚合增加耦合 | Me service 依赖 P3 service | 仅依赖只读 summary 方法 |
| due count 使用当前时间 | 测试可能不稳定 | 测试使用过去时间创建提醒 |

### 关键取舍

Me Overview 不展示 P3 模块明细，只负责告诉用户是否值得进入二级页。

---

## 10. Review 记录

### 自检结论

- 与 Me 信息架构一致。
- 与产品人格一致：轻量、收敛、不喧闹。
- 与工程规范一致：页面聚合接口由 service 组织，前端不拼多个底层资源。

### 后续建议

- Energy Dashboard 可在后续以同样方式加入入口级状态，但不要返回完整趋势。
