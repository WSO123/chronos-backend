# Iteration: P3 Reminder Dispatch Worker Placeholder

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Reminder Center 增加 due reminder 扫描 worker，占位完成 `scheduled -> sent` 流转，并返回待发送 payload，但不接真实 push/email。

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

上一轮已建立 Reminder 数据模型和 Reminder Center API，但到期提醒还不会被 worker 消费。本轮补最小调度承接能力，为后续真实通知通道提供稳定输出。

### 目标

- 新增 `ReminderService.dispatch_due_reminders`。
- 新增 Celery task `reminder.dispatch_due`。
- 到期 scheduled reminders 标记为 `sent`。
- 支持按 channel 过滤。

### 非目标

- 不接真实推送、邮件或系统通知。
- 不自动生成 reminder。
- 不重试发送。
- 不改变 Task / Goal / Today 状态。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder Center -> dispatch due reminders -> sent payload
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

Worker 只是安静地推进提醒状态，不做强推送，不制造不可控打扰。

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
| Due scan | 扫描到期 scheduled reminders | Must | scheduled_for <= now |
| Mark sent | 标记 sent / sent_at | Must | 不真实发送 |
| Channel filter | 限定 in_app / push / email | Should | 后续通道复用 |
| Worker task | Celery task 返回 JSON-ready payload | Must | `reminder.dispatch_due` |

### 用户故事

```text
作为 Chronos 用户，
我希望到期提醒能进入一个稳定的发送流程，
以便后续提醒能准时出现，但不会突然变成不可控打扰。
```

```text
作为后端开发者，
我希望 due reminder worker 先返回结构化 payload，
以便后续接入 push/email 时不用重写提醒状态机。
```

### 主要流程

```text
reminder.dispatch_due
-> select scheduled reminders due before now
-> mark sent
-> return sent reminder payloads
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

```text
scheduled -> sent
```

### 事件变更

无。当前 worker 不写 ActivityEvent，避免提醒发送污染执行行为流。

### API 变更

无 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `reminder.dispatch_due` | 扫描并标记到期 reminders |

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

- [x] 到期 scheduled reminder 会标记为 sent。
- [x] 未到期 reminder 保持 scheduled。
- [x] dismissed / canceled / sent 不重复发送。
- [x] worker 返回 JSON-ready payload。

### 数据验收

- [x] `sent_at` 正确写入。
- [x] channel filter 生效。
- [x] 不改变 Task / Goal / Today 状态。

### 体验验收

- [x] 当前不真实推送。
- [x] 后续通知通道可以接返回 payload。

---

## 8. 测试计划

### 单元测试

- [x] dispatch due reminders。
- [x] channel filter。
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
| 未真实发送却标记 sent | 语义可能过早 | 文档明确当前是 dispatch placeholder |
| 推送通道复杂度提前进入 | P3 膨胀 | 只返回 payload，不接 provider |
| 重复发送 | 用户打扰 | 只扫描 `status=scheduled` |

### 关键取舍

- 取舍 1：先完成状态流转和 payload，不做外部通知。
- 取舍 2：不写 ActivityEvent。
- 取舍 3：channel filter 先保留，推送通道后续接入。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 `reminder.dispatch_due` | Reminder Center 需要 worker 承接 | 后续 push/email 可复用 |
| 2026-05-17 | 当前标记 sent 但不真实发送 | 保持 P3 轻量 | 后续需补 delivery provider |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 dispatch service | `app/services/reminder_service.py` | due scan |
| 2026-05-17 | 新增 worker task | `app/workers/tasks.py` | Celery |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py` | service / worker |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | Reminder worker |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_reminder_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 push/email provider。
- [ ] 定时调度配置。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Deadline reminder generator：基于 Task / Goal deadline 生成 scheduled reminders。
- Notification delivery provider 抽象。
- Settings 通知偏好细化。
