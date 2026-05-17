# Iteration: P2 Task Semantic Planning Signals v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 LLM 的语义理解沉淀为可追踪的 Task Planning Signal，并让 Planning Engine 在 Today 编排中读取这些信号。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

当前 Chronos 已经具备 Capture -> Inbox -> Today -> Task Detail -> Focus -> Report 的基础闭环，也有 Capture Parser、Task Breakdown、Strategy Explanation 等 bounded agents。但 AI 的核心价值仍偏“拆任务 / 解释”，还没有真正把语义理解变成 Today 编排的输入。

本轮回到主线：Chronos 的核心不是做更多外围功能，而是每天帮用户把最高价值目标推进成今天做得出来的一步。

### 目标

- 新增 Task Semantic Planning Agent，产出结构化语义信号。
- 新增 TaskPlanningSignal 持久化模型，保留 AIJob 追踪。
- Task Detail 轻量展示最新 planning signal，不变成信息仓库。
- Planning Engine 读取语义信号，影响评分、估时、保护区和解释。

### 非目标

- 不做 P3/P4 的提醒、数据源、社交、商业化。
- 不让 LLM 直接改 Today 排序、Task 状态或 Goal 状态。
- 不让 Task Detail 变成完整 AI 调试面板。
- 不做真实 provider 验收扩张。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [x] Goals
- [x] AI Agent

### 产品人格

本轮把“聪明”藏在 Planning Engine 背后：用户只看到更合理的推荐时长、最小推进动作和排序解释，不需要面对复杂控制面板。

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
| Task Semantic Planning Agent | 读取任务、目标、步骤、依赖，输出语义规划信号 | Must | bounded structured output |
| TaskPlanningSignal | 保存复杂度、认知负荷、目标对齐、语义估时、最小推进动作 | Must | 可追踪、可解释 |
| Task Detail AI Info | 返回最新 planning_signal 和推荐时长 | Must | 轻量展示 |
| Planning Engine semantic scoring | 把语义信号转成 `semantic_*` score_breakdown | Must | LLM 不直接排序 |
| Strategy Detail factors | 暴露 semantic signal count / protected count | Should | 用于解释 |

### 用户故事

```text
作为高自驱但规划成本过高的用户，
我希望系统能理解“哪个任务真正推进目标、今天最小能做什么”，
以便在时间不够时也能优先推进高价值目标。
```

```text
作为 Planning Engine，
我希望读取结构化语义信号，
以便在保持确定性排序的前提下，把 LLM 理解转成可解释评分。
```

### 主要流程

```text
Task Detail / explicit API
-> Task Semantic Planning Agent
-> TaskPlanningSignal + AIJob
-> Today Replan / Get Today
-> Planning Engine reads semantic signal
-> score_breakdown exposes semantic contribution
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
TaskPlanningSignal {
  user_id
  task_id
  ai_job_id
  source
  task_type
  complexity
  cognitive_load
  energy_fit
  blocking_risk
  estimated_duration_min
  duration_confidence
  goal_alignment_score
  semantic_priority_score
  breakdown_recommended
  minimum_viable_step
  semantic_summary
  confidence
  raw_payload
}
```

### 状态机变更

无。

### 事件变更

- `TASK_PLANNING_SIGNAL_GENERATED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/tasks/{task_id}/planning-signal` | 生成任务语义规划信号 | empty | `ai_job + planning_signal` |
| GET | `/api/v1/tasks/{task_id}` | 返回 Task Detail | empty | `ai_info.planning_signal` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [ ] 涉及已有 Agent
- [x] 新增 Agent
- [x] 修改 Prompt
- [x] 修改 Structured Output
- [x] 修改 fallback

### Agent 设计

- Agent 名称：TaskSemanticPlanningAgent
- 输入对象：Task + Goal + Steps + Dependency counts
- 输出对象：TaskSemanticPlanningOutput
- Pydantic schema：`app/ai/schemas/task_semantic_planning.py`
- fallback 策略：规则估算任务类型、复杂度、认知负荷、目标对齐、语义优先级、最小推进步骤
- 是否需要用户确认：不直接改业务状态；作为 Planning Engine 输入和 Task Detail 展示，不创建任务、不改任务

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询

---

## 7. 验收标准

- [x] 生成 planning signal 会创建 `AIJob(job_type=task_semantic_planning)`。
- [x] Task Detail 返回最新 planning signal。
- [x] 无用户估时时，Today 可使用语义估时。
- [x] 高目标对齐、阻塞风险高的任务可以被 Planning Engine 放入保护区。
- [x] Strategy Detail 暴露 semantic signal 相关 factors。
- [x] score_breakdown 包含 `semantic_*` 分项，便于解释。

---

## 8. 主线偏离 Review

本轮没有继续 P3/P4、商业化、复杂 auth、前端页面或 provider 验收扩张。它直接服务核心主线：

```text
AI 语义理解
-> 可追踪 planning signal
-> Planning Engine 可解释评分
-> Today 更会保护高价值目标的最小推进动作
```

仍然没有让 LLM 直接接管排序；排序源头保持 deterministic Planning Engine。这符合“聪明但可信”的产品人格。

---

## 9. 后续迭代

- Goal-Oriented Minimum Viable Progress：当一个高价值 Goal 今天无法完整推进时，自动保护最小推进动作。
- Duration Calibration：用 Focus 实际时长修正未来语义估时。
- Planning Signal Refresh Policy：当 Task / Goal / dependency 改动后，识别哪些 signal 需要刷新。
