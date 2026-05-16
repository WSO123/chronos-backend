# Iteration: P3 Delivery Attempt Cleanup

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 `reminder.cleanup_delivery_attempts` worker，按 retention window 清理旧 ReminderDeliveryAttempt，避免 delivery attempt 表长期增长，同时不删除 Reminder 主记录。

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

上一轮新增 ReminderDeliveryAttempt 后，delivery 状态具备了可追踪性。但 attempts 属于运行观测数据，如果没有清理机制，长期会持续增长。P3 先补轻量 cleanup worker，为后续真实 provider 和调度计划提供维护出口。

### 目标

- 新增 `cleanup_delivery_attempts` service method。
- 新增 Celery task `reminder.cleanup_delivery_attempts`。
- 只删除超过 retention window 的 delivery attempts。
- Scheduler plan 纳入 cleanup task。

### 非目标

- 不删除 Reminder。
- 不清理 ActivityEvent / SyncRun。
- 不做复杂归档。
- 不做自动 Celery Beat wiring。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder Dispatch -> Delivery Attempts -> Cleanup Worker
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

清理 worker 是后台维护能力，不增加用户可见复杂度，也不改变提醒语义。

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
| Cleanup service | 删除旧 attempts | Must | retention_days |
| Cleanup worker | Celery task JSON-ready | Must | `reminder.cleanup_delivery_attempts` |
| Clamp 参数 | retention_days / limit 范围保护 | Must | 1..365 / 1..1000 |
| Scheduler plan | 纳入调度契约 | Should | daily |

### 用户故事

```text
作为后端开发者，
我希望 delivery attempts 有清理 worker，
以便提醒投递观测数据不会无限增长。
```

```text
作为 Chronos 用户，
我希望系统维护能力在后台安静运行，
以便产品保持轻盈可靠，而不增加可见复杂度。
```

### 主要流程

```text
reminder.cleanup_delivery_attempts
-> compute cutoff
-> select old attempts
-> delete attempts only
-> return deleted_count
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

无。

### 事件变更

无。

### API 变更

无 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `reminder.cleanup_delivery_attempts` | 清理旧 delivery attempts |

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

说明：本轮是维护 worker，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 旧 attempts 会被删除。
- [x] retention window 内 attempts 不删除。
- [x] Reminder 主记录不删除。
- [x] worker 返回 JSON-ready payload。
- [x] Scheduler plan 包含 cleanup task。

### 数据验收

- [x] 不新增模型或迁移。
- [x] 只删除 ReminderDeliveryAttempt。

### 体验验收

- [x] 不增加用户可见复杂度。
- [x] 不改变 Reminder Center 行为。

---

## 8. 测试计划

### 单元测试

- [x] cleanup deletes old attempts only。
- [x] worker JSON-ready result。
- [x] scheduler plan includes cleanup。

### API 测试

- [x] scheduler API includes cleanup task。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 误删 Reminder | 用户提醒丢失 | 只 query/delete ReminderDeliveryAttempt |
| retention 太短 | 调试信息不足 | 默认 30 天，参数可调 |
| 清理过大批量 | DB 压力 | limit 默认 500，上限 1000 |

### 关键取舍

- 取舍 1：先物理删除 attempts，不做归档。
- 取舍 2：不新增 HTTP API，只通过 worker 暴露。
- 取舍 3：纳入 scheduler contract，但不启动定时器。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 默认 retention 30 天 | 保留短期排障数据 | 长期数据需另行归档 |
| 2026-05-17 | Cleanup 不删除 Reminder | 保护提醒主语义 | 仅清理观测数据 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 cleanup service/worker | `app/services/reminder_service.py` / `app/workers/tasks.py` | delivery attempts |
| 2026-05-17 | Scheduler plan 纳入 cleanup | `app/services/scheduler_service.py` | daily |
| 2026-05-17 | 补测试 | Reminder / Scheduler tests | service / worker / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | cleanup worker |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_scheduler_services tests.test_scheduler_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] Celery Beat 实际每日运行。

### 已知问题

- 当前没有归档，超过 retention 的 attempts 会物理删除。

---

## 13. 后续迭代建议

- Celery Beat config generation from scheduler plan。
- Reminder read/seen state。
- P3 stabilization review。
