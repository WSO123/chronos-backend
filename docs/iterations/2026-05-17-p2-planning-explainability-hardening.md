# Iteration: P2 Planning Explainability Hardening

## 目标

把 Planning Engine v1 的评分结果从“可调试的数字”进一步收敛成“Strategy Detail 可直接使用的解释契约”，让前端能解释“为什么今天先做这个”，而不需要自己读取和翻译原始权重。

## 用户故事

作为 Chronos 用户，我希望在 Strategy Detail 里看到清楚、克制、可信的排序原因，知道系统为什么保护某个任务、为什么滚动某些任务，而不是只看到一堆分数字段。

## 开发者故事

作为前端和后端开发者，我需要 Planning Engine 输出稳定的解释结构，这样 Strategy Detail 可以直接渲染核心信号，Today 首屏仍然保持轻盈，不变成复杂驾驶舱。

## 系统故事

Planning Engine 继续 deterministic 评分和排序，落库 `DailyPlanItem.score_breakdown`。Strategy Detail 在读取当前 plan 时，将原始 `score_breakdown` 归纳为整天级 `score_explanation` 和任务级 `dominant_factor` / `dominant_reason` / `score_signals`。Strategy Explanation Agent 只基于这些证据生成自然解释，不改变排序、section 或业务状态。

## 范围

- `score_breakdown` 增加 `score_version` 和 `score_band`，明确评分版本和粗粒度强度。
- `GET /today/strategy` 增加 `score_explanation`。
- `task_rationales[]` 增加：
  - `dominant_factor`
  - `dominant_reason`
  - `score_signals[]`
- Strategy Explanation Agent 上下文接收 `score_explanation` 和任务级 score signals。
- 更新 P2 前端合同、后端架构文档、LLM Agent 架构文档。
- 补充 Today service / Today API 测试。

## 非范围

- 不改变 Planning Engine 排序权重。
- 不让 LLM 改变任务顺序、section、状态或计划内容。
- 不把解释字段放进 Today 首屏展示。
- 不新增数据库表或迁移。
- 不接真实 provider 验收。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | Strategy Detail 增加 `score_explanation` | 给前端一个直接可渲染的整天级解释，而不是暴露 raw score |
| 2026-05-17 | 任务级解释保留在 `task_rationales[]` | Task Detail 不扩张成信息仓库，Strategy Detail 负责解释编排 |
| 2026-05-17 | `score_signals` 从 deterministic score_breakdown 归纳 | 保持 Planning Engine 是事实来源，LLM 只改写自然语言 |
| 2026-05-17 | 不调整评分权重 | 本轮只加解释契约，不改变行为，降低回归风险 |

## 验证

```bash
uv run python -m unittest tests.test_today_services tests.test_today_api
uv run python -m compileall app tests scripts
git diff --check
```

## 后续

- 可以补 planner eval 对 `score_explanation` / `score_signals` 的固定场景断言，确保解释不会随着后续权重调整漂移。
- 如果要接真实 provider，Strategy Explanation Agent 应继续只消费已归纳证据，不直接读取未约束的业务状态。
