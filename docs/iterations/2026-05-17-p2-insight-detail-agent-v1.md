# Iteration: P2 Insight Detail Agent v1

## 目标

把 Insight Detail 从纯规则洞察升级为 provider-backed structured Agent。它基于周级行为数据、规则洞察和效率时段生成更自然、克制、可信的洞察解释，但不改变任何业务状态。

## 用户故事

作为 Chronos 用户，我希望在 Me -> Insights -> Insight Detail 里看到清楚但不施压的行为洞察，知道本周哪些模式值得保留，哪些风险需要下周轻量调整。

## 开发者故事

作为后端开发者，我需要 Insight Detail 复用统一 LLM provider、prompt registry、structured output 和 AIJob 生命周期，同时让 LLM 失败时仍能返回规则洞察。

## 系统故事

用户调用 `GET /api/v1/insights/detail` 后，系统先生成 `rule-insight-v1` 的 overview、efficiency windows、behavior patterns、recommendations 和 strategy notes，再创建 `AIJob(job_type=insight_generator)` 调用 `InsightDetailAgent` 改写解释性文本。Agent 失败时保留规则结果。无论成功或失败，都不修改 Task / Goal / DailyPlan / FocusSession / DailyReport。

## 范围

- 新增 `InsightDetailOutput` structured schema。
- 新增 `InsightDetailAgent`。
- 新增 `insight_detail` prompt registry entry。
- 新增 `AIJobType.INSIGHT_GENERATOR` 和 Alembic enum migration。
- `InsightService.get_detail` 接入 Agent、AIJob trace 和 fallback。
- `InsightSourceResponse` 增加可选 AIJob trace 字段。
- 补充 agent 单测、InsightService fallback 测试和 Insight API 回归测试。

## 非范围

- 不新增持久化 Insight 表。
- 不让 LLM 修改事实指标：`overview` 和 `efficiency_windows` 仍由规则聚合产生。
- 不让 LLM 修改任务、目标、计划、专注记录或报告。
- 不做真实 provider 验收。
- 不把 Insight Detail 塞回 Today 首屏。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | 新增 `insight_generator` AIJobType | 让 Insight Agent 与 Daily Report / Strategy Explanation 分开追踪 |
| 2026-05-17 | 不持久化 Insight 表 | 当前是二级只读聚合，先避免过早建模 |
| 2026-05-17 | Agent 只改写解释性文本 | 保护事实层可信度，不让“聪明”压过“可信” |
| 2026-05-17 | fallback 保留 `rule-insight-v1` | Insight Detail 不能因 LLM 不可用而失败 |

## 验证

```bash
uv run python -m unittest tests.test_insight_detail_agent tests.test_insight_services tests.test_insight_api
```

## 后续

- Daily Planner Agent critique / suggestion：基于 Planning Engine 结果做建议，不直接接管排序。
- 后续真实 provider 验收时，Insight Detail 可加入 golden 输出检查，但不阻塞当前核心主线。
