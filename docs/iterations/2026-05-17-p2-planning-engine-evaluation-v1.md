# Iteration: P2 Planning Engine Evaluation v1.1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Planning Engine v1 增加固定场景评估和容量超载解释，让后续调整排序权重时可以追踪质量变化，而不是只验证接口没有坏。

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

### 背景

Planning Engine v1 已经能基于价值、优先级、deadline、依赖、行为反馈、容量和 Energy 生成 Today 顺序。但算法类能力不能只靠普通接口测试保障，否则后续调权重时很容易“接口全绿，排序质量退化”。

本轮建立第一批固定评估场景，并补上一个重要体验风险：当多个受保护任务总时长超过容量时，系统应给出克制的 overload warning，而不是假装今天仍然完全可执行。

### 目标

- Strategy Detail 增加 `capacity_status` 和 `over_capacity_minutes`。
- Today Insights Preview 在主序列超载时返回一个轻量风险提示。
- 新增 `scripts/evaluate_planning_engine.py`，用固定场景评估 planner 行为。
- 新增 evaluation unit test，把评估场景纳入回归验证。
- 更新前后端契约和架构文档。

### 非目标

- 不改变现有核心评分权重。
- 不接真实 LLM。
- 不做日历 time blocking。
- 不把 Today 做成容量驾驶舱。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Focus
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

overload warning 的语气保持克制，只提醒“先完成一个高价值任务，再决定是否拉回更多任务”，不催促用户压榨更多时间。

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
| Capacity status | Strategy factors 返回容量状态 | Must | `within_capacity` / `overloaded` |
| Over capacity minutes | 返回主执行序列超出容量的分钟数 | Must | 只用于解释 |
| Today risk alert | 超载时 Today Insights Preview 返回轻量风险提示 | Should | 不展开为驾驶舱 |
| Planner evaluation script | 固定场景评估 Planning Engine 输出 | Must | 开发回归工具 |
| Evaluation unit test | 把固定场景纳入测试 | Must | 防止质量退化 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统在今日主序列明显过重时温和提醒我，
以便我先完成一个重要任务，而不是被一个不现实的计划压住。
```

```text
作为后端开发者，
我希望 Planning Engine 有固定评估场景，
以便后续调整排序权重或接入 LLM 时能看到核心行为是否退化。
```

### 主要流程

```text
GET /today
-> Planning Engine selects main sequence
-> compare selected_estimated_minutes with daily_capacity_minutes
-> attach capacity_status / over_capacity_minutes
-> Today Preview may show one light risk alert
```

```text
uv run python scripts/evaluate_planning_engine.py
-> seed deterministic scenarios
-> run planning_service
-> assert expected ordering/capacity/energy behavior
-> print JSON result
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

无。

### 状态机变更

无。

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/today/strategy` | Strategy Detail | query `plan_date` | factors 增加 `capacity_status` / `over_capacity_minutes` |
| GET | `/api/v1/today` | Today 聚合 | query `plan_date` | 超载时 `insights_preview.risk_alerts[]` 增加 `main_sequence_over_capacity` |

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

- Agent 名称：Planning Engine v1.1
- 输入对象：Task、TaskDependency、ActivityEvent、UserSettings、EnergyDailyMetric
- 输出对象：DailyPlanItem、StrategySnapshot、capacity factors、evaluation result
- fallback 策略：仍使用 deterministic Planning Engine
- 是否需要用户确认：不需要；用户通过 replan / priority adjustment / postpone 修正

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [ ] AIJob 状态可查询
- [x] 用户保留修正权

说明：本轮仍未接真实 LLM，AIJob 不适用；evaluation 为后续 LLM Planner Agent 提供回归基线。

---

## 7. 验收标准

### 功能验收

- [x] Strategy Detail 返回 `capacity_status`。
- [x] Strategy Detail 返回 `over_capacity_minutes`。
- [x] 多个 pinned 任务超容量时，Today Preview 返回轻量风险提示。
- [x] Evaluation script 能覆盖 capacity rollover、protected overload、low energy、high energy 场景。

### 数据验收

- [x] 不新增 migration。
- [x] 不改变 Task 本体状态。
- [x] 不新增 ActivityEvent。

### 体验验收

- [x] Today 仍只显示轻量提示。
- [x] 超载解释不制造压力。
- [x] Strategy Detail 可解释但不过载。

---

## 8. 测试计划

### 单元测试

- [x] Today service overload warning。
- [x] Strategy factors capacity fields。
- [x] Planning evaluation scenarios。

### API 测试

- [x] Strategy Detail response schema 包含 capacity fields。

### 集成测试

- [x] Evaluation script。
- [x] 全量测试。
- [x] P1/P2/P3 smoke。

### 手动验证

```text
uv run python scripts/evaluate_planning_engine.py
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| overload warning 让 Today 变焦虑 | 违背产品人格 | 只给一条轻量风险提示，不展示复杂容量面板 |
| evaluation 场景过少 | 覆盖不足 | 先覆盖最核心四类，后续逐步增加 |
| 评估脚本依赖测试 DB | 只能用于开发回归 | 明确作为 local evaluation，不作为生产 worker |

### 关键取舍

- 取舍 1：先做固定 seed 场景，不做复杂评分指标。
- 取舍 2：超载只解释，不自动降低 pinned 保护。
- 取舍 3：Evaluation script 复用测试 DB，避免污染真实数据。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 `capacity_status` / `over_capacity_minutes` | 让策略超载可解释 | Strategy Detail 更可信 |
| 2026-05-17 | 新增 planner evaluation script | 算法能力需要固定场景回归 | 后续可安全调权重 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 capacity factors / overload warning | `app/services/planning_service.py`, `app/schemas/today.py` | Strategy Detail + Today Preview |
| 2026-05-17 | 新增固定场景评估脚本 | `scripts/evaluate_planning_engine.py` | 4 个 deterministic scenarios；后续 v2 已扩展为 7 个场景 |
| 2026-05-17 | 新增 evaluation 回归测试 | `tests/test_planning_engine_evaluation.py`, `tests/test_today_services.py`, `tests/test_today_api.py` | service / API / evaluation |
| 2026-05-17 | 统一验证入口支持 planner eval | `scripts/verify_local.py` | `--planner-eval` |
| 2026-05-17 | 更新文档 | README / Architecture / LLM Agent / Engineering Guidelines / P2 Contract | 开发约束对齐 |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `uv run python -m unittest tests.test_today_services tests.test_today_api tests.test_planning_engine_evaluation`
- [x] `uv run python scripts/evaluate_planning_engine.py`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`

### 未验证

- [x] 无。

### 已知问题

- Evaluation 仍是第一版固定场景，不代表完整 planner quality benchmark。

---

## 13. 后续迭代建议

- 增加 planner benchmark fixture 文件，支持更多产品场景。
- 为 LLM Daily Planner Agent 增加 structured output 和 deterministic fallback 对比。
- 增加权重调整说明文档，避免随意改分数。
