# Iteration: P2 Goal Progress Strategy v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Planning Engine 不只看单个任务和 Goal 的静态价值，还能读取目标当前推进状态，在时间有限时优先保护“最能提高目标完成度”的下一步。

本轮仍以确定性 Planning Engine 为排序源头。LLM 不直接排序、不直接写业务状态；它后续可以帮助识别任务语义和拆解候选步骤，但 Today 的最终编排必须能解释、能回退、能测试。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Chronos 的核心价值是帮用户“每天接近真正重要的目标”。上一轮已经有 Goal next action coverage，可以为重要目标保留下一步；但它还不够理解目标本身的推进压力，比如：

- 一个高价值目标长期推进不足。
- 一个目标已经接近完成，只差少量任务收口。
- 一个目标完成率偏低，但 deadline 已经接近。

这些都不应该只靠单个任务优先级判断。Planning Engine 需要把 Goal progress 变成可解释的排序信号。

### 目标

- 计算目标完成率、剩余任务数、剩余估时、deadline 压力和目标价值。
- 只把目标进度策略应用到该目标的 next action，避免同一目标多个任务挤占 Today。
- 将 `goal_progress_score` 写入 Today item 的 `score_breakdown`。
- 在 Strategy Detail factors 中暴露 `goal_progress_signal_count`。
- 用 planner eval baseline 固化目标收口和目标压力场景，防止后续回退。

### 非目标

- 不新增 API。
- 不新增数据库表或 migration。
- 不做复杂项目管理、依赖图、甘特图或多目标资源优化器。
- 不让 LLM 直接生成最终排序。
- 不扩 P3/P4，不做提醒、外部数据源、社交或商业化。

---

## 3. 产品约束对齐

### 核心路径

```text
Goals -> Goal Detail -> Task Detail -> Focus
Today -> Task Detail -> Focus -> Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

本轮直接补强 Goals 与 Today 的编排关系。用户不需要看到复杂目标仪表盘，只会感受到 Today 更会保护高价值目标、临近截止目标和接近完成的目标。

### 产品人格

Chronos 仍然保持轻盈和克制：复杂的目标进度判断藏在 Planning Engine 里，前端只需要展示一条清晰可信的排序理由，例如“这个目标已经接近完成，Today 会保护下一步来提高目标完成度”。

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
| Goal progress profile | 计算目标完成率、剩余任务数、剩余估时、deadline 压力 | Must | 读取既有 Goal / Task |
| Goal progress scoring | 将目标推进状态转成 `goal_progress_score` | Must | 只作用于 next action |
| Goal completion closure | 目标接近完成时保护收口动作 | Must | 提高目标完成度 |
| Deadline progress recovery | 目标完成率偏低且截止压力高时优先拉回 | Must | 对齐高价值保护 |
| Strategy factors | 暴露 `goal_progress_signal_count` | Should | 供 Strategy Detail 解释 |
| Planner eval baseline | 新增 goal progress 策略场景 | Must | 固化核心算法 |

### 用户故事

```text
作为正在推进多个长期目标的用户，
我希望 Chronos 能看懂目标当前完成度和剩余压力，
以便今天优先做那些真正能推动目标往前走的下一步。
```

```text
作为时间不够的用户，
我希望系统能在琐事和目标任务之间做出可信取舍，
以便有限时间尽量换来更高的目标完成度。
```

```text
作为前端开发者，
我希望目标进度策略仍然通过既有 Today / Strategy contract 返回，
以便不用新增复杂页面也能解释排序原因。
```

### 主要流程

```text
Active Goal + unfinished Tasks
-> Goal next action selection
-> Goal progress profile
-> Planning Engine score_breakdown
-> Today item rationale
-> Strategy Detail explanation
```

---

## 5. 后端设计

### 影响模块

- [ ] API
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

无。

### 事件变更

无新增事件。目标进度策略读取既有 Goal / Task 状态。

### API 变更

无新增 API。

`GET /api/v1/today/strategy` 的 factors 增加：

```json
{
  "goal_progress_signal_count": 1
}
```

Today item 的 `score_breakdown` 增加一组解释字段：

```json
{
  "goal_progress_score": 14,
  "goal_progress_applied": true,
  "goal_progress_reason_key": "goal_completion_closure",
  "goal_progress_completion_rate": 0.67,
  "goal_progress_total_task_count": 3,
  "goal_progress_completed_task_count": 2,
  "goal_progress_unfinished_task_count": 1,
  "goal_progress_remaining_estimated_minutes": 45,
  "goal_progress_days_until_deadline": 10,
  "goal_progress_pressure_level": "medium"
}
```

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
- [x] LLM 不直接决定 Today 排序
- [x] Planning Engine 是最终排序 source of truth
- [x] 没有信号时回退到原有 deterministic 规则

### 边界说明

本轮是核心算法增强，不是 LLM Agent 增强。后续 LLM 可以辅助任务拆解、任务语义识别和策略解释，但目标进度分数必须由可测试的确定性规则计算，避免用户无法判断系统为什么安排今天。

---

## 7. 验收标准

### 功能验收

- [x] 高价值目标推进不足时，目标 next action 会得到 `goal_progress_score`。
- [x] 接近完成的目标会保护收口动作，帮助提高目标完成度。
- [x] 临近截止且完成率偏低的目标会产生 deadline progress recovery 信号。
- [x] `goal_progress_score` 进入 `total_score`，但不覆盖依赖、用户手动优先级、语义任务信号等更具体解释。
- [x] Strategy Detail 返回 `goal_progress_signal_count`。
- [x] Today item rationale 能解释目标进度策略。

### 数据验收

- [x] 不新增表。
- [x] 不改变既有任务状态。
- [x] 不引入隐藏 Today 写入。

---

## 8. 主线偏离 Review

本轮没有偏离主线。

- 没有做 P3/P4。
- 没有做前端页面。
- 没有做商业化。
- 没有做高级 auth。
- 没有做 provider 验收扩展。
- 没有让 LLM 接管排序。

它直接服务 P2 的 Goals、依赖、洞察、解释主线，并把核心价值推进到“系统能根据目标完成度保护今日行动”。

---

## 9. 验证记录

```bash
.venv/bin/python3 -m unittest tests.test_today_services tests.test_planning_engine_evaluation tests.test_planner_eval_policy tests.test_llm_acceptance_record_generator
```

结果：52 tests OK。

```bash
.venv/bin/python3 scripts/evaluate_planning_engine.py --run-id p2-goal-progress-local --jsonl-output /tmp/chronos-goal-progress-eval.jsonl
```

结果：11 个 planner eval 场景全部通过。

```bash
.venv/bin/python3 scripts/check_planner_eval_policy.py /tmp/chronos-goal-progress-eval.jsonl
```

结果：policy check OK，regression_count = 0。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke p1-mainline
```

结果：318 tests OK；compile OK；git diff --check OK；P1-MAINLINE smoke passed。

---

## 10. 下一步建议

下一轮建议做 `P2 Goal Progress Feedback v1`：把 Focus / quick action / Daily Report 的执行结果回流为目标推进反馈，让用户能看到“今天这次执行让哪个 Goal 前进了多少”。这仍然是 P1/P2 主线，不涉及 P3/P4，也不需要 LLM 接管排序。
