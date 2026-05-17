# Iteration: P2 Daily Planner Critique / Suggestion

## 目标

把 Daily Planner Agent 从 structured shell 升级为 critique / suggestion 能力：LLM 可以审阅 Planning Engine v1 的结果并给出轻量建议，但不能接管排序、不能移动 section、不能改变任务集合。

## 用户故事

作为 Chronos 用户，我希望在 Strategy Detail 里看到 AI 对今日编排的轻量审阅，知道这个计划是否可以直接开始，以及有哪些小建议能让我更稳地执行。

## 开发者故事

作为后端开发者，我需要 Daily Planner Agent 的建议与 Planning Engine 排序解耦，这样真实 LLM 可以参与判断表达，但不会破坏 deterministic planner core。

## 系统故事

系统先由 Planning Engine v1 生成 deterministic candidates，再调用 `DailyPlannerAgent` 生成策略摘要、推荐理由、`review_summary` 和 `suggestions`。`PlanningService` 校验 task_id、section、sort_order 完全一致后，才把 review 写入 `StrategySnapshot.score_factors`，并在 Strategy Detail 中以 `planner_review` 返回。

## 范围

- 扩展 `DailyPlannerOutput`，增加 `review_summary` 和 `suggestions`。
- 更新 Daily Planner prompt，明确 critique / suggestion 不能覆盖 deterministic order。
- `PlanningService` 将 planner review 写入 `StrategySnapshot.score_factors`。
- Strategy Detail 增加 `planner_review` 响应字段。
- 更新 P2 前端合同、LLM 架构和后端架构文档。
- 补充 Daily Planner Agent / Today service / Today API 测试。

## 非范围

- 不让 LLM 重排任务。
- 不让 LLM 移动 `section`。
- 不让 LLM 新增、删除或替换 task id。
- 不把 planner review 放进 Today 首屏。
- 不做真实 provider 验收。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | `planner_review` 只出现在 Strategy Detail | 避免 Today 变复杂驾驶舱 |
| 2026-05-17 | Review 写入 `StrategySnapshot.score_factors` | 不新增持久化表，跟随当前 plan revision |
| 2026-05-17 | 继续校验 task_id / section / sort_order | Planning Engine 仍是排序核心 |
| 2026-05-17 | suggestion 表示建议，不表示自动执行 | 保留用户控制感 |

## 验证

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
```

## 后续

- 可以继续补 Planning Engine / Agent 的 critique eval case，评估 LLM 建议质量，但不阻塞核心闭环。
- 真实 provider 验收后置，仍需使用现有 smoke / acceptance 记录链路。
