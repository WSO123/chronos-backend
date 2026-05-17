# Chronos P2 Frontend API Contract

日期：2026-05-16
状态：P2 backend contract

## 1. 目的

本文档沉淀 P2 已经可用的前端接口合同，用于承接：

```text
Goals -> Goal Detail -> Task Detail -> Focus
Me -> Reports / Insights
Today -> Strategy Detail / Insights Preview
```

P2 的原则仍然是：增强目标和洞察，但不让 Today 变成复杂驾驶舱，不让 Task Detail 变成信息仓库，不让洞察抢走行动感。

## 2. P2 Ready Map

| 页面 / 场景 | 接口 | 状态 |
| --- | --- | --- |
| Today Insights Preview | `GET /api/v1/today` -> `insights_preview` | Ready |
| Strategy Detail | `GET /api/v1/today/strategy` | Ready |
| Task Priority Adjustment | `PATCH /api/v1/tasks/{task_id}/priority` | Ready |
| Task Dependencies | `GET/POST/DELETE /api/v1/tasks/{task_id}/dependencies` | Ready |
| Goals Home | `GET /api/v1/goals/home` | Ready |
| Goal Detail | `GET /api/v1/goals/{goal_id}/detail` | Ready |
| Goal Progress Timeline | `GET /api/v1/goals/{goal_id}/progress-timeline` | Ready |
| Weekly Report | `GET /api/v1/reports/weekly` | Ready |
| Monthly Report | `GET /api/v1/reports/monthly` | Ready |
| Insight Detail | `GET /api/v1/insights/detail` | Ready |
| Me Insights Overview | `GET /api/v1/me/overview` -> `insights` | Ready |

## 3. Today

### GET `/api/v1/today`

P2 新增字段：

```json
{
  "insights_preview": {
    "risk_alerts": [],
    "remaining_time_suggestion": {
      "key": "remaining_time",
      "title": "Remaining time",
      "message": "The remaining plan is light enough to keep a calm pace.",
      "signal": "positive",
      "task_id": null
    },
    "adjustment_suggestions": [],
    "source": "rule-today-insights-v1"
  }
}
```

前端约束：

- 默认只展示 1 条风险或剩余时间提示。
- 不在 Today 首屏展开完整解释。
- 用户需要解释排序时进入 Strategy Detail。
- Today 排序由 Planning Engine v1 生成，已读取任务价值、优先级、截止时间、依赖、用户优先级修正、行为反馈和可用容量信号；前端仍只按分区和 `sort_order` 渲染，不需要自己重排。
- `score_breakdown` 可用于调试或 Strategy Detail，不建议在 Today 首屏展开。

### GET `/api/v1/today/strategy`

用于解释当前 Today 策略，不修改计划。

核心字段：

- `summary`
- `primary_reason`
- `factors`
- `explanation`
- `task_rationales`
- `source`

`source` 当前包含：

```json
{
  "strategy_snapshot_id": "uuid",
  "ai_job_id": "uuid",
  "model_name": "planning-engine-v1",
  "prompt_version": "p2-planning-engine-v1",
  "generated_at": "2026-05-17T09:00:00Z"
}
```

说明：

- `model_name` / `prompt_version` 指向最终落库的 Planning Engine strategy snapshot。
- `ai_job_id` 指向 Daily Planner Agent shell 的调用记录，可通过 `GET /api/v1/ai-jobs/{id}` 查看 provider、model、status、fallback 和 metadata。
- `AIJob.job_metadata.prompt_checksum` 可用于确认本次 planner agent 使用的具体 prompt 内容版本；前端一般不需要展示。
- `AIJob.latency_ms`、`job_metadata.failure_type`、`job_metadata.provider_latency_ms` 和 `job_metadata.usage` 只用于 Strategy Detail 深层解释、调试或后台观测，不建议进入 Today 首屏。
- Strategy Detail 可以把 `ai_job_id` 用于调试或深层解释；Today 首屏不展示这个字段。

`factors` 当前包含：

```json
{
  "task_count": 3,
  "high_value_task_count": 1,
  "pinned_count": 1,
  "recommended_count": 1,
  "low_priority_count": 1,
  "rolled_over_count": 0,
  "total_estimated_minutes": 95,
  "daily_capacity_minutes": 150,
  "selected_estimated_minutes": 95,
  "rolled_over_estimated_minutes": 0,
  "over_capacity_minutes": 0,
  "capacity_status": "within_capacity",
  "dependency_protected_count": 1,
  "user_adjusted_count": 1,
  "energy_level": "unknown",
  "energy_applied": false,
  "planner_agent_latency_ms": 12,
  "planner_agent_failure_type": null,
  "completed_count": 0,
  "focus_minutes": 0
}
```

说明：

- `dependency_protected_count` 表示被提前保护的前置任务数量。
- `user_adjusted_count` 表示当前计划读取到用户优先级修正事件的任务数量。
- `daily_capacity_minutes` 是 Planning Engine 的当日容量参考，不是严格日历时间块。
- `selected_estimated_minutes` 是今天主执行序列的估时总量。
- `rolled_over_estimated_minutes` 是被滚动到未来、保留可见但不计入主执行序列的估时。
- `over_capacity_minutes` 表示主执行序列超出当日容量参考的分钟数；只有受保护任务总量过重时才会大于 0。
- `capacity_status` 当前为 `within_capacity` 或 `overloaded`，只用于 Strategy Detail 解释。
- `energy_applied=true` 表示同日 Energy 数据已经作为排序和容量保护因子进入 Planning Engine；高精力不会自动增加工作量。
- `planner_agent_latency_ms` 和 `planner_agent_failure_type` 只用于 Strategy Detail 深层解释、调试或后台观测；Today 首屏不展示。
- 这些字段用于 Strategy Detail 的信任解释，不建议放到 Today 首屏。

`task_rationales[]` 中每个任务会包含 `score_breakdown`：

```json
{
  "task_id": "uuid",
  "title": "Draft proposal",
  "score_breakdown": {
    "total_score": 88,
    "value_score": 30,
    "urgency_score": 16,
    "dependency_score": 18,
    "duration_fit_score": 5,
    "energy_fit_score": 0,
    "behavior_feedback_score": 0,
    "user_preference_score": 10,
    "postponement_penalty": 0,
    "priority_score": 16,
    "daily_capacity_minutes": 150,
    "selected_for_today": true
  }
}
```

前端约束：

- `score_breakdown` 是解释数据，不要在 Today 首屏展示成复杂驾驶舱。
- Strategy Detail 可以按需展示 2-3 个最关键因子。
- `selected_for_today=false` 且 `rollover_reason=capacity` 表示任务被系统滚动到未来，不代表任务被用户手动延后；此时 `item_status` 仍可为 `planned`，前端应以 `section=rolled_over` 判断展示位置。
- 若 `capacity_status=overloaded`，Today 可在 Insights Preview 展示一条轻量风险提示，但不要展示完整容量面板。

## 4. Task Detail

### PATCH `/api/v1/tasks/{task_id}/priority`

用于用户修正 AI 判断。

```json
{
  "priority": 1,
  "value_level": "high",
  "reason": "Protect this task today"
}
```

规则：

- `priority` 和 `value_level` 至少传一个。
- `priority` 范围为 `1-5`，数字越小越优先。
- 写入 `TASK_PRIORITY_ADJUSTED`。
- 不自动触发 Today replan；下一次打开 Today 已有计划时不会静默改版，用户主动 replan 或新计划生成时会读取该信号。

### Task Dependencies

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/tasks/{task_id}/dependencies` | 获取当前任务的前置任务和后续任务 |
| POST | `/api/v1/tasks/{task_id}/dependencies` | 为当前任务添加前置任务 |
| DELETE | `/api/v1/tasks/{task_id}/dependencies/{prerequisite_task_id}` | 删除当前任务的一条前置依赖 |

依赖方向：

```text
prerequisite_task -> dependent_task
```

规则：

- 不允许自依赖。
- 不允许形成环。
- 不允许跨用户依赖。

## 5. Goals

### GET `/api/v1/goals/home`

用于 Goals 首页，返回：

- `summary`
- `filters`
- `goals`
- 每个 goal card 的 progress / risk / associated task count / recommended next task id

### GET `/api/v1/goals/{goal_id}/detail`

用于 Goal Detail，返回：

- `overview`
- `progress`
- `task_list`
- `dependency_map`
- `ai_suggestion`
- `actions`

Dependency Map 已返回真实依赖边，方向为：

```text
from_task_id -> to_task_id
```

### GET `/api/v1/goals/{goal_id}/progress-timeline`

用于 Goal Progress 区块，只读聚合 ActivityEvent。

核心字段：

- `summary`
- `milestones`
- `note`

前端约束：

- Timeline 是轻量关键节点，不做甘特图。
- 默认展示 5-8 个 milestones。

## 6. Reports

### GET `/api/v1/reports/weekly`

Query:

```text
week_start=YYYY-MM-DD
```

返回 weekly summary、daily trends、focus summary、lagging tasks 和规则建议。

### GET `/api/v1/reports/monthly`

Query:

```text
month=YYYY-MM-DD
```

返回 monthly summary、weekly trends、daily trends 和规则建议。

P2 约束：

- Weekly / Monthly Report 当前不持久化。
- 不替代 Today 的每日执行顺序。
- 规则建议不代表真实 LLM 洞察。

## 7. Insights

### GET `/api/v1/insights/detail`

Query:

```text
anchor_date=YYYY-MM-DD
```

返回：

- `overview`
- `behavior_patterns`
- `efficiency_windows`
- `recommendations`
- `strategy_notes`
- `source`

前端约束：

- Insight Detail 是二级页。
- 默认控制条数，避免抢走行动感。
- 当前是规则聚合，不接真实 LLM。

## 8. Me

### GET `/api/v1/me/overview`

P2 新增字段：

```json
{
  "insights": {
    "highlights": [],
    "suggested_next_view": "insights_detail",
    "detail_available": true
  }
}
```

前端约束：

- Me Overview 只展示少量 highlights。
- 深度分析进入 `/insights/detail`。
- Energy / Social 入口仍保留占位，不假设后端完成。

## 9. P2 仍不依赖

- 真实 LLM planning / insight generation。
- Energy Dashboard。
- Calendar / Email / Health 数据接入。
- Notification Center。
- Social / Groups / Friends。
- 多人任务分配。
- 吉祥物增强反馈。

## 10. 验收命令

```bash
uv run python -m unittest discover -s tests
uv run python scripts/smoke_p1_execution_loop.py
uv run python scripts/smoke_p2_goal_insight_loop.py
```
