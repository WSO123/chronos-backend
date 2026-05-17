# Iteration: P1 Inbox Confirm Today Impact

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Task 型 Inbox item 被确认后，能够明确反馈它是否已滚动纳入已有 Today 计划，补强 `Capture -> Inbox -> Today` 的真实闭环。

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

Chronos 的 P1 主线是 `Capture -> Inbox -> Today -> Task Detail -> Focus -> Report`。此前 Inbox confirm 已经可以生成 Task / Goal，Today 也能在读取时同步任务状态，但 confirm 响应没有告诉调用方“这个新任务是否已经影响今日编排”。这会让前端只能靠下一次刷新猜测结果，不符合“清晰、可信赖”的产品人格。

### 目标

- Task 型 Inbox confirm 后，如果当天已有 active Today plan，系统自动生成一个 `SYSTEM_REFRESH` revision。
- confirm 响应返回 `today_impact`，说明是否存在 Today、是否刷新、任务是否进入当前计划。
- Goal 型 confirm 不影响 Today，保持 `today_impact=null`。
- 已 confirmed item 的重复 confirm 只返回当前 `today_impact`，不再次刷新计划。

### 非目标

- 不在 Inbox confirm 中偷偷创建 Today plan。
- 不引入提醒、日历、邮件等 P3 能力。
- 不引入新的 LLM Agent，也不让 AI 直接改变业务状态。
- 不做前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

- 轻盈：confirm 返回一段简短影响结果，不增加用户决策负担。
- 克制：没有 active Today 时不自动创建计划，仍由 Today 页面承担决策中心职责。
- 可信赖：前端可以明确展示或记录“新任务已进入今日编排 / 暂未进入今日编排”。
- 聪明但不炫耀：用 deterministic Planning Engine 刷新，不引入黑盒 AI 改写排序。

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
| Inbox confirm Today impact | Task confirm 时返回 Today 影响 | Must | P1 闭环 |
| Existing Today system refresh | 若已有 active Today plan，生成新 revision | Must | trigger=`system_refresh` |
| No hidden Today creation | 若没有 active Today plan，不创建计划 | Must | 保持 Today 为决策中心 |

### 用户故事

```text
作为每天从 Capture 添加任务的用户，
我希望确认任务后系统能告诉我它是否进入今日安排，
以便我清楚知道下一步是回 Today 执行，还是稍后让 Today 重新生成计划。
```

```text
作为前端调用方，
我希望 Inbox confirm 返回结构化 today_impact，
以便在不额外猜测的情况下更新 Today 或提示用户。
```

### 主要流程

```text
POST /captures
-> 生成 Inbox item
-> POST /inbox/{id}/confirm
-> 创建 Task
-> 若已有 active Today plan，Planning Engine 生成 system_refresh revision
-> 返回 today_impact
-> GET /today 可看到新 Task
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
InboxItem.pending / edited -> confirmed
DailyPlan.current_version N -> N+1 仅在已有 active Today plan 且确认 Task 时发生
```

### 事件变更

- `TASK_CREATED`
- `INBOX_ITEM_CONFIRMED`
- `DAILY_PLAN_SYSTEM_REFRESHED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/inbox/{item_id}/confirm` | 确认 Inbox item | - | 新增 `today_impact` |

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
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 没有 active Today plan 时，Task confirm 返回 `today_impact.plan_exists=false`。
- [x] 已有 active Today plan 时，Task confirm 返回 `replanned=true`，并生成新版本。
- [x] 重复确认已 confirmed item 时，返回 `replanned=false` 且 plan version 不变。
- [x] Goal confirm 返回 `today_impact=null`。

### 数据验收

- [x] Task 仍正常创建。
- [x] Inbox item 仍进入 confirmed。
- [x] active Today plan 只在已存在时刷新。
- [x] 新 Task 出现在刷新后的 Today sections 中。

### 体验验收

- [x] 调用方能清楚知道确认后的下一步。
- [x] 响应字段克制，不暴露复杂评分细节。
- [x] 核心流程不依赖 LLM。

---

## 8. 测试计划

### 单元 / API 测试

- [x] `tests.test_capture_inbox_api`
- [x] `tests.test_capture_inbox_services`
- [x] `tests.test_today_api`
- [x] `tests.test_today_services`

### Smoke

- [x] `scripts/smoke_p1_bearer_capture_loop.py`
- [x] `scripts/verify_local.py --smoke p1-bearer-capture`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Inbox confirm 自动刷新 Today 可能看起来像隐藏调度 | 用户可能不理解为什么 Today version 变化 | 仅在已有 active Today plan 时刷新，并返回 `today_impact.reason` |
| 没有 active Today plan 时不创建计划 | 新任务不会立刻显示 Today | 保持 Today 作为决策中心，避免 Inbox 变成隐式计划入口 |

### 关键取舍

- 取舍 1：选择 `SYSTEM_REFRESH` 而不是用户触发的 `REPLAN`，因为这是系统响应已确认输入，不是用户手动要求重新排序。
- 取舍 2：不把 score breakdown 放进 confirm response，避免把 Today 复杂度外溢到 Capture / Inbox。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Task confirm 只刷新已有 Today，不创建新 Today | 保持 Today 的决策中心边界 | 前端可根据 `plan_exists` 判断是否刷新 Today |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 Today impact 计算 | `app/services/planning_service.py` | 新增 `include_confirmed_task_from_inbox` |
| 2026-05-17 | Inbox confirm 返回影响结果 | `app/services/inbox_service.py`, `app/api/v1/inbox.py` | 保持原 `confirm_item` 兼容 |
| 2026-05-17 | 扩展响应 schema | `app/schemas/inbox.py` | 新增 `InboxConfirmTodayImpactResponse` |
| 2026-05-17 | 补充 API 测试 | `tests/test_capture_inbox_api.py` | 覆盖有 / 无 Today plan |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_capture_inbox_api`
- [x] `uv run python -m unittest tests.test_capture_inbox_services tests.test_today_api tests.test_today_services`
- [x] `uv run python scripts/smoke_p1_bearer_capture_loop.py`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer-capture`
- [x] `git diff --check`

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 继续补强 `Task Detail / Focus / Report` 的状态一致性，确保从 Today 进入 Focus 后，Task、DailyPlanItem、DailyReport 三者统计不分叉。
- 检查 Planning Engine 对新确认任务的排序解释是否足够清楚，必要时在 Strategy Detail 中增加“来自 Inbox 的新任务”信号，但不放入 confirm response。
