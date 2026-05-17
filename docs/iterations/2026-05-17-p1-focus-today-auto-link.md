# Iteration: P1 Focus Today Auto Link

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Focus start 在未显式传入 `daily_plan_item_id` 时自动绑定当前 Today 中的同一任务，避免 Task、Today、Focus、Report 的状态和时长统计分叉。

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

P1 主线中，Focus 是从 Task Detail 进入执行态的二级页。Task Detail 已经返回 `today_context.daily_plan_item_id`，但 Focus API 允许不传 `daily_plan_item_id`。如果任务本来就在当前 Today 中，前端漏传该字段时，完成 Focus 会更新 Task 和 FocusSession，Daily Report 也会统计 FocusSession，但 Today 的 `focus_minutes` 无法累加，造成用户看到的执行结果不一致。

### 目标

- Focus start 在未传 `daily_plan_item_id` 时，自动查找当前 active Today plan 中的同一 Task。
- 自动绑定后，Focus complete / interrupt / postpone 继续走既有 Today item 同步逻辑。
- 保持 Focus API 简洁，不要求前端为防错补复杂逻辑。

### 非目标

- 不新增 Focus 页面能力。
- 不做 pause / resume。
- 不引入提醒、健康、社交等 P3/P4 能力。
- 不引入 LLM。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [ ] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

- 轻盈：前端可以继续传最少必要字段，后端补齐一致性。
- 克制：只自动绑定当前 Today 中已经存在的同一任务，不创建计划、不改排序。
- 可信赖：Focus 完成后的 Today 进度、Focus 时长、Daily Report 指标一致。
- 不施压：没有增加用户确认步骤。

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
| Focus auto link Today item | 未传 `daily_plan_item_id` 时自动绑定当前 Today item | Must | P1 状态一致性 |
| Today progress sync | 自动绑定后完成 Focus 能更新 Today `completed_count` / `focus_minutes` | Must | 复用既有逻辑 |
| API contract note | 明确字段可选但建议传入 | Should | 前端联调 |

### 用户故事

```text
作为从 Task Detail 进入 Focus 的用户，
我希望完成专注后 Today 进度和复盘数据自然同步，
以便我不需要理解底层 item id 也能获得一致反馈。
```

```text
作为前端开发者，
我希望 Focus API 在遗漏 daily_plan_item_id 时能自动绑定当前 Today item，
以便减少联调出错导致的状态分叉。
```

### 主要流程

```text
GET /today
-> GET /tasks/{task_id}
-> POST /focus-sessions { task_id }
-> 后端查找当前 Today item 并自动绑定
-> POST /focus-sessions/{id}/complete
-> Task completed + DailyPlanItem completed + Today focus_minutes updated
-> Daily Report 汇总 FocusSession
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无新增状态。自动绑定后继续复用既有状态流转：

```text
Task.active / postponed -> in_focus -> completed / active / postponed
FocusSession.active -> completed / interrupted / postponed
DailyPlanItem.planned / postponed -> completed / planned / postponed
```

### 事件变更

无新增事件，继续使用：

- `FOCUS_SESSION_STARTED`
- `FOCUS_SESSION_COMPLETED`
- `FOCUS_SESSION_INTERRUPTED`
- `FOCUS_SESSION_POSTPONED`
- `TASK_COMPLETED`
- `TASK_POSTPONED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/focus-sessions` | 开始 Focus | `daily_plan_item_id` 可为空 | 若自动绑定，响应返回绑定后的 `daily_plan_item_id` |

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

- [x] 任务存在于当前 Today 时，不传 `daily_plan_item_id` 也能启动 Focus 并自动绑定。
- [x] 自动绑定后 complete Focus 会更新 Task、DailyPlanItem、DailyPlan progress。
- [x] API 响应返回自动绑定后的 `daily_plan_item_id`。

### 数据验收

- [x] FocusSession 保存 `daily_plan_item_id`。
- [x] Today `completed_count` 正确增加。
- [x] Today `focus_minutes` 正确累加。
- [x] Report 继续从 FocusSession 汇总，不依赖前端传参。

### 体验验收

- [x] 前端推荐传 `today_context.daily_plan_item_id`，但漏传不会让主线状态分叉。
- [x] 没有新增用户操作负担。

---

## 8. 测试计划

### 单元 / API 测试

- [x] `tests.test_focus_services`
- [x] `tests.test_focus_api`
- [x] `tests.test_report_me_services`
- [x] `tests.test_report_me_api`

### Smoke

- [x] `scripts/verify_local.py --smoke p1-bearer-capture`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 自动绑定错误日期的 Today item | Today 统计错乱 | 只查询用户当前日期的 active Today plan |
| 前端以为可完全不传 item id | 某些非当前 Today 任务不会绑定 | 文档仍建议优先传 Task Detail 的 `today_context.daily_plan_item_id` |

### 关键取舍

- 取舍 1：自动绑定只对当前 active Today 生效，不跨日期查找。
- 取舍 2：不在 Focus start 中创建 Today plan，避免 Focus 成为隐式调度入口。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Focus start 自动绑定当前 Today item | 防止 P1 执行闭环状态分叉 | 前端漏传 item id 时仍能保持一致 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 暴露当前 Today item 查找方法 | `app/services/planning_service.py` | 不创建、不刷新 plan |
| 2026-05-17 | Focus start 自动绑定 Today item | `app/services/focus_service.py` | 仅在未传 item id 时触发 |
| 2026-05-17 | 补充状态一致性测试 | `tests/test_focus_services.py`, `tests/test_focus_api.py` | 覆盖 service 和 API |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_focus_services tests.test_focus_api tests.test_report_me_services tests.test_report_me_api`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer-capture`
- [x] `git diff --check`

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 继续检查 Daily Report 与 Today 在完成 / 延后 / 中断后是否需要显式返回一致性摘要，避免前端重复计算。
- 检查 Task Detail 的 `today_context` 在 Today revision 变化后是否总是指向最新 current item。
