# Iteration: P2 Planning Learning Summary v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 负责人：Codex  
> 关联 Commit：待提交

---

## 1. 迭代摘要

在 Strategy Detail 增加 `learning_summary`，把 Goal Progress、Semantic Planning、Execution Learning、Personalization 和 Planner Feedback 等已存在信号，收敛成一组轻量、可解释、不可越权的学习摘要。

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

前几轮已经把 Planning Objective、Semantic Planning Coverage、Execution Learning 打通。系统已经具备“更懂目标、更懂任务语义、更懂用户执行节奏”的信号，但这些信号分散在 `factors`、`score_explanation` 和 `task_rationales` 中。用户需要一个克制的摘要来建立信任，而不是阅读原始权重。

### 目标

- Strategy Detail 返回 `learning_summary`。
- 摘要只解释已存在的学习信号，不新增业务状态。
- 学习摘要带 contract，明确不可改变排序、section、Task / Goal 状态或 LLM 排序边界。
- Planner eval policy 升级到 v11，要求学习摘要存在。

### 非目标

- 不新增 DB 表。
- 不新增 Agent 或 Prompt。
- 不做 Today 首屏展示。
- 不做 P3/P4、商业化、外部集成、前端页面。
- 不让学习摘要改变排序或业务状态。

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

这轮继续把复杂度藏在背后。用户不需要理解所有权重，只需要在 Strategy Detail 中看到 Chronos 正在从目标、任务语义和 Focus 结果中学习，但系统仍然克制、透明、可校正。

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
| Learning Summary | Strategy Detail 返回 `learning_summary` | Must | 解释层 |
| Learning Signals | 归纳 goal / semantic / execution / personalization / feedback 信号 | Must | 最多 4 条 |
| Learning Contract | 明确不可修改计划和业务状态 | Must | 信任边界 |
| Eval Policy v11 | planner eval 要求 learning summary 字段 | Must | 防回归 |
| Frontend Contract | 文档沉淀 `learning_summary` 合同 | Must | Strategy Detail 使用 |

### 用户故事

```text
作为用户，
我希望在 Strategy Detail 里看到 Chronos 正在从哪些信号中学习，
以便我相信它不是黑箱，也不是随意调整我的计划。
```

```text
作为 Planning Engine，
我希望学习摘要只解释已读取的确定性信号，
以便增强信任感但不引入新的隐式调度逻辑。
```

### 主要流程

```text
Strategy Detail
-> factors / task_rationales / planner_review
-> planning_learning_summary
-> learning_summary.signals + learning_contract
-> 前端轻量展示，不进入 Today 首屏
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

### API 变更

已有接口响应增强：

| Method | Path | 增强 |
| --- | --- | --- |
| GET | `/api/v1/today/strategy` | 增加 `learning_summary` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不新增 Agent
- [x] 不修改 Prompt
- [x] 不调用 LLM
- [x] 不让 LLM 直接排序

### 边界

`learning_summary` 可影响：

- Strategy Detail 展示
- Strategy Explanation 输入理解
- task rationale 的用户理解

不可影响：

- Today 排序
- Today section
- Task 原始估时
- Task 状态
- Goal 状态
- LLM 直接排序

---

## 7. 验收标准

### 功能验收

- [x] Strategy Detail 返回 `learning_summary.version=p2-planning-learning-summary-v1`。
- [x] 无稳定学习信号时仍返回克制 summary 和空 signals。
- [x] 有 Execution Learning 时，signals 优先展示 `execution_learning`。
- [x] learning contract 明确 `plan_mutation_allowed=false`。
- [x] planner eval v11 要求 learning summary 字段。

### 数据验收

- [x] 无 DB migration。
- [x] 不新增 ActivityEvent。
- [x] 不修改 Task / Goal / DailyPlan 状态。

### 体验验收

- [x] Today 首屏无新增字段。
- [x] Strategy Detail 可以展示 0-4 条学习信号。
- [x] 学习摘要是信任解释，不是控制面板。

---

## 8. 测试与验证

已执行：

- [x] `uv run python -m unittest tests.test_today_services.TodayServiceTests.test_strategy_detail_explains_current_plan_without_changing_state tests.test_today_services.TodayServiceTests.test_planning_engine_uses_focus_execution_learning_for_semantic_task_type tests.test_planning_engine_evaluation.PlanningEngineEvaluationTests.test_fixed_scenarios_pass tests.test_planner_eval_policy.PlannerEvalPolicyTests.test_bundled_policy_matches_current_evaluator_version`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id p2-planning-learning-summary-v1 --jsonl-output /tmp/chronos-planner-learning-summary-v1.jsonl`
- [x] `uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-learning-summary-v1.jsonl`

待执行：

- [x] Full unittest
- [x] compileall
- [x] git diff --check
- [x] JSON policy validation

结果：

- Focused unittest：4 tests OK。
- Planner eval policy：`p2-planning-engine-eval-v11`，15 scenarios OK，0 regressions，0 changes。
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

- `P2 Goal Progress Feedback v2`：把 Daily Report / Goal Detail 中的目标推进反馈进一步和 Today objective 对齐，避免用户只看到任务完成，看不到目标完成率变化。
