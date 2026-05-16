# Iteration: P3 Deadline Reminder Generator

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

基于 Task / Goal deadline 生成 `deadline` 类型 reminders，为截止提醒提供自动生成底座，但不发送通知、不改变任务或目标状态。

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

Reminder Center 和 due dispatch worker 已完成，但提醒仍需手动创建。P3 中截止提醒是核心提醒能力之一，因此本轮补一个可重复运行、幂等的 deadline reminder generator。

### 目标

- 基于未完成 Task deadline 生成 reminder。
- 基于 active Goal deadline 生成 reminder。
- 避免重复生成同一 entity / scheduled_for 的 reminder。
- 新增 Celery task `reminder.generate_deadline`。

### 非目标

- 不发送通知。
- 不做 AI 自动判断。
- 不改变 Task / Goal / Today 状态。
- 不生成执行提醒。

---

## 3. 产品约束对齐

### 核心路径

```text
Task / Goal Deadline -> Reminder -> Reminder Center
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

Deadline reminder 只生成温和提醒，帮助用户看见截止风险，不强制打断或重排。

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
| Task deadline reminders | 未完成任务生成 deadline reminder | Must | active / postponed / in_focus |
| Goal deadline reminders | active goal 生成 deadline reminder | Must | P2 Goals 承接 |
| Idempotency | 重复运行不重复生成 | Must | entity + scheduled_for |
| Worker task | Celery task 返回 JSON-ready payload | Must | `reminder.generate_deadline` |

### 用户故事

```text
作为 Chronos 用户，
我希望临近截止的任务和目标能自动出现在提醒中心，
以便我不会漏掉重要事项，但也不会被强制重排今天。
```

```text
作为后端开发者，
我希望 deadline reminder generator 可重复运行且幂等，
以便后续定时调度不会制造重复提醒。
```

### 主要流程

```text
reminder.generate_deadline
-> find due Task / Goal in window
-> skip existing deadline reminder
-> create scheduled reminder
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。新生成 reminder 初始状态为 `scheduled`。

### 事件变更

无。

### API 变更

无 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `reminder.generate_deadline` | 生成 deadline reminders |

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

说明：本轮是规则 generator，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 未完成 Task deadline 可生成 reminder。
- [x] active Goal deadline 可生成 reminder。
- [x] 已完成 / archived task 不生成 reminder。
- [x] 重复运行不重复生成。
- [x] worker 返回 JSON-ready payload。

### 数据验收

- [x] reminder 关联 task_id 或 goal_id。
- [x] source=`worker`、reminder_type=`deadline`。
- [x] scheduled_for 使用用户时区的 reminder hour 后转 UTC。

### 体验验收

- [x] 不发送通知。
- [x] 不改变 Task / Goal / Today 状态。
- [x] 提醒文案温和、可行动。

---

## 8. 测试计划

### 单元测试

- [x] task + goal deadline generation。
- [x] idempotency。
- [x] completed task ignored。
- [x] worker JSON-ready result。

### API 测试

- [x] 复用 Reminder Center API 测试。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 重复生成提醒 | 用户被打扰 | entity + scheduled_for 幂等检查 |
| 截止提醒改变计划 | Today 复杂化 | 只生成 Reminder，不 replan |
| 提醒过早智能化 | 难解释 | 固定 deadline window + reminder hour |

### 关键取舍

- 取舍 1：先规则生成，不做 AI 判断。
- 取舍 2：只生成 scheduled，不发送。
- 取舍 3：幂等用查询约束，不新增索引迁移。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Deadline generator 覆盖 Task 和 Goal | P3 需要截止提醒入口 | Reminder Center 能承接截止风险 |
| 2026-05-17 | 不自动 replan | 提醒不等于调度 | 用户保留控制感 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 generator service | `app/services/reminder_service.py` | deadline reminders |
| 2026-05-17 | 新增 worker task | `app/workers/tasks.py` | Celery |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py` | service / worker |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | deadline generator |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_reminder_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 定时调度配置。
- [ ] 用户通知偏好细化。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Execution reminder generator：基于 Today 当前序列生成执行提醒。
- Notification settings 细化 channel 偏好。
- Delivery provider 抽象。
