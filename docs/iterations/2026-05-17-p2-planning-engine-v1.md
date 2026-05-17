# Iteration: P2 Planning Engine v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 Today 从“规则排序”升级为可解释的 Planning Engine v1：基于价值、优先级、截止时间、依赖、用户修正、历史行为、当日容量和 Energy 信号生成今日主执行序列，并把超出容量的任务滚动到未来。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P2 Frontend API Contract](../chronos-p2-frontend-api-contract.md)
- [x] [Chronos P3 Frontend API Contract](../chronos-p3-frontend-api-contract.md)

### 背景

P1/P2/P3 已经具备 Task、Goal、Today、Focus、Report、Energy 和外部数据源底座，但 Today 的核心还停留在较轻的规则排序。对 Chronos 来说，真正的产品核心不是“任务存在”，而是 AI Execution OS 能不能可信地回答“今天先做什么”。

本轮补上第一版可落地的编排核心。它仍是 deterministic planning engine，不接真实 LLM，但已经把后续 LLM / Agent 可替换的输入、输出和解释结构先稳定下来。

### 目标

- Today 生成计划时计算每个任务的 `score_breakdown`。
- Planning Engine 读取任务价值、优先级、deadline、估时、依赖、用户修正、行为反馈、容量和 Energy。
- 超出当日容量的非保护任务进入 `rolled_over`，不挤占主执行序列。
- Strategy Detail 返回完整解释因子；Today 首屏只保留轻量顺序和推荐理由。
- Energy 在新 plan / replan 时成为可解释的排序和容量保护因子；低精力可降低容量，高精力不自动增加工作量；旧 plan 不被静默改版。

### 非目标

- 不接真实 LLM provider。
- 不实现 calendar time blocking。
- 不实现 P4 团队协作或商业化能力。
- 不把 Today 做成复杂驾驶舱。
- 不让 Planning Engine 自动确认外部 Capture / Inbox 内容。

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

Planning Engine v1 负责把复杂判断藏在系统后面。用户在 Today 看到的是更清楚的执行顺序；需要信任解释时，再进入 Strategy Detail 看评分因子和容量说明。

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
| Task score breakdown | 为 DailyPlanItem 保存 per-task scoring factors | Must | Strategy Detail 用于解释 |
| Capacity selection | 按当日容量选择主执行序列，超量任务滚动到未来 | Must | 保护 Today 行动感 |
| Energy planning signal | 读取同日 EnergyDailyMetric 影响容量保护和 energy fit | Must | P3 回灌 P2 核心 |
| Behavior feedback | 读取完成、延后、中断行为影响排序 | Should | 第一版轻量权重 |
| Strategy factors | 返回容量、选中时长、滚动时长、Energy 状态 | Must | 解释克制可信 |

### 用户故事

```text
作为 Chronos 用户，
我希望 Today 自动把重要任务放进一个做得出来的顺序，
以便我不需要每天重新消耗脑力决定先做什么。
```

```text
作为前端开发者，
我希望 Today item 有可选的 score_breakdown，但首屏仍只按 section 和 sort_order 展示，
以便我可以保持界面轻盈，同时在 Strategy Detail 提供可信解释。
```

```text
作为系统模块，
我希望 Planning Engine 的输入和输出结构稳定，
以便后续真实 LLM / Agent 可以替换或增强评分，而不破坏 Today / Focus / Report 闭环。
```

### 主要流程

```text
GET /today or POST /today/replan
-> collect active/postponed tasks
-> build PlanningContext from user settings + Energy
-> score tasks with value/urgency/dependency/duration/energy/behavior/user preference
-> apply daily capacity
-> persist DailyPlanItem.score_breakdown
-> expose lightweight Today + detailed Strategy Detail
```

---

## 5. 后端设计

### 影响模块

- [ ] API
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
DailyPlanItem {
  score_breakdown JSON
}
```

`score_breakdown` 存储 Planning Engine v1 的解释因子，包括但不限于：

- `total_score`
- `value_score`
- `goal_value_score`
- `urgency_score`
- `goal_urgency_score`
- `dependency_score`
- `duration_fit_score`
- `energy_fit_score`
- `behavior_feedback_score`
- `user_preference_score`
- `priority_score`
- `daily_capacity_minutes`
- `selected_for_today`
- `rollover_reason`

### 状态机变更

Plan item 层面新增系统滚动语义：

```text
planned candidate -> selected main sequence
planned candidate -> rolled_over / planned plan item
user-postponed task -> rolled_over / postponed plan item
```

说明：系统容量滚动只改变 `DailyPlanItem.section`，不直接把 Task 本体改成 postponed，也不把 plan item 混同为用户手动延后；只有 Task 本体已经是 postponed 时，rolled_over item 才保持 `status=postponed`。

### 事件变更

复用已有事件作为行为反馈输入：

- `TASK_COMPLETED`
- `TASK_POSTPONED`
- `FOCUS_SESSION_INTERRUPTED`
- `FOCUS_SESSION_POSTPONED`
- `TASK_PRIORITY_ADJUSTED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/today` | 返回 Today 聚合 | query `plan_date` | Today item 增加 `score_breakdown` |
| GET | `/api/v1/today/strategy` | 返回 Strategy Detail | query `plan_date` | factors 增加容量、滚动和 Energy 字段 |
| POST | `/api/v1/today/replan` | 重新编排 Today | `reason` | 使用最新 PlanningContext |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [x] 修改 fallback

### Agent 设计

- Agent 名称：Planning Engine v1
- 输入对象：Task、TaskDependency、ActivityEvent、UserSettings、EnergyDailyMetric
- 输出对象：DailyPlanItem section / sort_order / recommendation_reason / score_breakdown
- Pydantic schema：当前复用 Today response schema；后续真实 LLM 接入时再新增 structured output schema
- fallback 策略：deterministic scoring engine
- 是否需要用户确认：不需要确认排序；用户可通过 replan、priority adjustment、postpone/complete 修正

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [ ] AIJob 状态可查询
- [x] 用户保留修正权

说明：本轮还未接真实 LLM，因此 AIJob 不适用；但 Planning Engine 的输入输出边界为后续 Agent 化预留。

---

## 7. 验收标准

### 功能验收

- [x] Today 新计划能生成 `score_breakdown`。
- [x] 高价值 / 高优先级 / deadline / 依赖任务仍能被保护在前。
- [x] 超出当日容量的非保护任务进入 `rolled_over`。
- [x] 低 Energy 时容量下降，并偏好轻量任务；高 Energy 只提升深度任务适配分，不扩容。
- [x] Strategy Detail 能解释容量、滚动和 Energy 是否应用。

### 数据验收

- [x] `daily_plan_items.score_breakdown` 正确落库。
- [x] 系统滚动不直接改变 Task 本体状态。
- [x] 旧 plan 不会因为读 Strategy Detail 被静默改版。

### 体验验收

- [x] Today 首屏不暴露完整评分细节。
- [x] Strategy Detail 的解释足够可信但不过载。
- [x] Energy 影响可见、可解释、可通过 replan 更新。

---

## 8. 测试计划

### 单元测试

- [x] Today service 基础计划生成。
- [x] 容量滚动逻辑。
- [x] Energy 低精力排序和容量影响，高精力不自动增加工作量。

### API 测试

- [x] Strategy Detail 返回 Planning Engine source。
- [x] Energy explanation 显示 `applied_to_plan`。
- [x] user_id 隔离不受影响。

### 集成测试

- [x] DB migration。
- [x] P1 execution loop smoke。
- [x] P2 goal / insight loop smoke。
- [x] P3 natural growth smoke。

### 手动验证

```text
1. 创建多个高/中/低价值任务。
2. 写入当天 Energy metric。
3. GET /today 生成计划。
4. GET /today/strategy 查看 score_breakdown / factors / energy。
5. POST /today/replan 验证策略可重算。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 评分过度复杂 | Today 变成驾驶舱 | Today 首屏不展示完整 breakdown |
| deterministic engine 被误解为真实 LLM | 产品表达失真 | 命名为 Planning Engine v1，文档说明真实 LLM 待后续 |
| Energy 影响旧计划 | 用户困惑、不可信 | 只有新 plan / replan 应用，读接口只解释 |
| pinned 任务过多导致超容量 | 今日仍可能过载 | 保留高价值保护，后续增加 overload warning |

### 关键取舍

- 取舍 1：先做 deterministic Planning Engine，而不是直接接真实 LLM；目的是稳定业务闭环和解释结构。
- 取舍 2：容量只影响主执行序列，不做时间块排程；Chronos 当前核心是行动次序，不是日历占位。
- 取舍 3：Energy 只进入轻量容量保护和适配分，不展示健康细节；低精力保护容量，高精力不自动加工作量，避免 Today 变复杂。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 `DailyPlanItem.score_breakdown` | Strategy Detail 需要解释 Planning Engine 判断 | Today 可轻量，详情可解释 |
| 2026-05-17 | 系统滚动使用 `rolled_over` section | 保护今日主序列行动感 | 低优先级/超容量任务仍可见 |
| 2026-05-17 | Energy 只在新 plan / replan 生效 | 避免旧计划被静默改变 | `GET /today/strategy` 只解释当前快照 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 score_breakdown 字段和迁移 | `app/models/daily_plan.py`, `alembic/versions/20260517_0016_planning_engine_score_breakdown.py` | Planning Engine 解释落库 |
| 2026-05-17 | 重构 Today planning service | `app/services/planning_service.py` | scoring / capacity / energy / behavior |
| 2026-05-17 | 扩展 Today schema | `app/schemas/today.py` | Strategy factors + item breakdown |
| 2026-05-17 | 补测试 | `tests/test_today_services.py`, `tests/test_today_api.py` | 容量和 Energy 覆盖 |
| 2026-05-17 | 更新文档合同 | Architecture / P1 / P2 / P3 contracts | 前后端约束对齐 |
| 2026-05-17 | 更新 LLM 架构 | `docs/chronos-llm-agent-architecture.md` | Planning Engine v1 成为 Daily Planner fallback/core |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `uv run python -m unittest tests.test_today_services tests.test_today_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`
- [x] `uv run alembic upgrade head --sql`
- [x] `uv run alembic upgrade head`
- [x] `uv run python scripts/smoke_p1_execution_loop.py`
- [x] `uv run python scripts/smoke_p2_goal_insight_loop.py`
- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`

### 未验证

- [x] 无。

### 已知问题

- pinned 任务当前优先保护，即使多个 pinned 总时长超过容量；后续可在 Strategy Detail 增加 overload warning。

---

## 13. 后续迭代建议

- Planning Engine v1.1：增加 overload warning 和策略偏好可配置解释。
- LLM Planner Agent：在 deterministic engine 外接真实 provider + structured output + fallback。
- Planner evaluation：加入固定 seed 场景和排序质量回归测试。
