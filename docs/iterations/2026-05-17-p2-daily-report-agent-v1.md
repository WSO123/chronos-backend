# Iteration: P2 Daily Report Agent v1

## 目标

把 Daily Report 的规则文案升级为 provider-backed structured Agent。它只基于当日执行统计生成复盘摘要和轻量建议，不反向修改任务、计划、目标或专注记录。

## 用户故事

作为 Chronos 用户，我希望每天复盘时看到一段温和、具体、可信的总结，知道今天发生了什么，以及明天应该怎么更容易开始。

## 开发者故事

作为后端开发者，我需要 Daily Report 复用统一 LLM provider、prompt registry、structured output 和 AIJob 生命周期，同时在 LLM 不可用时保持 Report 可生成。

## 系统故事

用户调用 Daily Report generate 后，系统先计算当日 `DailyReportMetrics`，写入或刷新 `DailyReport`，再创建 `AIJob(job_type=daily_report_generator)` 调用 `DailyReportAgent` 生成 `ai_summary` 和 `ai_suggestions`。Agent 失败时使用规则模板 fallback。无论成功或失败，都不修改 Task / Goal / DailyPlan / FocusSession 状态。

## 范围

- 新增 `DailyReportOutput` structured schema。
- 新增 `DailyReportAgent`。
- 新增 `daily_report` prompt registry entry。
- `ReportService.generate_daily_report` 接入 Agent、AIJob trace 和 fallback。
- `DAILY_REPORT_GENERATED` 事件 payload 增加 AIJob trace。
- 补充 agent 单测和 ReportService 回归测试。

## 非范围

- 不做 Weekly / Monthly Report Agent。
- 不做 Insight Detail Agent。
- 不让 LLM 改任务状态、计划排序或 Goal 进度。
- 不做真实 provider 验收。
- 不改变 Daily Report API response shape。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | 复用 `AIJobType.DAILY_REPORT_GENERATOR` | 该 job type 已存在，不需要新增 enum migration |
| 2026-05-17 | 先写入规则 fallback，再调用 Agent | 保证 Report 始终有可读结果 |
| 2026-05-17 | Agent 只更新 `DailyReport.ai_summary` 和 `ai_suggestions` | 保持复盘层不反向改变执行状态 |
| 2026-05-17 | 不改变 API response shape | 前端可继续按现有 Daily Report 契约接入 |

## 验证

```bash
uv run python -m unittest tests.test_daily_report_agent tests.test_report_me_services
```

## 后续

- Insight Detail Agent v1：基于行为数据、Daily/Weekly/Monthly Report 结果生成洞察解释，不直接改业务状态。
- Daily Planner Agent 仍暂不接管排序，继续让 Planning Engine v1 作为排序核心。
