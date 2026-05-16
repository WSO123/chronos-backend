# Iteration: P3 Reminder Delivery Attempts

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 ReminderDeliveryAttempt，用于记录 reminder dispatch 的送达尝试，并为未配置的 push / email provider 增加轻量 retry cooldown，避免外部 channel 被反复扫描。

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

Delivery provider 抽象已经避免 push / email 未配置时被误标记 sent，但 skipped reminder 会保持 scheduled。如果没有 attempt / cooldown，后续每次 dispatch 都会重复尝试同一条 external reminder，造成 worker 噪音。

### 目标

- 新增 `ReminderDeliveryAttempt` 持久化 delivery 尝试。
- sent / skipped 都记录 attempt。
- skipped 时设置 `next_retry_at`。
- cooldown 未到时 dispatch 返回 cooldown，不重复调用 provider。

### 非目标

- 不接真实 push / email provider。
- 不做复杂指数退避。
- 不改变 Reminder Center HTTP API。
- 不把 delivery attempt 暴露成独立列表接口。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder -> Dispatch Worker -> Delivery Attempt -> Reminder State
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

本轮让提醒系统更克制：没有可用外部 provider 时，不重复打扰、不伪装成功，只记录一次尝试并等待下一次合理重试。

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
| Delivery attempt model | 记录 sent / skipped delivery 尝试 | Must | 按 reminder |
| Retry cooldown | skipped 后 15 分钟内不重复 provider 调用 | Must | 轻量固定间隔 |
| Dispatch payload | 返回 cooldown_count / next_retry_at | Must | worker 可观测 |
| Migration | 新建 attempts 表 | Must | P3 delivery 底座 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统在外部通知不可用时不要反复尝试和制造噪音，
以便提醒能力保持克制、可靠。
```

```text
作为后端开发者，
我希望每次 reminder delivery 都有可追踪 attempt，
以便后续接入真实 provider、重试和排障时有稳定底座。
```

### 主要流程

```text
reminder.dispatch_due
-> find due scheduled reminders
-> check latest delivery attempt cooldown
-> provider.deliver
-> record attempt
-> sent: mark reminder sent
-> skipped: keep scheduled and set next_retry_at
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [x] Models
- [ ] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
ReminderDeliveryAttempt {
  user_id
  reminder_id
  channel
  provider
  status
  reason
  attempted_at
  next_retry_at
  metadata
}
```

### 状态机变更

```text
scheduled --in_app delivered--> sent
scheduled --external skipped--> scheduled + next_retry_at
scheduled --cooldown active--> scheduled
```

### 事件变更

无。

### API 变更

无 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `reminder.dispatch_due` | 返回 sent / skipped / cooldown delivery 结果 |

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

说明：本轮是 delivery persistence / cooldown，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] in_app sent 会记录 sent attempt。
- [x] email skipped 会记录 skipped attempt。
- [x] skipped attempt 设置 next_retry_at。
- [x] cooldown 内再次 dispatch 不重复调用 provider。
- [x] cooldown 过后可再次尝试并记录新 attempt。

### 数据验收

- [x] attempt 关联 user_id / reminder_id。
- [x] skipped reminder 保持 scheduled。
- [x] sent reminder 写入 sent_at。

### 体验验收

- [x] 不接真实外部通知。
- [x] 不重复打扰式尝试。
- [x] dispatch 结果可解释。

---

## 8. 测试计划

### 单元测试

- [x] sent attempt persisted。
- [x] skipped attempt persisted。
- [x] retry cooldown behavior。

### API 测试

- [x] 复用 Reminder Center API 测试。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic SQL / head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 固定 cooldown 不够智能 | 真实 provider 场景可能过粗 | 后续可升级为指数退避 |
| attempts 表增长 | 长期存储增加 | 后续补清理策略 |
| 未暴露 attempts API | 调试入口有限 | 当前 worker payload 已返回结果 |

### 关键取舍

- 取舍 1：固定 15 分钟 cooldown，先解决重复扫描噪音。
- 取舍 2：记录 attempt，但不新增前端列表。
- 取舍 3：不改变 Reminder 主状态机。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | skipped 保持 Reminder scheduled | 外部 provider 未来可能恢复 | Reminder Center 不丢提醒 |
| 2026-05-17 | 15 分钟固定 cooldown | 简单可解释 | 后续可替换成 retry policy |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 attempt model/migration | `app/models/reminder_delivery.py` / Alembic | delivery attempts |
| 2026-05-17 | dispatch 加 cooldown | `app/services/reminder_service.py` | next_retry_at |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py` | sent / skipped / cooldown |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | attempt semantics |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head --sql`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 provider retry。
- [ ] attempt 清理任务。

### 已知问题

- cooldown 固定为 15 分钟，后续接真实 provider 后应升级为可配置 retry policy。

---

## 13. 后续迭代建议

- Reminder Center pending count for Today Header。
- Scheduler plan for reminder generator / dispatch worker。
- Delivery attempt cleanup worker。
