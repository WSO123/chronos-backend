# Iteration: P2 Planner Feedback Preference Signal v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

把用户对 Planner Review 建议的多次接受 / 忽略压缩成确定性偏好摘要，并在 Strategy Detail 中展示为 `planner_review.feedback_summary`。

---

## 2. 背景与目标

上一轮已经能记录用户对单条 Planner Review suggestion 的反馈，但这些反馈仍是事件列表。Chronos 要“越来越懂用户”，需要把事件压缩成可解释、可追踪、可回滚的偏好信号，同时不能让 LLM 直接接管排序。

### 目标

- 基于 `PLANNER_REVIEW_FEEDBACK_RECORDED` 生成 deterministic `preference_summary`。
- 支持容量边界相关偏好：
  - `capacity_flexibility_preferred`
  - `capacity_flexibility_emerging`
  - `rollover_boundary_preferred`
  - `rollover_boundary_emerging`
  - `neutral`
- 把非 neutral 摘要暴露到 `planner_review.feedback_summary`。
- 把摘要放入 Daily Planner Agent 的只读 `review_context.user_feedback.preference_summary`。

### 非目标

- 不直接调整 Planning Engine 排序权重。
- 不自动扩大今日容量。
- 不新增用户画像表。
- 不做 P3/P4、商业化、前端页面或提醒。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Planner Review Feedback -> Preference Summary -> Strategy Detail
```

本轮让用户看到“系统确实读到了我的偏好”，但仍把行动入口保持在 Today / Focus，不把 Strategy Detail 变成控制面板。

### 用户故事

```text
作为一个对 AI 建议会持续修正的用户，
我希望 Chronos 能把我多次接受或忽略的建议总结成清晰偏好，
以便后续审阅更贴近我的执行习惯。
```

```text
作为 Planning Engine，
我希望用户偏好先以确定性摘要进入解释层，
以便保持排序 source of truth 不被 LLM 隐式替代。
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
| Preference summary | 从 accepted / ignored 聚合稳定偏好 | Must | deterministic |
| Strategy Detail exposure | `planner_review.feedback_summary` | Must | 只在 Strategy Detail |
| Agent context | `review_context.user_feedback.preference_summary` | Must | 只读 |
| Mock adaptation | 根据 summary 调整建议文案 | Should | 不改排序 |

### 主要流程

```text
用户多次反馈 planner suggestion
-> ActivityEvent 聚合 accepted / ignored count
-> 生成 preference_summary
-> Daily Planner Agent 只读该 summary
-> Strategy Detail 展示 feedback_summary
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [x] Schemas
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

继续使用：

```text
PLANNER_REVIEW_FEEDBACK_RECORDED
```

---

## 6. 验收标准

- [x] 2 次忽略 `respect_rollover` 会生成 `capacity_flexibility_preferred`。
- [x] 2 次接受 `respect_rollover` 会生成 `rollover_boundary_preferred`。
- [x] 单次反馈只生成 emerging 信号。
- [x] neutral 不展示在 `planner_review.feedback_summary`。
- [x] `feedback_summary` 不触发 replan，不修改任务或容量。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
git diff --check
```

---

## 8. 防偏航 Review

- 本轮只把反馈压缩为解释层信号。
- 没有新增外部集成、提醒、商业化或前端页面。
- 没有让 LLM 直接排序。
- 没有把用户反馈变成立刻改 plan 的隐藏控制面。

---

## 9. 下一轮建议

P2 Planner Preference Strategy Detail Copy v1：基于 `feedback_summary` 优化 Strategy Explanation Agent 的中文解释，让用户更清楚 Chronos 如何尊重偏好，但仍不改变排序。
