# Iteration: P3 Reminder Seen State

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Reminder `seen_at` 轻量已看状态和 `POST /api/v1/reminders/{id}/seen`，让 Reminder Center 可以清除未看数量，同时不改变 reminder 的 scheduled / sent / dismissed 主状态。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Reminder Summary 已能给 Today Header 提供 pending / due 数字，但还没有“用户已看过”的轻量状态。如果只用 dismiss 表达已看，会把“看过”和“不要再显示”混在一起。本轮补 `seen_at`，保持动作语义清晰。

### 目标

- Reminder 增加 `seen_at`。
- 新增 `POST /api/v1/reminders/{id}/seen`。
- Summary 返回 `unseen_count`。
- seen 操作幂等，不改变 reminder 主状态。

### 非目标

- 不新增复杂 read/unread 状态机。
- 不改变 dismiss 语义。
- 不自动标记 seen。
- 不做批量 seen。

---

## 3. 产品约束对齐

### 核心路径

```text
Today Header -> Reminder Summary -> Reminder Center -> Seen
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Seen 是一个安静的阅读状态，不催促、不打断，也不把提醒从用户视野中强制移除。

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
| seen_at column | Reminder 已看时间 | Must | nullable |
| Mark seen API | 标记已看 | Must | 幂等 |
| Summary unseen_count | Today Header 未看数 | Must | scheduled + seen_at null |
| Tests | service / API / migration | Must | 用户隔离 |

### 用户故事

```text
作为 Chronos 用户，
我希望看过提醒后能清除未看数字，
以便 Today Header 保持安静，但提醒本身不会被误删。
```

```text
作为前端开发者，
我希望 seen 和 dismiss 是两个动作，
以便 UI 能区分“已看过”和“不再显示”。
```

### 主要流程

```text
POST /reminders/{id}/seen
-> verify user ownership
-> set seen_at if empty
-> return reminder
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
Reminder {
  seen_at
}
```

### 状态机变更

无。`seen_at` 不改变 `status`。

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/reminders/{id}/seen` | 标记已看 | 无 | `ReminderResponse` |

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

说明：本轮是 Reminder Center 轻量状态，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 可标记 seen。
- [x] 重复 seen 幂等。
- [x] seen 不改变 reminder status。
- [x] 其他用户不能 mark seen。
- [x] summary 返回 unseen_count。

### 数据验收

- [x] `seen_at` nullable。
- [x] 新 reminder 默认 unseen。
- [x] migration 可应用。

### 体验验收

- [x] Today Header 可以清除未看数字。
- [x] Reminder 不会因为 seen 被移除。

---

## 8. 测试计划

### 单元测试

- [x] mark seen service。
- [x] summary unseen_count。

### API 测试

- [x] POST /reminders/{id}/seen。
- [x] create response includes seen_at。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic SQL / head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| seen 和 dismiss 混淆 | 用户误以为提醒消失 | 保持两套 API |
| unseen_count 规则膨胀 | Header 复杂 | 只统计 scheduled + seen_at null |
| 需要批量 seen | 操作成本 | 后续再补批量接口 |

### 关键取舍

- 取舍 1：只加 `seen_at`，不加 read status enum。
- 取舍 2：不自动 seen，交给前端显式调用。
- 取舍 3：先单条 seen，不做批量。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Seen 不改变 status | 保持 Reminder 主状态机稳定 | UI 可区分 seen / dismiss |
| 2026-05-17 | Summary 增加 unseen_count | 支持 Today Header 轻量数字 | 不展开列表 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 seen_at | Reminder model / Alembic | nullable |
| 2026-05-17 | 新增 seen API/service/schema | Reminders API / service / schema | idempotent |
| 2026-05-17 | Summary 增加 unseen_count | Reminder summary | Header |
| 2026-05-17 | 补测试 | Reminder service / API | seen state |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_reminder_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head --sql`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 前端批量 seen。

### 已知问题

- 暂无批量 mark seen 接口。

---

## 13. 后续迭代建议

- Batch reminder seen。
- P3 stabilization review。
- Calendar provider adapter hardening。
