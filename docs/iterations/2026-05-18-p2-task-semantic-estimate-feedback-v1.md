# Iteration: P2 Task Semantic Estimate Feedback v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

把同类任务的真实执行时长显式沉淀为 `semantic_estimate_feedback`，让 Planning Engine 可以解释“为什么本次估时更保守 / 更贴近用户节奏”，同时明确它不会覆盖任务原始估时，也不会让 LLM 直接排序。

---

## 2. 背景与目标

Chronos 的主线不是做一个任务列表，而是逐步变成更懂用户的每日执行系统。此前已经有 `TaskPlanningSignal.task_type` 和基于历史任务的 personalization，但字段语义偏泛，后续开发不容易看出它到底是“同类任务估时反馈”。

本轮只把已有能力产品化和契约化：真实执行时长可以校准本次 Today item 的估时和 Strategy Detail 解释，但不能修改 Task 原始估时、任务状态、目标状态或让 LLM 接管排序。

### 目标

- 在 personalization profile 中沉淀同类任务估时统计：
  - `estimated_total_min`
  - `actual_total_min`
  - `average_estimate_delta_min`
- 在 Today item `score_breakdown` 暴露：
  - `semantic_estimate_feedback_applied`
  - `semantic_estimate_feedback_source`
  - `semantic_estimate_feedback_contract`
- Strategy task rationale 文案说明真实执行时长带来的估时校准。
- Planner eval 的 `semantic_history_personalizes_duration` 场景覆盖该 contract。

### 非目标

- 不新增数据库表。
- 不修改 `Task.estimated_duration_min`。
- 不改变 LLM agent、prompt 或 provider。
- 不让 LLM 直接排序。
- 不做 P3/P4、外部集成、商业化或前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Task Semantic Signal
-> Focus / Complete actual duration
-> Semantic estimate feedback
-> Planning Engine duration estimate
-> Today / Strategy Detail explanation
```

这轮服务于“Chronos 越来越懂用户”的主线：系统通过真实执行数据更懂用户的任务耗时，但依旧保持可解释、可测试、可回退。

### 用户故事

```text
作为经常低估某类任务耗时的用户，
我希望 Chronos 能从我过去真实执行时长中学习，
以便下次安排同类任务时更接近现实，而不是继续给出过于乐观的估时。
```

```text
作为 Planning Engine，
我希望同类任务估时反馈只校准本次计划估时和解释，
以便不覆盖用户原始任务数据，也不让 LLM 直接接管排序。
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
| Estimate feedback stats | 历史 estimated / actual 聚合 | Must | 复用 Task / TaskPlanningSignal |
| Score breakdown fields | Today item 暴露估时反馈字段 | Must | 可解释 |
| Learning contract | 明确不能覆盖任务原估时 / 不能让 LLM 直接排序 | Must | 防偏航 |
| Rationale copy | 解释平均估时偏差 | Should | 中文 |
| Planner eval assertion | 评测场景覆盖 contract | Should | 防回归 |

### 主要流程

```text
历史 writing 任务：估时 30，实际 60
历史 writing 任务：估时 30，实际 50
当前 writing 任务：估时 30
-> Planning Engine 识别同类任务平均多 25 分钟
-> 本次 Today 使用更保守估时
-> score_breakdown 暴露 semantic_estimate_feedback_contract
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
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

无。继续复用任务完成 / Focus 完成后已经累计的 `Task.actual_duration_min`。

---

## 6. 验收标准

- [x] 同类任务历史估时 60 分钟、实际 110 分钟时，当前任务暴露 `personalization_average_estimate_delta_min=25`。
- [x] 当前任务暴露 `semantic_estimate_feedback_applied=true`。
- [x] contract 明确 `task_mutation_allowed=false`。
- [x] contract 的 `cannot_affect` 包含 `task_estimated_duration_min` 和 `llm_direct_sort_order`。
- [x] Strategy task rationale 说明“平均比估时多约 25 分钟”。
- [x] Planner eval 场景覆盖该 contract。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_today_services tests.test_planning_engine_evaluation
uv run python scripts/verify_local.py --planner-eval-policy
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
git diff --check
```

---

## 8. 防偏航 Review

- 本轮没有新增 Agent、DB、外部集成或前端页面。
- 没有让 LLM 直接排序。
- 没有覆盖 `Task.estimated_duration_min`。
- 没有把个性化学习做成黑盒画像表。
- 它只强化 P2 智能编排主线：用真实执行数据让 Today 更贴近用户可完成的一天。

---

## 9. 下一轮建议

P2 Estimate Feedback Strategy Summary v1：把 `semantic_estimate_feedback` 聚合到 Strategy Detail factors / score explanation 中，帮助用户在策略层看到“本次有几个任务读取了真实执行估时反馈”，但仍保持 Today 首屏轻量。
