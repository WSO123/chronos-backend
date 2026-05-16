# Iteration: P3 Execution Reminder Generator

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

基于已有 Today active plan 的推荐执行序列生成 `execution` 类型 reminders，让提醒中心能承接“该开始下一件事了”的轻量提醒，但不创建计划、不重排、不发送通知。

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

Deadline reminder generator 已支持截止提醒，但 P3 自动提醒还缺少面向执行路径的提醒。Execution reminder 应该从 Today 已经生成的执行序列中轻量派生，提醒用户开始高价值或推荐任务，而不是重新做调度决策。

### 目标

- 基于已有 Today active plan 生成 execution reminders。
- 只选择 pinned / recommended 且仍为 planned 的 DailyPlanItem。
- 重复运行不重复生成同一 task / scheduled_for 的 reminder。
- 新增 Celery task `reminder.generate_execution`。

### 非目标

- 不 lazy create Today plan。
- 不 replan，不修改 DailyPlan / DailyPlanItem。
- 不发送 push / email。
- 不接入 AI 自动提醒策略。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Reminder -> Reminder Center -> Today / Focus
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [x] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Execution reminder 只做温和、克制的“开始提醒”，帮助用户顺着 Today 已有序列进入行动，不制造新的调度压力。

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
| Existing plan only | 只读取已有 Today active plan | Must | 无 plan 返回 no_plan |
| Candidate selection | 选择 pinned / recommended planned items | Must | 按 sort_order |
| Idempotency | 重复运行不重复生成 | Must | task + scheduled_for |
| Worker task | Celery task 返回 JSON-ready payload | Must | `reminder.generate_execution` |

### 用户故事

```text
作为 Chronos 用户，
我希望 Today 推荐序列中的关键任务能被温和提醒，
以便我更容易开始下一件事，但不会感觉系统在替我强行重排一天。
```

```text
作为后端开发者，
我希望 execution reminder generator 只消费已有计划且可重复运行，
以便后续定时调度不会产生隐式 replan 或重复提醒。
```

### 主要流程

```text
reminder.generate_execution
-> find existing active DailyPlan
-> select pinned / recommended planned items
-> skip existing execution reminders
-> create scheduled reminders
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
| `reminder.generate_execution` | 从已有 Today active plan 生成 execution reminders |

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

- [x] 无 Today active plan 时返回 `no_plan`，不创建 Today。
- [x] 有 Today active plan 时生成 execution reminders。
- [x] 只覆盖 pinned / recommended planned items。
- [x] 重复运行不重复生成。
- [x] worker 返回 JSON-ready payload。

### 数据验收

- [x] reminder 关联 task_id。
- [x] source=`worker`、reminder_type=`execution`。
- [x] scheduled_for 使用用户时区起始时间后转 UTC。
- [x] metadata 记录 daily_plan_id / daily_plan_item_id / section / sort_order。

### 体验验收

- [x] 不发送通知。
- [x] 不重排 Today。
- [x] 提醒文案温和、可行动。

---

## 8. 测试计划

### 单元测试

- [x] existing Today plan generation。
- [x] no plan does not create Today。
- [x] idempotency。
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
| 提醒生成隐式创建计划 | 用户不信任 AI 调度 | generator 只查询已有 active plan |
| 提醒太多 | 产生打扰感 | 默认 limit=3，且只选 pinned / recommended |
| 重复生成提醒 | Reminder Center 噪音 | task + scheduled_for 幂等检查 |

### 关键取舍

- 取舍 1：先规则生成，不做 AI 判断。
- 取舍 2：只生成 scheduled，不发送。
- 取舍 3：从 Today 序列派生提醒，不重新计算执行序列。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Execution reminder 只读取已有 Today active plan | 避免提醒系统偷偷接管调度 | 无 plan 时安全返回 no_plan |
| 2026-05-17 | 默认最多生成 3 条 | 保持提醒轻量 | 后续可接入偏好配置 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 generator service | `app/services/reminder_service.py` | execution reminders |
| 2026-05-17 | 新增 worker task | `app/workers/tasks.py` | Celery |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py` | service / worker |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | execution generator |

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
- [ ] 真实 delivery provider。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Notification settings / reminder preferences：限制 execution reminder 的时间、数量和 channel。
- Delivery provider abstraction：在不改变 Reminder 模型的前提下接入真实发送。
- Reminder Center unread / pending count：给 Today Header 提供轻量数字入口。
