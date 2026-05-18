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
| Daily Available Time | `POST /api/v1/today/replan` -> `available_minutes` | Ready |
| Task Semantic Planning Signal | `POST /api/v1/tasks/{task_id}/planning-signal` | Ready |
| Task Priority Adjustment | `PATCH /api/v1/tasks/{task_id}/priority` | Ready |
| Task Dependencies | `GET/POST/DELETE /api/v1/tasks/{task_id}/dependencies` | Ready |
| Goals Home | `GET /api/v1/goals/home` | Ready |
| Goal Detail | `GET /api/v1/goals/{goal_id}/detail` | Ready |
| Goal Progress Timeline | `GET /api/v1/goals/{goal_id}/progress-timeline` | Ready |
| Goal Progress Feedback | Focus / Today / Daily Report / Goal Detail 中的 `goal_progress_feedback` | Ready |
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
- Today 排序由 Planning Engine v1 生成，已读取任务价值、优先级、截止时间、依赖、用户优先级修正、行为反馈、可用容量和任务语义规划信号；前端仍只按分区和 `sort_order` 渲染，不需要自己重排。
- `score_breakdown` 可用于调试或 Strategy Detail，不建议在 Today 首屏展开。
- 用户通过 `PATCH /api/v1/today/items/{item_id}` 完成目标任务时，单个 Today item response 会返回 `goal_progress_feedback`，用于轻量提示“本次完成让哪个 Goal 前进了多少”。普通 Today 列表不需要常驻展示该字段。

### GET `/api/v1/today/strategy`

用于解释当前 Today 策略，不修改计划。

核心字段：

- `summary`
- `primary_reason`
- `factors`
- `score_explanation`
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
- `ai_job_id` 指向 Daily Planner Agent 的调用记录，可通过 `GET /api/v1/ai-jobs/{id}` 查看 provider、model、status、fallback 和 metadata。
- `AIJob.job_metadata.prompt_checksum` 可用于确认本次 planner agent 使用的具体 prompt 内容版本；前端一般不需要展示。
- `AIJob.latency_ms`、`job_metadata.failure_type`、`job_metadata.provider_latency_ms`、`job_metadata.provider_response_id` 和 `job_metadata.usage` 只用于 Strategy Detail 深层解释、调试或后台观测，不建议进入 Today 首屏；真实 provider 返回 usage 时这里可能包含 token 统计。
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
  "base_capacity_minutes": 150,
  "daily_capacity_minutes": 150,
  "capacity_source": "planning_preference",
  "manual_available_minutes": null,
  "energy_capacity_adjusted": false,
  "selected_estimated_minutes": 95,
  "rolled_over_estimated_minutes": 0,
  "over_capacity_minutes": 0,
  "capacity_status": "within_capacity",
  "dependency_protected_count": 1,
  "goal_next_action_count": 2,
  "goal_progress_signal_count": 1,
  "user_adjusted_count": 1,
  "semantic_signal_count": 1,
  "semantic_protected_count": 1,
  "minimum_viable_progress_count": 1,
  "execution_feedback_count": 1,
  "personalization_signal_count": 1,
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
- `goal_next_action_count` 表示有多少高价值 / 临近截止目标各自保留了一个下一步行动。
- `goal_progress_signal_count` 表示有多少目标下一步读取了 Goal 完成率、剩余任务数和截止压力，用来提升目标完成度。
- `user_adjusted_count` 表示当前计划读取到用户优先级修正事件的任务数量。
- `semantic_signal_count` 表示当前计划读取到 TaskPlanningSignal 的任务数量。
- `semantic_protected_count` 表示因为语义信号对目标推进价值较高而被保护的任务数量。
- `minimum_viable_progress_count` 表示有多少大任务在 Today 中只保护“今天做得出来的最小推进动作”。
- `execution_feedback_count` 表示有多少任务读取了真实执行时间，并用它校准今日剩余估时。
- `personalization_signal_count` 表示有多少任务读取了同类任务历史执行画像，用于调整估时和排序力度；它来自确定性聚合，不是 LLM 直接排序。
- `base_capacity_minutes` 是用户偏好或手动输入形成的基础容量。
- `daily_capacity_minutes` 是 Planning Engine 的当日容量参考，不是严格日历时间块。
- `capacity_source` 当前可能是 `planning_preference`、`manual_today_override` 或 `energy_adjusted`。
- `manual_available_minutes` 表示用户本次手动设置的今日可用时间；为空时使用 Planning Preference 默认容量。
- `energy_capacity_adjusted=true` 表示低精力把默认容量收敛到更轻的范围；如果用户手动设置了可用时间，手动输入优先。
- `selected_estimated_minutes` 是今天主执行序列的估时总量。
- `rolled_over_estimated_minutes` 是被滚动到未来、保留可见但不计入主执行序列的估时。
- `over_capacity_minutes` 表示主执行序列超出当日容量参考的分钟数；只有受保护任务总量过重时才会大于 0。
- `capacity_status` 当前为 `within_capacity` 或 `overloaded`，只用于 Strategy Detail 解释。
- `energy_applied=true` 表示同日 Energy 数据已经作为排序和容量保护因子进入 Planning Engine；高精力不会自动增加工作量。
- `planner_agent_latency_ms` 和 `planner_agent_failure_type` 只用于 Strategy Detail 深层解释、调试或后台观测；Today 首屏不展示。
- 这些字段用于 Strategy Detail 的信任解释，不建议放到 Today 首屏。

`score_explanation` 是 Planning Engine 从 `score_breakdown` 归纳出的可读解释：

```json
{
  "score_explanation": {
    "summary": "Planning Engine 将 3 个主序列任务压在约 120 分钟内，容量参考为 150 分钟。",
    "signals": [
      {
        "key": "high_value_protection",
        "title": "高价值优先",
        "message": "1 个任务被放入保护区，优先处理重要或紧急事项。",
        "signal": "positive",
        "score": 1
      }
    ],
    "source": "planning-engine-score-breakdown-v1"
  }
}
```

前端约束：

- `score_explanation` 只用于 Strategy Detail，不进入 Today 首屏。
- `signals` 建议最多展示 2-4 条，作为解释而不是控制项。
- `signal` 当前可能是 `positive`、`info`、`watch`、`risk`。

`planner_review` 来自 Daily Planner Agent 对 Planning Engine 结果的审阅：

```json
{
  "planner_review": {
    "summary": "Planning Engine 的排序可以直接执行，LLM 只补充轻量审阅，不改变任务顺序。",
    "suggestions": [
      {
        "key": "start_with_first_task",
        "title": "先开始第一项",
        "message": "当前排序已经可执行，先从主序列第一项开始，完成后再看下一步。",
        "signal": "positive"
      }
    ],
    "source": "daily_planner_agent_v1"
  }
}
```

前端约束：

- `planner_review` 只出现在 Strategy Detail，不放入 Today 首屏。
- 它是 critique / suggestion，不表示系统已修改任务顺序。
- 当 Daily Planner Agent fallback 或旧计划没有该字段时，`planner_review` 可以为 `null`。

`task_rationales[]` 中每个任务会包含 `score_breakdown`：

```json
{
  "task_id": "uuid",
  "title": "Draft proposal",
  "score_breakdown": {
    "total_score": 88,
    "score_version": "planning-engine-v1",
    "score_band": "high",
    "value_score": 30,
    "urgency_score": 16,
    "dependency_score": 18,
    "duration_fit_score": 5,
    "energy_fit_score": 0,
    "behavior_feedback_score": 0,
    "user_preference_score": 10,
    "postponement_penalty": 0,
    "priority_score": 16,
    "semantic_signal_applied": true,
    "semantic_total_score": 38,
    "goal_alignment_signal_score": 13,
    "goal_next_action_score": 10,
    "semantic_priority_signal_score": 10,
    "semantic_minimum_viable_step": "先完成一个可验证的小结果",
    "base_estimated_duration_min": 180,
    "actual_duration_min": 30,
    "remaining_estimated_duration_min": 150,
    "execution_feedback_applied": true,
    "execution_feedback_reason": "actual_duration_remaining",
    "original_estimated_duration_min": 150,
    "planned_duration_min": 45,
    "minimum_viable_progress_applied": true,
    "base_capacity_minutes": 150,
    "daily_capacity_minutes": 150,
    "capacity_source": "planning_preference",
    "manual_available_minutes": null,
    "selected_for_today": true
  },
  "dominant_factor": "deadline_soon",
  "dominant_reason": "截止时间较近，因此排序会适度提前。",
  "score_signals": [
    {
      "key": "deadline_soon",
      "title": "截止时间接近",
      "message": "截止时间较近，因此排序会适度提前。",
      "signal": "watch",
      "score": 16
    }
  ]
}
```

前端约束：

- `score_breakdown` 是解释数据，不要在 Today 首屏展示成复杂驾驶舱。
- Strategy Detail 优先展示 `dominant_reason` 和 `score_signals`，不要让前端自行解释原始权重。
- `goal_progress_*` 字段来自 Goal 下任务的确定性聚合，用于解释系统如何保护“更接近目标完成”的下一步；它不新增 Goal 页面复杂度。
- `semantic_*` 字段来自 TaskPlanningSignal，只表示 Planning Engine 读取到语义信号；它不是 LLM 直接改排序。
- `personalization_*` 字段来自同类 TaskPlanningSignal 历史任务的执行结果，用于解释“系统如何逐渐理解这个用户的真实执行节奏”；它不直接修改 Task 本体。
- `base_estimated_duration_min` 是任务原始 / 语义估时，`personalized_estimated_duration_min` 是结合个人历史执行画像后的本轮估时，`remaining_estimated_duration_min` 是结合 Focus 实际投入后的剩余估时，`original_estimated_duration_min` 是最小推进切片前的本轮估时。
- `capacity_source=manual_today_override` 时，说明本轮 Today 是按用户手动设置的 `available_minutes` 编排；这只影响今日容量，不会修改 Task 原始估时。
- 当 `minimum_viable_progress_applied=true` 时，Today item 代表“今日最小推进切片”，不是整个 Task；完成该 item 后后端会记录 Task partial progress，Task 仍保持 active。
- `selected_for_today=false` 且 `rollover_reason=capacity` 表示任务被系统滚动到未来，不代表任务被用户手动延后；此时 `item_status` 仍可为 `planned`，前端应以 `section=rolled_over` 判断展示位置。
- 若 `capacity_status=overloaded`，Today 可在 Insights Preview 展示一条轻量风险提示，但不要展示完整容量面板。

### POST `/api/v1/today/replan`

用于显式重新编排 Today。P2 可传入今日手动可用时间：

```json
{
  "reason": "下午只有一小时能专注",
  "available_minutes": 60
}
```

Response：`TodayResponse`。

说明：

- `available_minutes` 范围为 15-720，表示用户今天愿意交给 Chronos 编排的可用执行时间。
- 传入后，本日当前 plan revision 的 `capacity_source` 会变为 `manual_today_override`。
- 同一个 active Today 后续再次 replan 且未传 `available_minutes` 时，会沿用当前手动可用时间，避免用户设置被新任务或 signal refresh 冲掉。
- 手动可用时间优先于 Energy 对容量的收敛；Energy 仍可作为任务排序与解释信号，但不会覆盖用户明确输入。
- 这是用户控制入口，不是日历时间块，不会自动创建 Reminder，也不会让 LLM 接管排序。

### POST `/api/v1/today/planning-signals`

为当前 Today 主序列准备缺失或过期的 TaskPlanningSignal，并在生成新信号后触发一次 deterministic replan。

Query：

- `plan_date?: YYYY-MM-DD`
- `limit?: number`，默认 10，范围 1-20。
- `replan?: boolean`，默认 true。

Response：

```json
{
  "plan_date": "2026-05-16",
  "task_count": 2,
  "generated_count": 1,
  "existing_count": 1,
  "stale_count": 0,
  "skipped_count": 0,
  "replanned": true,
  "planning_signal_ids": ["uuid"],
  "ai_job_ids": ["uuid"],
  "today": {
    "date": "2026-05-16",
    "plan_version": 2,
    "sections": {}
  }
}
```

前端约束：

- 这是受控的 AI 准备动作，不是 Today 首屏自动狂跑 provider。
- 生成的是 TaskPlanningSignal；LLM 不直接改 Task / Goal / DailyPlan 排序。
- `existing_count` 表示仍然新鲜的 signal；`stale_count` 表示任务、目标、步骤、依赖或执行进度变化后需要刷新的旧 signal。
- 如果 `generated_count=0`，默认不 replan，避免无意义刷新。
- 如果 `replanned=true`，前端直接使用 response 内的 `today` 刷新页面。

## 4. Task Detail

### POST `/api/v1/tasks/{task_id}/planning-signal`

生成或刷新当前 Task 的语义规划信号。

Request：无 body。

Response：

```json
{
  "ai_job": {
    "id": "uuid",
    "job_type": "task_semantic_planning",
    "status": "succeeded",
    "result_entity_type": "task_planning_signal",
    "result_entity_id": "uuid",
    "provider": "mock",
    "model": "structured-mock-v1",
    "prompt_version": "p2-task-semantic-planning-agent-v1",
    "job_metadata": {}
  },
  "planning_signal": {
    "id": "uuid",
    "task_id": "uuid",
    "ai_job_id": "uuid",
    "source": "ai",
    "task_type": "writing",
    "complexity": "high",
    "cognitive_load": "high",
    "energy_fit": "high_energy",
    "blocking_risk": "high",
    "estimated_duration_min": 60,
    "duration_confidence": 0.56,
    "goal_alignment_score": 0.9,
    "semantic_priority_score": 0.62,
    "breakdown_recommended": true,
    "minimum_viable_step": "先完成一个可验证的小结果",
    "semantic_summary": "该任务与高价值目标关联较强，复杂度为 high，应该保护一个最小推进动作。",
    "confidence": 0.66,
    "created_at": "2026-05-17T09:00:00Z"
  }
}
```

前端约束：

- 这个接口适合作为 Task Detail 的“刷新 AI Info”动作，或者在任务刚确认后由后端工作流触发。
- 不要把所有 planning signal 字段都摊开成信息仓库；优先展示推荐时长、最小推进动作、语义摘要。
- 生成 signal 不会直接修改 Task、Goal 或 Today 当前版本；下一次 Today 生成 / replan 时由 Planning Engine 读取。

### GET `/api/v1/tasks/{task_id}`

Task Detail 的 `ai_info` 会附带最新语义信号：

```json
{
  "ai_info": {
    "recommended_duration_min": 60,
    "priority": 4,
    "value_level": "medium",
    "execution_suggestion": "先推进：先完成一个可验证的小结果",
    "planning_signal": {
      "id": "uuid",
      "task_type": "writing",
      "complexity": "high",
      "goal_alignment_score": 0.9,
      "minimum_viable_step": "先完成一个可验证的小结果"
    }
  }
}
```

前端约束：

- `planning_signal` 可能为 `null`。
- 如果存在，推荐优先展示 `minimum_viable_step` 和 `semantic_summary`，不要展示完整评分细节。
- `recommended_duration_min` 会优先使用用户显式填写的任务估时；没有用户估时时，才使用 planning signal 的语义估时。

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
- 如果该任务已经位于当前 active Today plan，后端会触发 `manual_adjust` 生成新的 Today version，并在响应中返回 `today_impact`。
- 如果当前没有 active Today plan，或该任务不在当前 Today，响应仍会说明 `today_impact`，后续生成 / 刷新 Today 时再读取该信号。

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
- 如果新增 / 删除的依赖涉及当前 active Today plan 中的任务，后端会触发 `system_refresh` 生成新的 Today version，使 Planning Engine 的排序和 Strategy Detail 解释立即读取最新依赖。
- 如果相关任务不在当前 Today，依赖只更新 Task Detail / Goal Detail；后续生成或主动刷新 Today 时再读取该信号。

## 5. Goals

### GET `/api/v1/goals/home`

用于 Goals 首页，返回：

- `summary`
- `filters`
- `goals`
- 每个 goal card 的 progress / risk / associated task count / recommended next task id
- `recommended_next_task_id` 会避开仍有未完成前置任务的后续任务；如果所有未完成任务都被阻塞，则回退到排序最高的未完成任务。
- Goal `progress` / `completion_rate` 按任务自身 `progress` 汇总，能反映最小推进切片带来的部分进展；`completed_task_count` 仍只表示真正完成的 Task 数。

### GET `/api/v1/goals/{goal_id}/detail`

用于 Goal Detail，返回：

- `overview`
- `progress`
- `task_list`
- `dependency_map`
- `ai_suggestion`
- `today_feedback`
- `actions`

Dependency Map 已返回真实依赖边，方向为：

```text
from_task_id -> to_task_id
```

`task_list.recommended_next_task` 与 Goals 首页保持一致：优先推荐未被依赖阻塞的下一步，避免把用户直接带到暂时不能执行的后续任务。

`today_feedback` 表示今天该 Goal 是否被执行推进，来自 `TASK_COMPLETED` / `TASK_PARTIAL_PROGRESS_RECORDED` 事件的确定性聚合。前端建议放在 Goal Progress 区块附近，以一句话提示为主，不做复杂仪表盘。

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

### GET `/api/v1/reports/daily`

Daily Report 返回 `goal_progress_feedback`：

```json
{
  "goal_progress_feedback": {
    "report_date": "2026-05-18",
    "touched_goal_count": 1,
    "advanced_goal_count": 1,
    "high_value_goal_count": 1,
    "total_progress_delta": 0.25,
    "items": [
      {
        "goal_id": "uuid",
        "goal_title": "完成论文初稿",
        "goal_value_level": "high",
        "task_id": null,
        "task_title": null,
        "impact_type": "daily_goal_progress",
        "progress_before": 0.25,
        "progress_after": 0.5,
        "progress_delta": 0.25,
        "task_progress_delta": 0.25,
        "completed_task_count": 2,
        "total_task_count": 4,
        "unfinished_task_count": 2,
        "focus_minutes": 35,
        "message": "今天让「完成论文初稿」前进约 25%，当前完成度约 50%。",
        "signal": "positive",
        "source": "goal-progress-feedback-v1"
      }
    ],
    "source": "goal-progress-feedback-v1"
  }
}
```

前端约束：

- Daily Report 可以展示目标推进汇总，但不要替代 Today 的下一步执行入口。
- `total_progress_delta` 是按当天被触碰 Goal 的完成率变化累加，用于反馈感，不用于重新排序。
- 没有推进时 `items=[]`，前端应保持安静，不制造压力。

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
- `completion_rate` 按当前 DailyPlanItem 完成情况计算；`completed_task_count` 只统计真正 completed 的 Task。最小推进切片完成会提高 completion_rate，但不会被误算为完成整个任务。

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
- 当前已接入 Insight Detail Agent，但仍保持只读。
- `source.generated_by` 成功时为 `insight-agent-v1`，fallback 时为 `rule-insight-v1`。
- `source` 可返回 `ai_job_id`、`ai_job_status`、`model_name`、`prompt_version`、`fallback_reason`，用于调试和来源展示。
- Agent 只改写 `behavior_patterns`、`recommendations`、`strategy_notes`，不改变 `overview` 和 `efficiency_windows`。

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
