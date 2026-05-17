# Iteration: P2 Capture Parser Agent v1

## 目标

把 Capture Parser 从 P1 rule parser 升级为第一个真实 Agent 接入点。它负责把用户输入解析成可确认的 Inbox 候选项，但不直接创建 Task / Goal，继续保留用户确认权。

## 用户故事

作为 Chronos 用户，我希望随手输入一句话后，系统能更聪明地判断这是任务、目标、想法还是未知内容，并把结果放进 Inbox 等我确认，而不是让我一开始就手动分类。

## 开发者故事

作为后端开发者，我需要 Capture Parser 复用统一 LLM provider、prompt registry、structured output 和 AIJob 生命周期，这样后续 Task Breakdown / Strategy Explanation / Insight Agent 可以沿用同一条 Agent 接入方式。

## 系统故事

Capture 创建后，系统先生成 `CaptureInput`，再创建 `AIJob(job_type=capture_parser)`，调用 `CaptureParserAgent` 生成结构化输出。输出只写入 `AIParseResult` 和 `InboxItem`。如果 Agent 或 provider 失败，系统使用 rule parser fallback，仍然生成 InboxItem。

## 范围

- 新增 `CaptureParserOutput` structured schema。
- 新增 `CaptureParserAgent`。
- 新增 `capture_parser` prompt registry entry。
- `CaptureService` 接入 Agent 优先、rule fallback。
- `AIJob` 记录 provider、model、prompt version、prompt checksum、latency、usage、fallback reason。
- 补充 agent 单测和 Capture/Inbox service 单测。

## 非范围

- 不接语音 / 图片真实多模态解析。
- 不让 Capture 直接创建 Task / Goal。
- 不改 Inbox confirm 逻辑。
- 不做真实 provider 验收。
- 不继续扩展 Daily Planner tooling。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | Capture Parser 作为第一个真实 Agent | 价值明显，风险最低，输出仍进入 Inbox |
| 2026-05-17 | 默认 mock provider 使用 rule parser 输出作为 mock output | 本地开发稳定，不依赖真实 LLM |
| 2026-05-17 | Agent 失败时 `AIJob.status=succeeded_with_fallback` | Capture 不能因为 LLM 不可用而中断输入闭环 |
| 2026-05-17 | `result_entity` 指向 InboxItem | Agent 的业务结果是待确认项，不是正式 Task / Goal |

## 验证

```bash
uv run python -m unittest tests.test_capture_parser_agent tests.test_capture_inbox_services
uv run python -m compileall app/ai app/services tests/test_capture_parser_agent.py tests/test_capture_inbox_services.py
```

## 后续

- Task Breakdown Agent v1：把当前 rule/mock 拆解升级为 provider-backed structured Agent。
- Strategy Explanation Agent v1：只基于 Planning Engine `score_breakdown` 生成解释，不改排序。
