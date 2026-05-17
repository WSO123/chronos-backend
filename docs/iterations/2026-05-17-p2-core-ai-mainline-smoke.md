# Iteration: P2 Core AI Mainline Smoke

## 目标

把已经落地的核心 AI 主线串成一个可复跑 smoke：Capture Parser -> Inbox confirmation -> Today Planning / Daily Planner -> Strategy Explanation -> Task Breakdown -> Focus -> Daily Report Agent -> Insight Detail Agent。

这轮不新增业务能力，而是补一条开发者验证入口，证明 Chronos 当前最重要的 AI 执行闭环不是散点能力。

## 用户故事

作为 Chronos 用户，我希望系统可以从输入、编排、解释、拆解、执行、复盘到洞察连续工作，而不是每个 AI 能力只能单独演示。

## 开发者故事

作为后端开发者，我需要一个本地 smoke 在一次运行里验证核心 bounded agents 都被真实调用、都写入 `AIJob`，并且最终仍然通过用户确认和执行闭环落到业务状态。

## 系统故事

系统用一个合成用户创建 Capture，经 Capture Parser 进入 Inbox；用户确认后生成 Task；Today 调用 Planning Engine 和 Daily Planner；Strategy Detail 调用 Strategy Explanation 并返回 `planner_review`；Task Detail 前由 Task Breakdown 生成可编辑步骤；Focus 完成后 Daily Report Agent 和 Insight Detail Agent 生成只读复盘文本。Smoke 最后直接查询 `ai_jobs`，校验所有核心 agent 的状态。

## 范围

- 新增 `scripts/smoke_core_ai_mainline.py`。
- 验证以下 AIJob 类型都存在且处于成功状态：
  - `capture_parser`
  - `daily_planner`
  - `strategy_explanation`
  - `task_breakdown`
  - `daily_report_generator`
  - `insight_generator`
- 输出结构化 JSON evidence，包含核心实体 id、Strategy source、planner review 和 AIJob 摘要。
- `verify_local.py --smoke ai-mainline` 支持显式运行。
- 放宽旧 P1 smoke 对 Task Breakdown AIJob 的状态判断，兼容 agent 成功态和受控 fallback 态。
- 补充 smoke helper 单元测试。

## 非范围

- 不把该 smoke 放入默认 CI。
- 不把该 smoke 放入 `--all-smoke`。
- 不调用真实外部 LLM provider。
- 不新增业务表或业务接口。
- 不改变 Planning Engine 排序规则。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | 新增独立 `ai-mainline` smoke | 旧 P1/P2/P3 smoke 验证业务路径，但没有集中证明 bounded agents 主线 |
| 2026-05-17 | 通过 API 执行业务动作，通过 DB 查询 AIJob | API 是真实业务入口，DB 查询能覆盖 Daily Report 等未直接暴露 job id 的能力 |
| 2026-05-17 | 接受 `succeeded` 和 `succeeded_with_fallback` | fallback 是当前设计的一等受控路径，但 evidence 会暴露具体状态 |
| 2026-05-17 | 不加入 `--all-smoke` | 避免日常全量 smoke 越来越重 |

## 验证

```bash
uv run python -m unittest tests.test_core_ai_mainline_smoke_script
uv run python -m compileall scripts tests
git diff --check
```

如本地数据库已启动且已完成迁移，可手动运行：

```bash
uv run python scripts/smoke_core_ai_mainline.py
uv run python scripts/verify_local.py --smoke ai-mainline
```

## 后续

- 下一轮应回到核心功能本身：检查 Planning Engine 的评分 explainability 是否足够支持前端 Strategy Detail，而不是继续扩张外围工具。
- 如果接真实 provider，再用现有 provider acceptance 流程记录 smoke / fallback / eval 证据。
