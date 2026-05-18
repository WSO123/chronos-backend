# Iteration: P2 Semantic Planning Coverage v2

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

增强 Task Semantic Planning Agent 的结构化输出，让 LLM 更明确地描述任务复杂度、估时依据、最小推进动作、目标相关性和目标推进影响，并把这些信号作为 Planning Engine 的确定性输入。

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

### 背景

上一轮 `P2 Planning Objective v2` 已经让 Today 在容量约束下优先保护高价值目标推进。但 objective 的质量依赖输入信号质量：如果 LLM 只给粗粒度的目标对齐分和语义估时，系统仍然不够“懂任务为什么重要、今天最小该推进什么、估时为什么可信”。本轮强化语义信号覆盖度，让 LLM 输出更具体，但继续保持 bounded，不直接控制排序。

### 目标

- 升级 Task Semantic Planning Agent 到 v2。
- 新增结构化字段：复杂度原因、估时原因、目标推进影响、目标相关原因、最小推进分钟数。
- Planning Engine 消费这些字段，写入 `score_breakdown` 并纳入 objective semantic component。
- planner eval 增加 v2 语义覆盖场景，防止后续回归。

### 非目标

- 不新增 DB 表。
- 不让 LLM 改任务、目标、Today section 或排序。
- 不做 P3/P4、外部数据源、社交、商业化或前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
Goals -> Goal Detail -> Task Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

这轮继续把复杂度藏在后端：用户看到的是更可信的推荐时长、最小推进动作和 Strategy Detail 解释，不需要面对复杂参数。AI 变聪明，但不炫耀，不越权。

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
| Semantic Agent v2 | Prompt / schema 升级到 `p2-task-semantic-planning-agent-v2` | Must | 中文 prompt |
| Coverage Fields | 输出复杂度原因、估时原因、目标影响、目标相关原因、最小推进分钟数 | Must | 存入 raw_payload |
| Planning Engine Consumption | 把 v2 字段写入 score_breakdown 并纳入 objective | Must | 不让 LLM 直接排序 |
| Eval Baseline v9 | 新增 semantic coverage v2 场景 | Must | required scenarios 14 |

### 用户故事

```text
作为高自驱但时间有限的用户，
我希望 Chronos 不只是知道任务名字，而是理解它和目标的关系、今天最小能推进什么，
以便 Today 在时间不够时仍然帮我靠近重要目标。
```

```text
作为 Planning Engine，
我希望 LLM 只提供可验证的语义信号，
以便我能确定性地把语义理解转成排序、容量和解释，而不是让模型直接接管计划。
```

### 主要流程

```text
Task Detail / Today signal preparation
-> Task Semantic Planning Agent v2 生成结构化语义信号
-> TaskPlanningSignal 保存基础字段和 raw_payload v2 字段
-> Planning Engine 只读取 fresh signal
-> score_breakdown 暴露 semantic v2 字段
-> objective 使用 semantic goal impact / minimum viable minutes
-> Strategy Detail / task rationale 给出克制解释
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无新增表、无 migration。

新增字段不落模型列，保存在 `TaskPlanningSignal.raw_payload`：

```text
semantic_schema_version
complexity_reason
duration_reason
goal_progress_impact
goal_relevance_reason
minimum_viable_minutes
```

### 状态机变更

无。

### 事件变更

复用：

- `TASK_PLANNING_SIGNAL_GENERATED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/tasks/{task_id}/planning-signal` | 生成语义规划信号 | 无 | `planning_signal` 返回 v2 字段 |
| GET | `/api/v1/tasks/{task_id}` | Task Detail AI Info | 无 | `ai_info.planning_signal` 返回 v2 字段 |
| GET | `/api/v1/today/strategy` | Strategy Detail | 无 | factors 增加 `semantic_goal_impact_count` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [x] 修改 Prompt
- [x] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

- Agent 名称：Task Semantic Planning Agent
- 输入对象：Task context、Goal context、steps、dependency counts
- 输出对象：`TaskSemanticPlanningOutput`
- Pydantic schema：`app/ai/schemas/task_semantic_planning.py`
- fallback 策略：规则生成 v2 结构化字段
- 是否需要用户确认：不直接改业务状态，因此不需要确认；它只生成规划信号

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] Task Semantic Planning Agent prompt version 为 `p2-task-semantic-planning-agent-v2`。
- [x] Task Detail / generation response 返回 v2 语义字段。
- [x] Planning Engine 使用 `minimum_viable_minutes` 作为大任务的今日推进切片。
- [x] `goal_progress_impact=large` 转成 `semantic_goal_progress_impact_score` 并进入 objective。

### 数据验收

- [x] 不新增 DB migration。
- [x] v2 字段写入 `TaskPlanningSignal.raw_payload`。
- [x] 旧 signal 缺失 v2 字段时仍有安全默认值。

### 体验验收

- [x] Task Detail 仍只需展示推荐时长、最小动作和摘要，不变成信息仓库。
- [x] Strategy Detail 可解释 semantic goal impact，但 Today 不增加控制复杂度。
- [x] LLM 失败不会阻塞 Planning Engine。

---

## 8. 测试计划

### 单元测试

- [x] Task Semantic Planning Agent v2 schema / prompt registry
- [x] Task planning signal service 生成和 fallback
- [x] Planning Engine 消费 semantic coverage v2

### API 测试

- [x] `POST /api/v1/tasks/{task_id}/planning-signal`

### 集成测试

- [x] Planner eval v9
- [x] Planner eval policy

### 手动验证

```text
1. 创建高价值 Goal 下的大任务。
2. 生成 semantic planning signal。
3. 确认 Task Detail 返回 v2 字段。
4. 进入 Today / Strategy Detail，确认最小推进分钟数和目标推进语义进入 score_breakdown。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| v2 字段过多 | Task Detail 可能显得复杂 | 前端约束只展示少量字段；详细字段主要供 Strategy Detail / debug |
| LLM 误判目标影响 | 可能抬高不该抬高的任务 | Planning Engine 只把它作为一个分项，并保留确定性权重、用户优先级和容量约束 |
| schema 升级影响旧 signal | 旧数据缺字段 | raw_payload 读取有默认值，不强制迁移 |

### 关键取舍

- 取舍 1：不新增 DB 列，先用 raw_payload 承载 LLM 语义扩展。
- 取舍 2：v2 语义信号进入 objective，但不允许 LLM 直接排序。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-18 | Semantic Planning Agent 升级到 v2 | 提高目标相关性、估时和最小动作的结构化覆盖度 | Planning Engine objective 输入更强 |
| 2026-05-18 | v2 字段存 raw_payload | 避免过早 schema 固化和 migration | 需要 service 层提取字段 |
| 2026-05-18 | planner eval 升级到 v9 | 锁住语义覆盖能力 | required scenario count 从 13 到 14 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-18 | 扩展 semantic output schema | `app/ai/schemas/task_semantic_planning.py` | v2 fields |
| 2026-05-18 | 新增中文 prompt v2 | `app/ai/prompts/task_semantic_planning/` | prompt registry 指向 v2 |
| 2026-05-18 | service fallback / summary 支持 v2 | `app/services/task_planning_signal_service.py` | raw_payload 提取 |
| 2026-05-18 | Planning Engine 消费 v2 信号 | `app/services/planning_service.py` | score_breakdown / objective |
| 2026-05-18 | planner eval v9 | `scripts/`, `docs/planner-eval-baselines/` | 14 scenarios |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_task_semantic_planning_agent tests.test_task_goal_services.TaskGoalServiceTests.test_generate_task_planning_signal_creates_ai_job_and_task_detail_ai_info tests.test_task_goal_services.TaskGoalServiceTests.test_generate_task_planning_signal_falls_back_to_rule_signal tests.test_today_services.TodayServiceTests.test_planning_engine_consumes_semantic_coverage_v2_for_goal_impact_and_minimum_minutes tests.test_today_services.TodayServiceTests.test_planning_engine_slices_large_semantic_task_into_minimum_viable_progress`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id p2-semantic-coverage-v2 --jsonl-output /tmp/chronos-planner-semantic-coverage-v2.jsonl`
- [x] `uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-semantic-coverage-v2.jsonl`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- [ ] 无。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- P2 Execution Learning v2：用 Focus/Report 实际结果校准语义估时和 objective 权重。
- P2 Goal Progress Feedback v2：把语义 goal impact 与 Goal Detail 的推荐下一步更明确地串起来。
- P2 Semantic Planning Evaluation：后续可增加真实 provider 的固定样例验收，但仍不让 LLM 直接排序。
