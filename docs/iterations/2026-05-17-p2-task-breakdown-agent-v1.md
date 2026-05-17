# Iteration: P2 Task Breakdown Agent v1

## 目标

把 Task Breakdown 从 P1 rule/mock 拆解升级为 provider-backed structured Agent。它负责把一个 Task 拆成少量可执行步骤，并落成可编辑的 `TaskStep`。

## 用户故事

作为 Chronos 用户，我希望在一个任务太大、不好开始时，系统能把它拆成几步清楚的小动作，让我能直接进入 Focus，而不是继续面对一个笼统任务。

## 开发者故事

作为后端开发者，我需要 Task Breakdown 复用统一 LLM provider、prompt registry、structured output 和 AIJob 生命周期，且失败时仍能提供 rule fallback 步骤，保证主执行闭环不中断。

## 系统故事

用户调用 `POST /tasks/{task_id}/breakdown` 后，系统创建 `AIJob(job_type=task_breakdown)`，调用 `TaskBreakdownAgent` 生成结构化步骤，然后写入 `TaskStep`。如果任务已有步骤，系统不调用 Agent、不覆盖已有步骤，并返回空 `created_steps`。如果 Agent 失败，系统使用规则步骤 fallback。

## 范围

- 新增 `TaskBreakdownOutput` structured schema。
- 新增 `TaskBreakdownAgent`。
- 新增 `task_breakdown` prompt registry entry。
- `TaskService.breakdown_task` 接入 Agent 优先、rule fallback。
- `AIJob` 记录 provider、model、prompt version、prompt checksum、latency、usage、fallback reason。
- `TaskBreakdownResponse.ai_job` 增加 provider / model / prompt_version。
- 补充 agent 单测和 Task service/API 回归测试。

## 非范围

- 不做异步 worker。
- 不覆盖已有用户步骤。
- 不做真实 provider 验收。
- 不做复杂项目管理式拆解。
- 不改变 Task priority、deadline、goal 或 status。

## 决策

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-17 | Agent 输出直接落成 `TaskStep` | Task Breakdown 是低风险建议型能力，步骤本身可编辑 |
| 2026-05-17 | 已有步骤时不调用 Agent | 保持用户控制感，避免覆盖用户已有结构 |
| 2026-05-17 | Agent 失败时生成 rule fallback steps | 拆解能力不因 provider 不可用中断 |
| 2026-05-17 | 步骤数量限制为最多 6 个 | 避免 Task Detail 变成信息仓库 |

## 验证

```bash
uv run python -m unittest tests.test_task_breakdown_agent tests.test_task_goal_services tests.test_task_goal_api
```

## 后续

- Strategy Explanation Agent v1：基于 Planning Engine `score_breakdown` 生成自然解释，不改变排序。
- Insight / Report Agent v1：基于已有行为数据生成复盘文字，不直接改业务状态。
