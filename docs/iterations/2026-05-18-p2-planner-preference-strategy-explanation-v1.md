# Iteration: P2 Planner Preference Strategy Explanation v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

让 Strategy Explanation Agent 读取 `planner_review.feedback_summary`，用中文解释 Chronos 如何尊重用户最近形成的 planner 偏好，但仍不改变排序、容量或任务状态。

---

## 2. 背景与目标

上一轮已经把 Planner Review 的多次接受 / 忽略压缩成确定性 `feedback_summary`，并在 Strategy Detail 暴露。缺口在于：Strategy Detail 的 `explanation[]` 仍只解释容量、依赖、目标和执行历史，没有把“系统已经读到你的反馈”讲清楚。

Chronos 的产品人格要求聪明但不炫耀、可信但不施压。因此本轮只做解释增强，让用户知道偏好被尊重，同时明确系统不会自动替用户修改计划。

### 目标

- Strategy Explanation Agent 接收 `feedback_summary`。
- 规则 fallback 也能解释 `capacity_flexibility_*` / `rollover_boundary_*`。
- `AIJob.job_metadata` 记录本次解释使用的 `planner_feedback_summary`。
- Prompt 明确：反馈摘要是解释层信号，不代表自动修改计划。

### 非目标

- 不改变 Planning Engine 排序权重。
- 不自动扩大今日容量。
- 不自动 replan。
- 不新增用户画像表。
- 不做 P3/P4、商业化、前端页面或提醒。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Explanation -> Task Detail -> Focus
```

本轮增强 Strategy Detail 的可信解释，不增加 Today 首屏复杂度。

### 用户故事

```text
作为持续修正 AI 建议的用户，
我希望 Strategy Detail 能说明 Chronos 如何理解我的反馈，
以便我相信系统在学习，但仍由我保留控制感。
```

```text
作为 Strategy Explanation Agent，
我希望读取确定性的 feedback_summary，
以便生成自然中文解释，同时不直接改变计划。
```

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱。
- [x] 不让 Task Detail 变成信息仓库。
- [x] 不让 Focus 变成控制面板。
- [x] 不让解释抢走行动感。
- [x] 不让“聪明”压过“可信”。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Agent input | `StrategyExplanationAgent.run(..., feedback_summary=...)` | Must | 只读 |
| Rule fallback copy | fallback explanation 加入偏好说明 | Must | 本地稳定 |
| AIJob metadata | 记录 `planner_feedback_summary` | Should | 可追踪 |
| Prompt boundary | 中文 prompt 明确不自动改计划 | Must | 产品人格 |

### 主要流程

```text
StrategySnapshot.score_factors.planner_feedback_summary
-> Strategy Explanation Agent input
-> explanation[] 增加偏好说明
-> Strategy Detail 返回
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无。

---

## 6. 验收标准

- [x] `capacity_flexibility_preferred` 会在 `explanation[]` 中解释“可以手动增加可用时间，但不会自动把滚动任务拉回今天”。
- [x] `rollover_boundary_preferred` 会在 `explanation[]` 中解释“继续保护主序列和滚动边界”。
- [x] Strategy Explanation AIJob metadata 记录 `planner_feedback_summary`。
- [x] Agent prompt 明确反馈摘要不是自动修改计划。
- [x] planner eval 无 regression / change。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_strategy_explanation_agent tests.test_today_services tests.test_today_api
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
git diff --check
```

---

## 8. 防偏航 Review

- 本轮只增强 Strategy Detail 的解释层。
- 没有新增 API / DB / worker。
- 没有让 LLM 改排序。
- 没有让偏好摘要变成隐藏控制面。
- 没有进入 P3/P4、商业化或前端实现。

---

## 9. 下一轮建议

P2 Planner Preference Eval Scenario v1：把 feedback preference 的解释行为补进 planner / strategy 评估 fixture，防止后续重构丢失“用户偏好被解释但不改计划”的边界。
