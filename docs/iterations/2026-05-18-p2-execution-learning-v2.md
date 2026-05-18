# Iteration: P2 Execution Learning v2

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 负责人：Codex  
> 关联 Commit：待提交

---

## 1. 迭代摘要

把 Focus 执行结果回流到 Planning Engine，形成可解释、可约束的 Execution Learning v2。它让系统逐步理解用户在同类任务上的真实执行节奏，但不让 AI 或学习信号直接修改任务、目标或排序。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Chronos 的核心不是一次性拆任务，而是持续降低每日规划成本，让系统越来越懂用户。此前已有语义任务类型、语义估时和 Planning Objective v2，但 Focus 执行结果还没有形成明确的学习事件和 objective 输入。本轮补上这个回路。

### 目标

- Focus 完成 / 中断 / 延后后写入 `EXECUTION_LEARNING_OBSERVED` 事件。
- Planning Engine 读取同类任务 Focus 历史，识别超时、中断、延后和完成势能。
- 在 `score_breakdown` 暴露 `execution_learning_*` 字段和学习边界。
- 让 planning objective 接收 execution learning component，但仍由确定性引擎计算。
- planner eval 增加 Execution Learning v2 场景。

### 非目标

- 不新增 DB 表。
- 不做 P3/P4、商业化、外部集成或前端页面。
- 不让 LLM 根据学习信号直接排序。
- 不覆盖 Task 原始估时、Task 状态或 Goal 状态。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
Goals -> Goal Detail -> Task Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

这轮让 Chronos 更懂用户，但仍然克制：用户看到的是更贴近真实执行节奏的估时、理由和策略解释，而不是更多控制面板。

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
| Focus Learning Event | Focus 结果写入 `EXECUTION_LEARNING_OBSERVED` | Must | 无新表 |
| Execution Learning Profile | 按语义任务类型聚合同类 Focus 历史 | Must | 只读历史 |
| Planning Objective Input | 将学习信号转成 objective component | Must | 确定性计算 |
| Strategy Explainability | Strategy Detail / task rationale 暴露学习解释 | Must | 不进 Today 首屏 |
| Planner Eval v10 | 增加 execution learning 场景 | Must | required scenarios 15 |

### 用户故事

```text
作为持续学习者或知识工作者，
我希望 Chronos 能记住我真实执行某类任务时经常超时、中断还是顺手完成，
以便后续 Today 不只是按任务列表排序，而是越来越贴近我的真实执行节奏。
```

```text
作为系统，
我希望 Focus 结果只能作为可解释的计划校准信号，
以便学习能力增强但不破坏用户控制感和业务状态一致性。
```

### 主要流程

```text
Task Detail -> Focus -> complete / interrupt / postpone
-> EXECUTION_LEARNING_OBSERVED
-> Planning Engine 读取同类 TaskPlanningSignal.task_type 历史
-> 生成 execution_learning_* score_breakdown
-> planning_objective_execution_learning_component
-> Strategy Detail / task rationale 解释
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

无新增表、无 migration。

新增事件：

```text
ActivityEvent.event_type = EXECUTION_LEARNING_OBSERVED
```

事件 payload：

```json
{
  "version": "p2-execution-learning-v2",
  "source": "focus_session",
  "outcome": "completed | partial_progress | interrupted | postponed",
  "planned_duration_min": 25,
  "actual_duration_min": 18,
  "duration_delta_min": -7,
  "learning_contract": {
    "task_mutation_allowed": false
  }
}
```

### API 变更

无新增 API。

已有接口响应增强：

| Method | Path | 增强 |
| --- | --- | --- |
| GET | `/api/v1/today/strategy` | `factors` 增加 execution learning counts |
| GET | `/api/v1/today/strategy` | `task_rationales[].score_breakdown` 增加 `execution_learning_*` |
| POST | `/api/v1/focus-sessions/{id}/complete` | 写入学习事件 |
| POST | `/api/v1/focus-sessions/{id}/interrupt` | 写入学习事件 |
| POST | `/api/v1/focus-sessions/{id}/postpone` | 写入学习事件 |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不新增 Agent
- [x] 不修改 Prompt
- [x] 不让 LLM 直接排序
- [x] Planning Engine 消费学习信号

### 边界

- Execution Learning v2 只读取确认过的 Focus 结果。
- 学习信号可影响：
  - 今日 item 估时
  - `planning_objective_score`
  - Strategy Detail / task rationale 解释
- 学习信号不可影响：
  - Task 原始估时
  - Task 状态
  - Goal 状态
  - LLM 直接排序

---

## 7. 验收标准

### 功能验收

- [x] Focus 完成会写入 `EXECUTION_LEARNING_OBSERVED`。
- [x] Planning Engine 能按语义任务类型读取历史 Focus 结果。
- [x] `score_breakdown` 暴露 `execution_learning_applied`、`execution_learning_signal`、样本数、风险率和 learning contract。
- [x] `planning_objective_execution_learning_component` 能接收学习校准。
- [x] Strategy Detail factors 暴露 execution learning count。

### 数据验收

- [x] 无新增 DB migration。
- [x] 学习事件和 `score_breakdown` 都带不可越权的 contract。
- [x] 没有修改 Task 原始估时、Task 状态或 Goal 状态。

### 体验验收

- [x] Today 首屏不新增控制项。
- [x] Task rationale 能解释执行学习，但不要求用户理解原始权重。
- [x] Focus 仍然只做执行，不变成学习控制面板。

---

## 8. 测试与验证

- [x] `uv run python -m unittest tests.test_focus_services.FocusServiceTests.test_start_and_complete_focus_updates_task_today_and_events tests.test_today_services.TodayServiceTests.test_planning_engine_uses_focus_execution_learning_for_semantic_task_type tests.test_planning_engine_evaluation.PlanningEngineEvaluationTests.test_fixed_scenarios_pass tests.test_planner_eval_policy.PlannerEvalPolicyTests.test_bundled_policy_matches_current_evaluator_version`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id p2-execution-learning-v2 --jsonl-output /tmp/chronos-planner-execution-learning-v2.jsonl`
- [x] `uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-execution-learning-v2.jsonl`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`
- [x] `uv run python -m json.tool docs/planner-eval-baselines/p2-planning-engine-eval-v10.json`

结果：

- Focus / Today focused unittest：4 tests OK。
- Planner eval policy：`p2-planning-engine-eval-v10`，15 scenarios OK，0 regressions，0 changes。
- Full unittest：332 tests OK。
- compileall：OK。
- diff check：OK。
- JSON policy：OK。

---

## 9. 主线偏离检查

- [x] 没有进入 P3/P4。
- [x] 没有新增前端页面。
- [x] 没有做商业化。
- [x] 没有扩张 auth。
- [x] 没有让 LLM 成为 planner source of truth。

---

## 10. 后续建议

- `P2 Planning Learning Summary v1`：把 Execution Learning、Semantic Signal、Goal Progress 的影响收敛成更清楚的 Strategy Detail 学习摘要，仍然不进入 Today 首屏。
