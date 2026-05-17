# Iteration: P2 Strategy Explanation Agent v1

## 目标

把 Strategy Detail 的规则解释升级为 provider-backed structured Agent。它只解释 Planning Engine v1 的 `score_breakdown`、strategy factors 和 task rationales，不改变排序、不改 Task / Goal / DailyPlan 状态。

## 用户故事

作为 Chronos 用户，我希望在 Strategy Detail 里看到清楚、克制、可信的解释，知道为什么今天先做这些任务，而不是只看到一组分数或生硬规则。

## 开发者故事

作为后端开发者，我需要 Strategy Explanation 复用统一 LLM provider、prompt registry、structured output 和 AIJob 生命周期，同时把解释能力与 Daily Planner 的计划生成能力分开追踪。

## 系统故事

用户调用 `GET /today/strategy` 后，系统读取当前 `StrategySnapshot`、`DailyPlanItem.score_breakdown` 和聚合 factors，创建 `AIJob(job_type=strategy_explanation)`，调用 `StrategyExplanationAgent` 生成 1-4 条解释。Agent 失败时回退规则解释。无论成功或失败，都不修改计划排序和任务状态。

## 范围

- 新增 `StrategyExplanationOutput` structured schema。
- 新增 `StrategyExplanationAgent`。
- 新增 `strategy_explanation` prompt registry entry。
- 新增 `AIJobType.STRATEGY_EXPLANATION` 和 Alembic enum migration。
- `PlanningService.get_strategy_detail` 接入 Agent 解释和 fallback。
- `StrategyDetailSourceResponse` 增加 explanation AIJob trace 字段。
- 补充 agent 单测和 Today strategy 回归测试。

## 非范围

- 不让 LLM 重排任务。
- 不让 LLM 修改 StrategySnapshot / DailyPlan / Task。
- 不做真实 provider 验收。
- 不把 score 权重完整暴露给 Today 首屏。
- 不做 Insight / Report 复盘生成。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | Strategy Explanation 独立于 Daily Planner AIJob | 区分“生成计划”和“解释计划” |
| 2026-05-17 | `source.ai_job_id` 继续指向 Daily Planner | 保持现有 API 语义兼容 |
| 2026-05-17 | 新增 `source.explanation_ai_job_id` | 让解释 Agent 可追踪 |
| 2026-05-17 | Agent 失败回退规则解释 | Strategy Detail 不能因 LLM 不可用而失败 |

## 验证

```bash
uv run python -m unittest tests.test_strategy_explanation_agent tests.test_today_services tests.test_today_api
```

## 后续

- Insight / Report Agent v1：基于行为数据生成复盘文字，不直接改业务状态。
- Daily Planner Agent 暂不接管排序，继续让 Planning Engine v1 作为排序核心。
