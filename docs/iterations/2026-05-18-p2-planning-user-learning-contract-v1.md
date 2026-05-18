# Iteration: P2 Planning User Learning Contract v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

为 Planner Review feedback preference 增加后端学习契约，让 API 明确表达：用户反馈可以影响 Strategy Detail 解释、Planner Review 建议和只读审阅上下文，但不能直接改变 Today 排序、分区、容量或任务 / 目标状态。

---

## 2. 背景与目标

前几轮已经把“用户反馈 -> 偏好摘要 -> 中文解释 -> eval 护栏”跑通。当前缺口在于 contract 仍主要靠字段名和测试语义传达，后续前端或服务层容易误解 `feedback_summary` 是一个可直接控制计划的偏好开关。

Chronos 的核心是越来越懂用户，但必须保持可信：系统可以学习并解释，不能越权替用户改变当天计划。

### 目标

- 在 `POST /api/v1/today/planner-review/feedback` 返回中加入 `learning_contract`。
- 在 `planner_review.feedback_summary` 中加入同一份 `learning_contract`。
- contract 明确：
  - `can_affect`: `strategy_explanation`、`planner_review_suggestions`、`daily_planner_review_context`
  - `cannot_affect`: `today_sort_order`、`today_sections`、`daily_capacity_minutes`、`task_status`、`goal_state`
  - `plan_mutation_allowed = false`
  - `requires_explicit_user_action = true`
- 让 service / API / planner eval 测试都覆盖该边界。

### 非目标

- 不新增数据库表或用户画像表。
- 不改变 Planning Engine 排序权重。
- 不让 feedback summary 自动触发 replan。
- 不新增 Agent、Worker、外部集成、P3/P4 或前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Planner Review Feedback
-> Preference Summary
-> Learning Contract
-> Strategy Detail Explanation / Review Suggestions
-> Today remains deterministic
```

本轮服务于“AI Execution OS 越来越懂用户”的主线，但仍把计划变更留给用户明确操作。

### 用户故事

```text
作为一个会持续修正 AI 建议的用户，
我希望 Chronos 明确告诉我这些反馈会怎样被使用，
以便我知道系统在学习，但不会偷偷替我改计划。
```

```text
作为后端开发者，
我希望学习信号的影响范围有清晰 contract，
以便后续迭代不会把解释层偏好误接到排序、容量或状态 mutation 上。
```

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱。
- [x] 不让 Task Detail 变成信息仓库。
- [x] 不让 Focus 变成控制面板。
- [x] 不让洞察和解释抢走行动感。
- [x] 不让“聪明”压过“可信”。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Learning contract schema | 新增 `PlannerUserLearningContractResponse` | Must | API 可见 |
| Feedback response contract | 反馈记录返回影响边界 | Must | 即时告知 |
| Feedback summary contract | Strategy Detail 暴露同一边界 | Must | 审阅可追踪 |
| Eval assertion | planner eval 场景断言 contract 不允许改计划 | Should | 防回归 |

### 主要流程

```text
用户记录 Planner Review feedback
-> API 返回 learning_contract
-> 反馈聚合成 preference_summary
-> Strategy Detail 返回 feedback_summary.learning_contract
-> Planner eval 确认 contract 禁止隐藏排序变化
```

---

## 5. 后端设计

### 影响模块

- [x] API Schema
- [x] Service
- [ ] Models
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests / Eval
- [x] Docs

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无，继续使用：

```text
PLANNER_REVIEW_FEEDBACK_RECORDED
```

---

## 6. 验收标准

- [x] `PlannerReviewFeedbackResponse.learning_contract.plan_mutation_allowed = false`。
- [x] `StrategyPlannerFeedbackSummaryResponse.learning_contract.plan_mutation_allowed = false`。
- [x] contract 的 `can_affect` 包含解释 / 审阅建议，不包含排序或容量。
- [x] contract 的 `cannot_affect` 包含 Today 排序、分区、容量、任务状态和目标状态。
- [x] planner eval 新场景验证 preference contract 不允许隐藏排序变化。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_today_services tests.test_today_api tests.test_planning_engine_evaluation
uv run python scripts/verify_local.py --planner-eval-policy
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
git diff --check
```

---

## 8. 防偏航 Review

- 本轮只强化 P2 学习边界 contract，没有新增产品入口。
- 没有把用户偏好接入排序权重或容量计算。
- 没有让 LLM / Daily Planner 变成计划 source of truth。
- 没有进入 P3/P4、商业化、提醒或前端实现。
- 这轮直接服务 P1/P2 主线：Today 可执行、AI 可解释、用户保留控制感。

---

## 9. 下一轮建议

P2 Task Semantic Estimate Feedback v1：把 Focus / 完成时长反馈更清晰地沉淀为“同类任务估时校准”的可解释学习信号，让 Chronos 更懂用户真实执行节奏，但仍只作为 deterministic Planning Engine 输入，不让 LLM 直接改排序。
