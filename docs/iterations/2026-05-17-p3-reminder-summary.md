# Iteration: P3 Reminder Summary

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Reminder Summary 接口，为 Today Header 的提醒入口提供 pending / due 数字和下一条提醒，避免 Today 首屏展开完整 Reminder Center。

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

产品信息架构中 Reminder 入口位于 Today Header，但设计约束要求 Today 不能变成复杂驾驶舱。因此前端需要一个轻量 summary，而不是为了显示一个数字加载完整提醒列表。

### 目标

- 新增 `GET /api/v1/reminders/summary`。
- 返回 pending / due / execution / deadline counts。
- 返回下一条 scheduled reminder。
- 保持用户隔离，只统计当前用户 scheduled reminders。

### 非目标

- 不新增 unread 状态。
- 不展开完整 Reminder Center。
- 不改变 Reminder dispatch / generator。
- 不新增数据库表。

---

## 3. 产品约束对齐

### 核心路径

```text
Today Header -> Reminder Summary -> Reminder Center
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

Summary 只给用户一个轻量入口信号，让提醒可见但不抢走行动感。

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
| Pending count | 统计 scheduled reminders | Must | 当前用户 |
| Due count | 统计 scheduled_for <= now | Must | Header badge |
| Type counts | execution / deadline count | Should | 轻量区分 |
| Next reminder | 返回下一条 scheduled reminder | Must | 不展开列表 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Today Header 轻量看到是否有提醒，
以便我知道有没有需要注意的事项，但不会被完整列表打断。
```

```text
作为前端开发者，
我希望有一个 reminder summary 接口，
以便 Today Header 不必加载完整 Reminder Center。
```

### 主要流程

```text
GET /reminders/summary
-> load current user's scheduled reminders
-> compute counts
-> return next reminder
```

---

## 5. 后端设计

### 影响模块

- [x] API
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
| GET | `/api/v1/reminders/summary` | Today Header 提醒摘要 | `now` query | `ReminderSummaryResponse` |

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

说明：本轮是只读 summary，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] pending_count 只统计 scheduled。
- [x] due_count 按 now 判断。
- [x] next_reminder 返回最早 scheduled reminder。
- [x] 不统计其他用户 reminders。

### 数据验收

- [x] 不写入数据。
- [x] 不改变 reminder 状态。
- [x] 不新增模型。

### 体验验收

- [x] Today Header 可轻量展示提醒入口。
- [x] 完整提醒仍由 Reminder Center 承接。

---

## 8. 测试计划

### 单元测试

- [x] summary service counts。
- [x] user isolation。

### API 测试

- [x] GET /reminders/summary。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Summary 字段继续膨胀 | Today Header 变复杂 | 只保留数字和下一条 |
| 无 unread 状态 | 无法表达已读未读 | 当前 P3 先用 scheduled / due |
| Python 侧计数 | 数据量大时低效 | 后续必要时替换为 SQL aggregate |

### 关键取舍

- 取舍 1：summary 只读，不写 read/unread。
- 取舍 2：Today Header 不拿完整列表。
- 取舍 3：先用简单计数，保持接口稳定。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Summary 放在 `/reminders/summary` | 属于 Reminder Center 入口摘要 | Today 不直接承载提醒列表 |
| 2026-05-17 | 不引入 unread | 避免过早增加状态 | 后续可补 read/seen |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 summary service | `app/services/reminder_service.py` | read-only |
| 2026-05-17 | 新增 summary API/schema | `app/api/v1/reminders.py` / `app/schemas/reminders.py` | Today Header |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py` / `tests/test_reminder_api.py` | service / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | summary contract |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_reminder_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 前端 Today Header 接入。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Scheduler plan for reminder generator / dispatch worker。
- Delivery attempt cleanup worker。
- Reminder read/seen state。
