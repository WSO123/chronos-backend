# Iteration: P3 Reminder Snooze

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Reminder Snooze 操作，让用户可以把 pending reminder 温和地推迟，而不是只能 dismiss。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Reminder Center 已支持 seen、batch seen、dismiss 和 dispatch。用户面对一个暂时不想处理的提醒时，dismiss 太强，seen 又不改变提醒时间，因此需要一个符合“温和、不施压”的 snooze 操作。

### 目标

- 新增 `POST /api/v1/reminders/{reminder_id}/snooze`。
- 只允许 `scheduled` reminder snooze。
- 按 `minutes` 推迟 `scheduled_for`。
- 记录 snooze metadata。
- 不改变关联 Task / Goal / Today。

### 非目标

- 不新增 recurrence。
- 不支持 sent reminder 重新入队。
- 不接真实推送撤回。
- 不新增数据库字段。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder Center -> Snooze -> Gentle Reschedule
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

Snooze 给用户一个温和的“稍后”选择，不把提醒变成催促，也不让系统替用户重新规划今天。

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
| Snooze API | 推迟 pending reminder | Must | `minutes` 5..1440 |
| Snooze service | 校验状态与用户隔离 | Must | 只允许 scheduled |
| Metadata | 记录 snoozed_count / last_snoozed_at | Must | 不新增字段 |
| Tests | service / API 测试 | Must | 包含 sent 拒绝 |

### 用户故事

```text
作为 Chronos 用户，
我希望可以稍后再提醒，
以便我暂时不处理某件事时，不需要直接关闭提醒。
```

```text
作为前端开发者，
我希望 Reminder Center 有 snooze 操作，
以便提醒卡片能提供更温和的用户选择。
```

### 主要流程

```text
POST /reminders/{id}/snooze
-> ensure reminder belongs to user
-> ensure status=scheduled
-> scheduled_for = now + minutes
-> mark seen if needed
-> update metadata
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

```text
scheduled -> scheduled
sent / dismissed / canceled -> reject
```

### 事件变更

无。本轮将 snooze 轻量记录在 `reminder_metadata`，暂不新增 ActivityEvent。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/reminders/{reminder_id}/snooze` | 推迟 pending reminder | `{ "minutes": 15 }` | `ReminderResponse` |

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

说明：本轮不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] scheduled reminder 可以 snooze。
- [x] snooze 更新 `scheduled_for`。
- [x] snooze 记录 metadata。
- [x] snooze 会将未读 reminder 标记为 seen。
- [x] sent reminder 不能 snooze。
- [x] 跨用户 snooze 返回 404。

### 数据验收

- [x] 不新增 schema。
- [x] 不改变 Task / Goal / Today。
- [x] 不改变 reminder type / source / channel。

### 体验验收

- [x] Reminder Center 行为更温和。
- [x] 不让提醒变成强压迫式催促。

---

## 8. 测试计划

### 单元测试

- [x] reminder service snooze happy path / invalid state / isolation。

### API 测试

- [x] reminder snooze API。

### 集成测试

- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| sent reminder 重新 snooze 语义复杂 | 可能需要撤回已发送通知 | P3 先拒绝 sent reminder |
| metadata 记录不如字段易查询 | 不便统计 snooze 趋势 | P3 保持轻量，后续需要分析再升模型 |
| snooze 被当作 replan | 破坏 Today 边界 | 只改 reminder scheduled_for，不碰 DailyPlan |

### 关键取舍

本轮把 snooze 限定在 pending reminder 内，不做复杂 recurrence 或重新调度。

---

## 10. Review 记录

### 自检结论

- 与 Reminder Center 信息架构一致。
- 与产品人格一致：温和、克制、不施压。
- 与工程边界一致：service 校验状态，API 只调用 service。

### 后续建议

- 后续若要统计 snooze 习惯，可再引入 ActivityEvent 或专用字段。
