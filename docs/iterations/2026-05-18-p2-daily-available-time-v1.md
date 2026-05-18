# Iteration: P2 Daily Available Time v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待补

---

## 1. 迭代摘要

让用户能在 Today replan 时输入“今天可用多少分钟”，Planning Engine 按这个容量滚动任务，并在 Strategy Detail 解释容量来源。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Planning Engine 已经有默认容量：轻量 90 分钟、普通 150 分钟、冲刺 210 分钟，且低精力会把默认容量收敛到 90 分钟。但 Chronos 的核心承诺是“把今天安排成真正做得出来的一天”，用户当天真实可用时间往往比默认值更重要。

### 目标

- 支持用户在 `POST /today/replan` 中传入今日可用分钟数。
- Planning Engine 使用该手动容量进行容量滚动和 Strategy Detail 解释。
- 后续同日 replan 默认沿用当前手动容量，避免用户设置被信号刷新或新增任务冲掉。
- 手动输入优先于 Energy 对容量的收敛，但 Energy 仍可作为排序解释信号。

### 非目标

- 不做日历时间块。
- 不做 P3 自动提醒或外部日程接入。
- 不新增 LLM Agent。
- 不新增长期画像或复杂可用时间设置页。
- 不让 Today 首屏变成容量仪表盘。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Task Detail -> Focus -> Report
```

- [x] Today
- [x] Strategy Detail
- [x] Focus
- [x] Report
- [ ] P3/P4

### 产品人格

本轮增强让用户保留控制感：用户只告诉系统“今天大概有多少分钟”，系统在背后重新滚动任务，前台只展示更可执行的 Today 和轻量解释。

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
| Replan available minutes | `POST /today/replan` 支持 `available_minutes` | Must | 范围 15-720 |
| Manual capacity source | Strategy Detail factors 暴露 `capacity_source` | Must | `manual_today_override` 表示用户输入 |
| Capacity persistence | 同日后续 replan 沿用当前手动容量 | Must | 避免新增任务 / signal refresh 冲掉用户设置 |
| Energy boundary | 手动容量优先于低精力容量收敛 | Should | Energy 仍参与排序和解释 |
| Frontend contract | 更新 P2 API contract | Must | 不要求前端做复杂面板 |

### 用户故事

```text
作为时间碎片化的用户，
我希望告诉 Chronos 今天只有 60 分钟可用，
以便 Today 不再给我一个看起来正确但实际做不完的清单。
```

```text
作为后端系统，
我希望手动可用时间成为 Planning Engine 的确定性输入，
以便排序、滚动和解释保持一致，而不是让 LLM 黑盒决定工作量。
```

### 主要流程

```text
POST /today/replan { available_minutes }
-> PlanningContext capacity_source = manual_today_override
-> Planning Engine 重新分配 pinned / recommended / rolled_over
-> Strategy Detail 展示容量来源和滚动原因
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Schemas
- [x] Tests
- [ ] Models
- [ ] DB Migration
- [ ] Agents

### 数据模型变更

无。手动容量随当前 plan revision 写入 `PlanRevision.diff_payload`、`StrategySnapshot.score_factors` 和 item `score_breakdown`，不新增持久表。

### 状态机变更

无。

### 事件变更

复用：

- `DAILY_PLAN_REPLANNED`
- `DAILY_PLAN_CREATED`

payload 增加：

- `manual_available_minutes`

---

## 6. API 合同

### POST `/api/v1/today/replan`

Request:

```json
{
  "reason": "今天只有一小时",
  "available_minutes": 60
}
```

Response: `TodayResponse`

Strategy Detail factors 新增：

```json
{
  "base_capacity_minutes": 60,
  "daily_capacity_minutes": 60,
  "capacity_source": "manual_today_override",
  "manual_available_minutes": 60,
  "energy_capacity_adjusted": false
}
```

---

## 7. 验收标准

- [x] 手动设置 60 分钟后，Today 只保留能放入 60 分钟容量的主序列，其他任务滚动到未来。
- [x] Strategy Detail 返回 `capacity_source=manual_today_override` 和 `manual_available_minutes`。
- [x] 同日再次 replan 且不传 `available_minutes` 时，沿用当前手动容量。
- [x] 低精力数据存在时，手动容量不被强制降到 90 分钟。
- [x] 无 DB migration。
- [x] 无 P3/P4 扩张。

---

## 8. Review

本轮对齐主线：它直接增强 Today 编排的可执行性，让 Chronos 更接近“今天先做什么、做多少才现实”的核心承诺。复杂度仍在 Planning Engine 内部，用户只看到可用时间输入、重新编排结果和 Strategy Detail 的轻量解释。

下一轮建议做 `P2 Planner Review Uses Capacity Context v1`：让 Daily Planner Agent 的 critique / suggestion 读取 `capacity_source`、`manual_available_minutes`、`rolled_over_estimated_minutes`，生成更贴近用户真实可用时间的只读建议，但仍不改变排序。
