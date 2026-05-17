# Iteration: P2 Minimum Viable Progress Planning

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Planning Engine 在高价值任务过大、今天时间不够时，保护一个“最小可推进动作”，而不是把整块任务硬塞进 Today。

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

TaskPlanningSignal 已经能提供 `minimum_viable_step`、复杂度、目标对齐和语义估时。下一步要让这些信号真正服务 Chronos 的核心价值：今天时间不够时，也要把用户往高价值目标推进一点。

### 目标

- Planning Engine 对高价值 / 高目标对齐的大任务使用 planned slice duration。
- DailyPlanItem 展示今天计划推进的切片时长，不改 Task 原始估时。
- score_breakdown 记录原估时、切片时长、是否应用最小推进动作。
- Strategy Detail 解释这不是完整任务承诺，而是今日最小推进。

### 非目标

- 不自动创建子任务。
- 不修改 Task.estimated_duration_min。
- 不让 LLM 直接决定排序或时长。
- 不做复杂项目管理、时间块日历或前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Goals -> Goal Detail -> Task Detail -> Today -> Focus -> Report
```

- [x] Today
- [x] Task Detail
- [x] Goals
- [x] AI Agent

### 产品人格

本轮的关键是“把今天安排成真正做得出来的一天”：大任务仍然保留真实规模，但 Today 只要求用户先推进一个清楚的小动作。

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
| Planned slice duration | 大任务在 Today 中使用今日切片时长 | Must | 不改 Task 原始估时 |
| Minimum viable score breakdown | 记录 `minimum_viable_progress_applied` 等解释字段 | Must | Strategy Detail 可解释 |
| Strategy factors | 返回 `minimum_viable_progress_count` | Should | 只用于 Strategy Detail |
| Score signal | task rationale 中展示“最小推进动作” | Should | 不进入 Today 首屏复杂展示 |

### 用户故事

```text
作为时间不够但仍想推进重要目标的用户，
我希望 Chronos 不把一个 3 小时大任务直接压给我，
而是帮我保护今天能做出来的最小推进动作。
```

### 主要流程

```text
TaskPlanningSignal.minimum_viable_step
-> Planning Engine score_breakdown
-> planned_duration_min
-> DailyPlanItem.estimated_duration_min
-> Strategy Detail explains minimum viable progress
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
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

无新增接口；`GET /today` 和 `GET /today/strategy` 的 response 中已有字段承载解释：

- `DailyPlanItem.estimated_duration_min`：今日计划推进时长。
- `score_breakdown.original_estimated_duration_min`：任务原估时。
- `score_breakdown.planned_duration_min`：今日计划切片。
- `score_breakdown.minimum_viable_progress_applied`：是否应用最小推进动作。
- `factors.minimum_viable_progress_count`：本次计划中使用最小推进动作的任务数量。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent 输出
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

不新增 Agent。本轮只消费上一轮 `TaskPlanningSignal.minimum_viable_step`。

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询

---

## 7. 验收标准

- [x] 有 TaskPlanningSignal 且任务明显过大时，Today 使用 planned slice duration。
- [x] Task 原估时仍保存在 score_breakdown，不被覆盖。
- [x] Strategy Detail 暴露 `minimum_viable_progress_count`。
- [x] task rationale 能解释“最小推进动作”。
- [x] 无语义信号的旧 planner eval baseline 不回退。

---

## 8. 主线偏离 Review

本轮没有扩张 P3/P4，也没有新增复杂 UI 或真实 provider 工作。它直接强化核心命题：

```text
高价值目标
-> 今天做得出来的一步
-> 可解释计划
```

排序仍由 Planning Engine 完成，LLM 只提供结构化语义信号。

---

## 9. 验证记录

```bash
uv run python -m unittest tests.test_today_services
```

结果：25 tests OK。

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

结果：305 tests OK；compile OK；git diff --check OK；9 个 planner eval 场景通过；planner eval policy 无 regression / change。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke mainline-state
```

结果：305 tests OK；compile OK；git diff --check OK；MAINLINE-STATE smoke passed。
