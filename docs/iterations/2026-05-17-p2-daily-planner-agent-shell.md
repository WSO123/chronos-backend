# Iteration: P2 Daily Planner Agent Shell

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Today 编排链路接入第一版 Daily Planner Agent shell：保留 Planning Engine v1 的 deterministic 排序和容量保护，由 LLM Agent 只输出结构化建议，并通过 `AIJob` 记录调用、校验、fallback 和可追踪元数据。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P2 Frontend API Contract](../chronos-p2-frontend-api-contract.md)

### 背景

Planning Engine v1 已经能基于价值、优先级、deadline、依赖、用户修正、行为反馈、容量和 Energy 生成 Today 顺序，并通过固定评估脚本保护排序质量。但 Chronos 的产品核心是 AI Execution OS，后续必须有真实 LLM / Agent 进入每日编排链路。

这轮不是直接让 LLM 接管排序，而是先把 Agent 接入点、structured output、provider registry、AIJob 追踪和业务层校验边界落下来。这样既能向真实 LLM 演进，又不会破坏 Today 的轻盈和可信。

### 目标

- 新增 `app/ai` 包，承载 provider、schema 和 agent shell。
- 定义 Daily Planner structured output schema。
- 新增 mock LLM provider，默认在 `AI_ENABLE_REAL_LLM=false` 时使用。
- Today 创建或 replan 时同步调用 Daily Planner Agent shell。
- 每次 planner agent 调用都记录 `AIJob(job_type=daily_planner)`。
- 业务层校验 LLM 输出，v1 不允许 LLM 改变任务集合、分区或排序。
- Strategy Detail `source` 暴露 `ai_job_id`，前端可按需查看 planner trace。
- Agent 失败或输出不合法时回退 Planning Engine v1，Today 仍可用。

### 非目标

- 不接真实 OpenAI / Anthropic / Gemini provider。
- 不让 LLM 直接创建、删除或修改 Task / Goal。
- 不让 LLM 绕过 Capture / Inbox 用户确认。
- 不允许 LLM 在 v1 重排任务或移动 `section`。
- 不把 Today 首屏改成 AI 调试面板。
- 不引入 LangGraph；本轮仍是普通 Agent function。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [x] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本轮把复杂度藏在系统后面：用户在 Today 看到的仍然是清楚的执行顺序和少量理由；Agent 的调用状态、provider、prompt_version 和 fallback 细节只进入 `AIJob` 和 Strategy Detail source，不抢占行动入口。

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

---

## 4. 需求范围

### 功能清单

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| LLM provider base | 定义 structured output provider 协议 | Must | 不写业务状态 |
| Mock provider | 默认返回可校验 structured output | Must | 本地和 CI 稳定 |
| Daily planner schema | 定义 mode、summary、primary_reason、items、confidence | Must | Pydantic 校验 |
| Daily Planner Agent | 接收 plan_context、candidates、strategy_seed，返回结构化结果 | Must | v1 普通 function |
| PlanningService integration | 创建 plan revision 时调用 Agent shell | Must | Planning Engine 仍是核心 |
| AIJob trace | 记录 provider、model、prompt_version、status、metadata | Must | Strategy Detail 可追踪 |
| Output validation | 禁止 v1 LLM 改任务集合、排序和分区 | Must | 防止不可控编排 |
| Fallback | Agent 失败或输出不合法时回退 deterministic plan | Must | Today 不被 LLM 可用性阻塞 |

### 用户故事

```text
作为 Chronos 用户，
我希望 AI 能逐步参与每日编排，但不突然打乱我对 Today 顺序的信任，
以便我仍然可以把它当成每天开始行动的可靠入口。
```

```text
作为前端开发者，
我希望 Strategy Detail source 能拿到 planner ai_job_id，
以便需要解释或排障时可以查看 AIJob 状态，但 Today 首屏仍然保持轻量。
```

```text
作为后端开发者，
我希望 LLM Agent 只返回结构化建议，最终由 PlanningService 校验和落库，
以便后续接真实 provider 时不会把业务状态交给模型直接决定。
```

```text
作为系统模块，
我希望 Daily Planner Agent 失败时可以使用 Planning Engine v1 fallback，
以便核心执行闭环不依赖 LLM 成功。
```

### 主要流程

```text
GET /today 或 POST /today/replan
-> Planning Engine v1 生成 deterministic candidates
-> Daily Planner Agent shell 输出 structured suggestions
-> PlanningService 校验 task_id / section / sort_order
-> 写入 DailyPlanItem / StrategySnapshot
-> 记录 AIJob
-> Strategy Detail source 返回 ai_job_id
```

Fallback 流程：

```text
Daily Planner Agent error / invalid output
-> AIJob.status = succeeded_with_fallback
-> 保留 Planning Engine v1 的顺序和理由
-> StrategySnapshot.score_factors 记录 planner_agent_status
-> Today / Focus / Report 继续可用
```

---

## 5. 数据与接口

### 新增代码结构

```text
app/ai/
  agents/
    daily_planner.py
  providers/
    base.py
    mock.py
    registry.py
  schemas/
    planning.py
```

### Daily Planner Output

```json
{
  "mode": "normal",
  "strategy_summary": "Keep a steady order.",
  "primary_reason": "The sequence balances value and capacity.",
  "items": [
    {
      "task_id": "uuid",
      "section": "pinned",
      "sort_order": 1,
      "recommendation_reason": "Protect this high-value task first."
    }
  ],
  "confidence": 0.72
}
```

### Strategy Detail Source

```json
{
  "strategy_snapshot_id": "uuid",
  "ai_job_id": "uuid",
  "model_name": "planning-engine-v1",
  "prompt_version": "p2-planning-engine-v1",
  "generated_at": "2026-05-17T09:00:00Z"
}
```

说明：

- `model_name` / `prompt_version` 仍指向落库的 Planning Engine snapshot。
- `ai_job_id` 指向本次 Daily Planner Agent shell 调用记录。
- 前端不需要在 Today 首屏展示 `ai_job_id`。

### AIJob Metadata

成功：

```json
{
  "mode": "sync_structured_shell",
  "planner_core": "planning-engine-v1",
  "output_applied": true,
  "confidence": 0.72,
  "item_count": 3
}
```

Fallback：

```json
{
  "mode": "sync_structured_shell",
  "planner_core": "planning-engine-v1",
  "output_applied": false,
  "fallback_reason": "daily_planner_agent_failed",
  "fallback_error_type": "RuntimeError"
}
```

---

## 6. 验收标准

- [x] `DailyPlannerAgent` mock provider 返回 Pydantic structured output。
- [x] `GET /today/strategy` 创建计划时记录 `AIJob(job_type=daily_planner)`。
- [x] `source.ai_job_id` 可以通过 `GET /api/v1/ai-jobs/{id}` 查询。
- [x] Agent 失败时 `AIJob.status=succeeded_with_fallback`，Today 仍返回 deterministic plan。
- [x] Agent 输出不合法时不会改变任务顺序或分区。
- [x] 文档同步说明 LLM 只提出建议，业务层负责校验和落库。

---

## 7. 验证计划

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
uv run python -m unittest discover -s tests
uv run python -m compileall app tests scripts
uv run python scripts/evaluate_planning_engine.py
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 8. 风险与边界

| 风险 | 说明 | 控制方式 |
| --- | --- | --- |
| LLM 破坏排序信任 | 模型可能重排任务或移动 section | v1 校验禁止改 task set、sort_order、section |
| LLM 失败影响 Today | provider 网络或输出格式异常 | `succeeded_with_fallback`，继续使用 Planning Engine |
| Today 变成调试台 | 前端可能展示过多 AIJob/score 信息 | 契约强调 Today 首屏不展示完整 trace |
| 真实 provider 接入过早 | 缺少脱敏、超时、重试和成本控制 | 本轮仅 mock provider，真实 provider 单独迭代 |

---

## 9. Review Checklist

- [x] 是否符合 Chronos “AI Execution OS” 定位，而不是普通 Todo App。
- [x] 是否保留用户控制感和修正权。
- [x] 是否没有让 LLM 直接写业务状态。
- [x] 是否保留 deterministic fallback。
- [x] 是否更新架构文档、LLM 文档、前端契约和测试。

---

## 10. 后续迭代建议

1. 增加真实 provider adapter，但默认仍关闭 `AI_ENABLE_REAL_LLM`。
2. 把 Daily Planner prompt 模板从代码字符串迁移到版本化 prompt 文档。
3. 增加 planner agent 输出离线评估，把 LLM 输出和 Planning Engine baseline 做对比。
4. 增加用户对排序建议的反馈入口，让后续 planner 学习偏好。
