# Iteration: P2 Priority Adjustment Today Refresh

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让用户在 Task Detail 中调整任务优先级 / 价值等级后，当前 Today 中的同一任务能触发 `manual_adjust` revision，使用户修正即时进入 Today 编排和 Strategy Detail 解释。

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

Chronos 的 AI 编排要可信，关键不是 AI 永远正确，而是用户可以修正它。P2 已经支持 `PATCH /tasks/{id}/priority` 记录 `TASK_PRIORITY_ADJUSTED`，Planning Engine 也能读取该信号；但如果 Today plan 已经存在，用户调整后当前 plan 不会自动对齐，修正需要等主动 replan 或新计划生成。

### 目标

- 用户调整当前 Today 中任务的 `priority` / `value_level` 后，生成 `manual_adjust` revision。
- 响应返回 `today_impact`，告诉前端 Today 是否被刷新。
- Strategy Detail 的 `user_adjusted_count` 和推荐理由立即体现用户修正。

### 非目标

- 不新增 AI 策略偏好系统。
- 不做复杂手动排序。
- 不做前端页面。
- 不引入 LLM。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Task Detail -> 调整优先级 -> Today / Strategy Detail
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [ ] AI Agent

### 产品人格

- 轻盈：用户只调整任务本身，不需要理解 plan revision。
- 克制：只刷新当前 Today 中的同一任务，不做全局策略配置。
- 可信赖：用户修正会被立即尊重，并在 Strategy Detail 解释。
- 有判断：使用 `manual_adjust` 区分用户修正和系统刷新。

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
| Priority adjustment Today refresh | 当前 Today 任务被调整后刷新 plan | Must | trigger=`manual_adjust` |
| today_impact response | 调整接口返回 Today 影响 | Must | 前端可刷新 Today |
| Strategy explanation alignment | `user_adjusted_count` 立即更新 | Must | 复用已有解释 |

### 用户故事

```text
作为用户，
我希望把某个任务改成高优先级后，Today 能立刻尊重我的判断，
以便我感觉 AI 编排是可校正、可信赖的。
```

```text
作为前端开发者，
我希望优先级调整接口返回 today_impact，
以便知道是否需要刷新 Today 和 Strategy Detail。
```

### 主要流程

```text
GET /today
-> GET /tasks/{task_id}
-> PATCH /tasks/{task_id}/priority
-> 记录 TASK_PRIORITY_ADJUSTED
-> 如果任务在当前 Today，生成 manual_adjust revision
-> 返回 today_impact
-> GET /today / strategy 读取用户修正
```

---

## 5. 后端设计

### 影响模块

- [x] API
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

无新增状态。

```text
DailyPlan.current_version N -> N+1
PlanRevision.trigger = manual_adjust
```

### 事件变更

- `TASK_PRIORITY_ADJUSTED`
- `DAILY_PLAN_MANUAL_ADJUSTED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| PATCH | `/api/v1/tasks/{task_id}/priority` | 用户修正优先级 / 价值等级 | `priority`, `value_level`, `reason` | 新增 `today_impact` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 当前 Today 中的任务被调整优先级后，返回 `today_impact.replanned=true`。
- [x] Today version 增加。
- [x] 调整后的任务进入更高优先级分区。
- [x] Strategy Detail `user_adjusted_count` 增加。

### 数据验收

- [x] `TASK_PRIORITY_ADJUSTED` 写入。
- [x] `DAILY_PLAN_MANUAL_ADJUSTED` 写入。
- [x] `PlanRevision.trigger=manual_adjust`。

### 体验验收

- [x] 用户修正立即生效。
- [x] Today 首屏仍只显示轻量理由。
- [x] 详细解释仍通过 Strategy Detail 承接。

---

## 8. 测试计划

### 单元 / API 测试

- [x] `tests.test_today_services`
- [x] `tests.test_task_goal_services`
- [x] `tests.test_task_goal_api`
- [x] `tests.test_today_api`

### Smoke

- [x] `scripts/verify_local.py --smoke p1-bearer-capture`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 用户每次微调都刷新 Today | plan version 增长 | 只在字段真实变化且任务位于当前 Today 时刷新 |
| Today 展示过多解释 | 变复杂驾驶舱 | 只保留短推荐理由，详细因子留给 Strategy Detail |

### 关键取舍

- 取舍 1：使用 `manual_adjust` 而不是 `system_refresh`，明确这是用户修正。
- 取舍 2：不实现拖拽排序，先让优先级 / 价值等级成为可解释修正入口。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 优先级调整触发当前 Today `manual_adjust` | 用户修正权是 AI 编排可信度核心 | P2 修正能力和 P1 Today 主线闭合 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加优先级调整刷新入口 | `app/services/planning_service.py` | 返回 Today impact |
| 2026-05-17 | Task priority 调整后调用刷新 | `app/services/task_service.py` | 先 flush 事件供 Planning Engine 读取 |
| 2026-05-17 | 扩展响应 schema | `app/schemas/tasks.py` | 新增 `TaskTodayImpactResponse` |
| 2026-05-17 | 补充回归测试 | `tests/test_today_services.py`, `tests/test_task_goal_api.py` | 覆盖有 / 无 active Today |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_today_services tests.test_task_goal_services tests.test_task_goal_api tests.test_today_api`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer-capture`
- [x] `git diff --check`

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 检查 Goal Detail 的 recommended next task 是否应避开被依赖阻塞的任务。
- 检查 Strategy Detail 是否需要暴露最近一次用户修正的轻量来源说明。
