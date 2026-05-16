# Iteration: P3 Reminder Center Foundation

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

建立 Reminder Center 的基础后端能力：提醒模型、列表、手动创建和 dismiss，为后续自动执行提醒、截止提醒和推送 worker 提供承接层。

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

P3 信息架构中 Notification / Reminder 作为执行提醒、截止提醒和后续小组提醒入口。当前还没有提醒数据模型，因此无法承接自动提醒 worker 或前端 Reminder Center。

### 目标

- 新增 `Reminder` 模型和迁移。
- 支持 `GET /reminders` 读取提醒中心。
- 支持 `POST /reminders` 手动创建提醒。
- 支持 `POST /reminders/{id}/dismiss` 关闭提醒。

### 非目标

- 不做真实 push/email 发送。
- 不做自动生成提醒。
- 不接系统通知权限。
- 不改变 Task / Goal / Today 状态。

---

## 3. 产品约束对齐

### 核心路径

```text
Today Header -> Reminder Center
Task / Goal -> Reminder
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [x] Goals
- [ ] AI Agent

### 产品人格

Reminder Center 是安静的提醒入口，不制造压力。当前只做可见、可关闭的提醒记录，不做强打扰推送。

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
| Reminder model | 提醒记录 | Must | scheduled / dismissed |
| Reminder list API | Reminder Center 列表 | Must | scheduled_count / overdue_count |
| Create reminder API | 手动创建提醒 | Must | 可关联 Task 或 Goal |
| Dismiss reminder API | 用户关闭提醒 | Must | 不删除记录 |

### 用户故事

```text
作为 Chronos 用户，
我希望能看到和关闭提醒，
以便提醒帮助我开始行动，而不是变成不可控的压力。
```

```text
作为后端开发者，
我希望自动提醒 worker 有统一的提醒模型，
以便后续执行提醒、截止提醒和小组提醒都能复用。
```

### 主要流程

```text
POST /reminders
-> validate task / goal ownership
-> create scheduled reminder
-> GET /reminders
-> POST /reminders/{id}/dismiss
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
  id
  user_id
  task_id
  goal_id
  title
  message
  reminder_type
  status
  scheduled_for
  channel
  source
  dismissed_at
  sent_at
  metadata
}
```

### 状态机变更

```text
scheduled -> dismissed
```

预留：

```text
scheduled -> sent
scheduled -> canceled
```

### 事件变更

无。当前 Reminder Center 是独立承接层，不写 ActivityEvent，避免提醒操作污染执行行为时间线。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/reminders` | 提醒列表 | query `status`, `limit`, `offset` | `ReminderListResponse` |
| POST | `/api/v1/reminders` | 创建提醒 | `ReminderCreate` | `ReminderResponse` |
| POST | `/api/v1/reminders/{id}/dismiss` | 关闭提醒 | - | `ReminderResponse` |

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

说明：本轮不做 AI 自动提醒生成。

---

## 7. 验收标准

### 功能验收

- [x] 可创建 scheduled reminder。
- [x] 可读取 Reminder Center 列表。
- [x] 可 dismiss reminder。
- [x] 可统计 scheduled / overdue。

### 数据验收

- [x] task / goal 关联必须属于当前用户。
- [x] 一个 reminder 最多关联一个 task 或 goal。
- [x] user isolation 正确。

### 体验验收

- [x] 不真实推送。
- [x] 不改变 Task / Goal 状态。
- [x] Today 首屏只需要展示入口，不承载完整列表。

---

## 8. 测试计划

### 单元测试

- [x] create / list / dismiss。
- [x] overdue count。
- [x] owner validation。
- [x] user isolation。

### API 测试

- [x] create / list / dismiss。
- [x] user isolation。
- [x] cross-user task rejected。

### 集成测试

- [x] Alembic SQL 生成。
- [x] 真实 DB upgrade。
- [x] 全量测试。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 提醒变成压力源 | 违背产品人格 | 当前支持 dismiss，不做强推送 |
| 过早做推送系统 | P3 复杂度膨胀 | 本轮只做数据底座 |
| 和 ActivityEvent 边界混乱 | 行为时间线噪声 | Reminder 暂不写 ActivityEvent |

### 关键取舍

- 取舍 1：先做 Reminder Center，不做通知发送。
- 取舍 2：Reminder 可关联 Task / Goal，但不改变它们。
- 取舍 3：状态使用字符串，避免早期频繁扩 enum。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 Reminder 模型 | P3 自动提醒需要承接层 | 后续 worker 可复用 |
| 2026-05-17 | 不写 ActivityEvent | 提醒中心不是执行行为本身 | 行为时间线保持清晰 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增模型和迁移 | `app/models/reminder.py`, `alembic/versions/20260517_0012_reminders.py` | reminder |
| 2026-05-17 | 新增 service/API/schema | `app/services/reminder_service.py`, `app/api/v1/reminders.py`, `app/schemas/reminders.py` | reminder center |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py`, `tests/test_reminder_api.py` | service / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | Reminder API 合同 |

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

- [ ] 自动提醒生成。
- [ ] push / email 真实发送。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Reminder worker：按 due scheduled reminders 标记 sent，并返回待发送列表。
- Deadline reminder generator：基于 Task / Goal deadline 生成提醒。
- Settings 通知偏好细化。
