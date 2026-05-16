# Iteration: P3 Notification Delivery Provider

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 reminder dispatch 增加 notification delivery provider 抽象，让 `in_app` 能被明确送达 Reminder Center，而未配置的 `push` / `email` 不再被误标记为 sent。

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

`reminder.dispatch_due` 已能扫描 due reminders，但此前会直接把所有 due reminder 标记为 `sent`。在 P3 通知偏好支持 `push` / `email` channel 后，如果没有 provider 抽象，外部 channel 会出现“未真实发送却被标记 sent”的数据语义问题。

### 目标

- 新增 notification delivery provider registry。
- `in_app` provider 代表送达 Reminder Center，可标记 `sent`。
- 未配置的 `push` / `email` provider 返回 skipped，保持 reminder 为 `scheduled`。
- dispatch 结果返回 delivery_results，便于后续观测。

### 非目标

- 不接真实 push / email 服务。
- 不新增 delivery attempt 持久化表。
- 不做重试策略。
- 不改变 reminder generator 逻辑。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder -> Dispatch Worker -> Delivery Provider -> Reminder Center / External Channel
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

本轮避免把未真实发送的通知伪装成已发送，保护系统可信度。Chronos 可以聪明地提醒，但必须诚实地表达提醒状态。

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
| Delivery provider registry | 按 channel 分发 delivery | Must | provider abstraction |
| In-app provider | `in_app` 标记 sent | Must | Reminder Center 内送达 |
| Unconfigured provider | push/email skipped | Must | 不假装发送 |
| Dispatch result | 返回 delivery_results | Must | 可观测 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统只在确实送达提醒时标记已发送，
以便我能信任提醒中心里的状态。
```

```text
作为后端开发者，
我希望 dispatch worker 通过 provider 抽象发送提醒，
以便后续接入 push / email 时不改动 Reminder 核心状态机。
```

### 主要流程

```text
reminder.dispatch_due
-> find due scheduled reminders
-> build delivery request
-> provider.deliver
-> sent: mark sent
-> skipped: keep scheduled
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
scheduled --in_app delivered--> sent
scheduled --push/email unconfigured--> scheduled
```

### 事件变更

无。

### API 变更

无 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `reminder.dispatch_due` | 扫描 due reminders 并通过 provider 决定 sent / skipped |

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

说明：本轮是 provider abstraction，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] in_app due reminder 会标记 sent。
- [x] push/email 未配置时返回 skipped。
- [x] skipped reminder 保持 scheduled。
- [x] worker 返回 JSON-ready delivery_results。

### 数据验收

- [x] sent_at 只在 sent 时写入。
- [x] dispatch 返回 sent_count 和 skipped_count。
- [x] 不新增持久化表，避免过早复杂化。

### 体验验收

- [x] 不接真实外部通知。
- [x] 不误标记外部 channel 为已发送。
- [x] Reminder Center 状态更可信。

---

## 8. 测试计划

### 单元测试

- [x] in_app dispatch marks sent。
- [x] email dispatch skipped when provider unconfigured。
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
| skipped reminder 一直 due | 后续重复扫描 | 后续补 retry / cooldown 策略 |
| 无 delivery attempt 表 | 历史观测有限 | 当前先返回 payload，不扩大模型 |
| provider 过早复杂化 | P3 变重 | 只保留 registry + in_app + unconfigured |

### 关键取舍

- 取舍 1：`in_app` 视为送达 Reminder Center，可标记 sent。
- 取舍 2：未配置外部 provider 不标记 sent。
- 取舍 3：先不持久化 delivery attempt。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | in_app provider 使用 Reminder Center 语义 | 当前无真实系统通知 | 能保持 P3 轻量 |
| 2026-05-17 | push/email unconfigured 返回 skipped | 避免虚假发送状态 | 后续需要 retry / provider 配置 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 notification provider registry | `app/providers/notifications.py` | in_app / unconfigured |
| 2026-05-17 | dispatch 走 provider | `app/services/reminder_service.py` | sent / skipped |
| 2026-05-17 | 补测试 | `tests/test_reminder_services.py` | service / worker |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | delivery provider |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 push provider。
- [ ] 真实 email provider。
- [ ] delivery retry / cooldown。

### 已知问题

- skipped 的 external reminders 会在下一次 dispatch 中再次被扫描，后续应补 retry/cooldown 或 delivery attempt 表。

---

## 13. 后续迭代建议

- Reminder delivery attempt / retry cooldown。
- Reminder Center pending count for Today Header。
- Scheduler plan for generator / dispatch worker frequency。
