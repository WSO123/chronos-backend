# Iteration: P2 Goal Progress Feedback v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待补

---

## 1. 迭代摘要

把 Focus / Today 快速完成 / Daily Report / Goal Detail 中的执行结果回流成轻量目标推进反馈，让用户能看到“今天这次行动让哪个 Goal 前进了多少”。

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

上一轮 `Goal Progress Strategy v1` 已经让 Today 编排读取目标完成率、剩余任务数、deadline 和价值等级。本轮补齐执行后的可见反馈：用户完成或推进任务后，系统需要把任务进度转译成 Goal 层面的进展，而不是只停留在任务状态变化。

### 目标

- Focus 完成后返回本次执行对 Goal 的推进反馈。
- Today 快速完成后返回同一套 Goal 推进反馈。
- Daily Report 汇总当天被触碰和被推进的 Goals。
- Goal Detail 展示当天该目标的轻量反馈，承接 `Goals -> Task Detail -> Focus` 路径。

### 非目标

- 不新增 DB 表和迁移。
- 不引入新的 LLM Agent。
- 不让 Today 首屏变成复杂目标仪表盘。
- 不做 P3/P4 的提醒、外部数据、社交或商业化能力。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
Goals -> Goal Detail -> Task Detail -> Focus -> Report
```

- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Goals

### 产品人格

本轮反馈只做一句可行动、可理解的目标推进提示，例如“完成 A，让 B 前进约 25%”。它提供确定性事实，不制造压力，也不把解释铺满界面。

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
| Task-level feedback | Task 完成 / 部分推进时生成 Goal 推进反馈 | Must | 由 Task 当前 progress 和同 Goal 任务聚合计算 |
| Focus feedback | Focus complete response 带 `goal_progress_feedback` | Must | 不影响 Focus 状态机 |
| Today item feedback | `PATCH /today/items/{id}` 完成项时返回 `goal_progress_feedback` | Must | 仅响应本次动作，不长期挂在 Today 列表 |
| Daily report aggregation | Daily Report 返回当天 Goal 推进汇总 | Must | 基于 ActivityEvent payload 聚合 |
| Goal detail today feedback | Goal Detail 返回当天该 Goal 的轻量反馈 | Should | 用于 Goal Detail 的 Progress 区块 |

### 用户故事

```text
作为 Chronos 用户，
我希望完成一个任务后能知道它让哪个目标前进了多少，
以便我感受到今天的行动确实在靠近高价值目标。
```

```text
作为后端系统，
我希望 Goal 推进反馈来自 ActivityEvent 和 Task progress 的确定性聚合，
以便 Report、Goal Detail 和执行入口保持同一事实口径。
```

### 主要流程

```text
Task / Focus / Today item completed
-> Task progress changes
-> ActivityEvent writes goal progress payload
-> Response returns goal_progress_feedback
-> Daily Report / Goal Detail read same event facts
```

---

## 5. 后端设计

### 影响模块

- [x] Service
- [x] Schemas
- [x] Tests
- [ ] DB Migration
- [ ] Agents

### 数据模型变更

无。反馈为动态 response 字段和 ActivityEvent payload。

### 状态机变更

无。复用现有 Task、DailyPlanItem、FocusSession 状态机。

### 事件变更

复用并增强 payload：

- `TASK_COMPLETED`
- `TASK_PARTIAL_PROGRESS_RECORDED`
- `TASK_POSTPONED`

新增 payload 字段：

- `goal_id`
- `goal_title`
- `goal_value_level`
- `goal_progress_before`
- `goal_progress_after`
- `goal_progress_delta`
- `task_progress_delta`
- `goal_progress_feedback_source`

---

## 6. API 合同

### GoalProgressFeedbackItem

```json
{
  "goal_id": "uuid",
  "goal_title": "完成论文初稿",
  "goal_value_level": "high",
  "task_id": "uuid",
  "task_title": "写完引言",
  "impact_type": "completed_task",
  "progress_before": 0.25,
  "progress_after": 0.5,
  "progress_delta": 0.25,
  "task_progress_delta": 1.0,
  "completed_task_count": 2,
  "total_task_count": 4,
  "unfinished_task_count": 2,
  "focus_minutes": 35,
  "message": "完成「写完引言」，让「完成论文初稿」前进约 25%，当前完成度约 50%。",
  "signal": "positive",
  "source": "goal-progress-feedback-v1"
}
```

### 使用位置

- `FocusSessionResponse.goal_progress_feedback`
- `TodayTaskResponse.goal_progress_feedback`
- `TaskResponse.goal_progress_feedback`
- `DailyReportResponse.goal_progress_feedback`
- `GoalDetailResponse.today_feedback`

---

## 7. 验收标准

- [x] Focus 完成目标任务时，返回本次 Goal 推进反馈。
- [x] Today 快速完成目标任务时，返回本次 Goal 推进反馈。
- [x] Daily Report 汇总当天推进过的 Goal。
- [x] Goal Detail 可读取当天该目标反馈。
- [x] 无 DB migration。
- [x] 不引入 P3/P4 或新 Agent。

---

## 8. Review

本轮对齐主线。它强化的是 `Today -> Task Detail -> Focus -> Report` 和 `Goals -> Task Detail -> Focus` 的反馈闭环，让用户看到高价值目标是否真的被推进。复杂度留在后端聚合，前端只接收轻量、可解释、可隐藏的反馈字段。

下一轮建议做 `P2 Daily Capacity & Available Time v1`：把用户当天可用时间从固定默认值升级为可手动设置 / 可解释读取的输入，让 Planning Engine 更接近“今天做得出来的一天”。
