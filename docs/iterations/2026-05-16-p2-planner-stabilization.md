# Iteration: P2 Planner Stabilization

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Done

## 1. 背景

P2 已经完成 Task Dependencies、Task Priority Adjustment、Strategy Detail 和 Today Insights Preview，但此前 Today planner 主要按 deadline、value、priority 做规则排序，尚未真正读取 P2 新增信号。

本轮目标是让调度层开始使用这些信号，同时继续遵守产品约束：

- Today 仍然是每日执行入口，不变成复杂驾驶舱。
- Strategy Detail 只做轻量解释，不改变计划。
- 用户修正 AI 判断后，系统能在下一次重排中体现偏好。
- 任务依赖存在时，前置任务应保护在被依赖任务之前。

## 2. 本轮范围

### Backend

- Today planner 读取 `TaskDependency`。
- 前置任务会被提升到 protected sequence，用于解锁后续任务。
- 被依赖任务保留可见，但排序在前置任务之后。
- Today planner 读取 `TASK_PRIORITY_ADJUSTED` ActivityEvent。
- 用户调整过的任务在推荐理由和 Strategy Detail factors 中体现。

### API

- `GET /api/v1/today` 响应结构不新增复杂字段，仍通过 sections 和 item `recommendation_reason` 承载排序结果。
- `GET /api/v1/today/strategy` 的 `factors` 新增：
  - `dependency_protected_count`
  - `user_adjusted_count`

### Docs

- 更新 backend architecture。
- 更新 P1/P2 frontend API contract。
- 新增本迭代记录。

## 3. 非目标

- 不接真实 LLM。
- 不做实时自动 replan。
- 不在 Today 首屏展示 score factors。
- 不做复杂依赖图调度、资源约束调度或日历时间块。

## 4. 行为规则

| 信号 | 行为 |
| --- | --- |
| 前置任务仍未完成 | 前置任务优先保护，排在依赖它的任务前 |
| 被依赖任务仍在计划内 | 保留可见，但推荐理由说明其依赖关系 |
| 用户调整 priority / value_level | 写入事件后，后续新计划或主动 replan 会读取该修正 |
| Today 已有 active plan | 不静默改版，只同步任务状态；用户需要主动 replan 才改变顺序 |

## 5. 验收标准

- 有依赖关系时，`prerequisite_task` 在 Today 中先于 `dependent_task`。
- Strategy Detail 返回 `dependency_protected_count`。
- 通过 priority adjustment 提升的任务在 Today recommendation reason 中体现用户修正。
- Strategy Detail 返回 `user_adjusted_count`。
- 原有 Today / Focus / Report 主链路测试继续通过。

## 6. 验证结果

| 验证项 | 结果 |
| --- | --- |
| `python -m unittest tests.test_today_services tests.test_today_api` | 13 tests OK |
| `python -m unittest discover -s tests` | 86 tests OK |
| `python -m compileall app tests scripts` | OK |
| `git diff --check` | OK |
| `alembic upgrade head` | OK |
| `scripts/smoke_p1_execution_loop.py` | OK |
| `scripts/smoke_p2_goal_insight_loop.py` | OK |

## 7. 风险与后续

- 当前依赖排序仍是轻量拓扑深度，不处理复杂资源约束。
- `TASK_PRIORITY_ADJUSTED` 当前只作为“用户修正”信号，不做长期学习权重。
- 后续可将这些 signals 传入真实 LLM planner adapter，但必须保留规则 fallback。
