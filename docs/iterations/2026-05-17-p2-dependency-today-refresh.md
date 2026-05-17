# Iteration: P2 Dependency Today Refresh

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让任务依赖新增 / 删除后，当前 Today 中受影响的任务能触发 `system_refresh`，保证 Planning Engine 排序、Task Detail 依赖和 Strategy Detail 解释不滞后。

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

P2 已经支持 Task Dependency，并且 Planning Engine v1 会读取依赖信号，把前置任务提前保护。但如果用户在 Today plan 已经存在后新增或删除依赖，当前 plan 不会自动刷新，导致 Today 排序和 Strategy Detail 解释短暂滞后。这会削弱用户对“AI 今日编排”的信任。

### 目标

- 添加 / 删除依赖后，如果相关任务位于当前 active Today plan，生成 `system_refresh` revision。
- 刷新后的 Today 立刻读取最新依赖，前置任务可以提前于后续任务。
- 不把依赖系统扩成项目管理套件，只服务 Today 编排可信度。

### 非目标

- 不做复杂 Dependency View UI。
- 不新增跨目标 / 跨团队依赖。
- 不做 P3/P4 协作。
- 不引入 LLM。

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
- [ ] AI Agent

### 产品人格

- 轻盈：Today 只刷新结果，不把依赖图搬到首页。
- 克制：只有当前 Today 中的相关任务会触发刷新。
- 可信赖：用户刚调整依赖，Strategy Detail 就能解释新的前置任务保护。
- 聪明但不炫耀：依赖仍由 deterministic Planning Engine 使用，不交给 LLM 改排序。

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
| Dependency change refresh | 依赖新增 / 删除后刷新当前 Today | Must | 仅相关任务在当前 Today 时 |
| Planning Engine re-read dependencies | 刷新 revision 时读取最新依赖 | Must | 复用已有评分 |
| Contract update | 文档说明依赖变更对 Today 的影响 | Should | 前端联调 |

### 用户故事

```text
作为正在整理任务依赖的用户，
我希望添加“B 依赖 A”后，Today 能立刻把 A 放到 B 前面，
以便我相信系统理解了真正的执行顺序。
```

```text
作为后端开发者，
我希望依赖变更能触发受影响 Today 的 system_refresh，
以便 Task Detail、Goal Detail、Today 和 Strategy Detail 使用同一份依赖事实。
```

### 主要流程

```text
GET /today
-> POST /tasks/{dependent_task_id}/dependencies
-> TaskDependency created
-> 如果 dependent / prerequisite 已在当前 Today，生成 system_refresh revision
-> GET /today 返回新 version 和新排序
-> GET /today/strategy 返回 dependency_protected_count / dependency signal
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
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
PlanRevision.trigger = system_refresh
```

### 事件变更

- `TASK_DEPENDENCY_CREATED`
- `TASK_DEPENDENCY_DELETED`
- `DAILY_PLAN_SYSTEM_REFRESHED`

### API 变更

无新增 endpoint。既有接口行为增强：

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/tasks/{task_id}/dependencies` | 添加前置依赖 | `prerequisite_task_id` | 可能刷新当前 Today |
| DELETE | `/api/v1/tasks/{task_id}/dependencies/{prerequisite_task_id}` | 删除前置依赖 | - | 可能刷新当前 Today |

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

- [x] 当前 Today 已存在时，添加涉及当前 Today 任务的依赖会生成新 plan version。
- [x] 新 version 中前置任务排序早于后续任务。
- [x] 推荐理由包含前置任务解锁信号。

### 数据验收

- [x] 新增依赖正常落库。
- [x] `PlanRevision.trigger=system_refresh`。
- [x] `DAILY_PLAN_SYSTEM_REFRESHED` 写入 activity event。

### 体验验收

- [x] Today 仍只返回轻量推荐理由。
- [x] 详细依赖解释仍留在 Strategy Detail / Task Detail。

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
| 每次依赖变更都刷新 Today | 过度改版 | 只有相关任务已在当前 active Today 时刷新 |
| 依赖图复杂度外溢到 Today | Today 变驾驶舱 | Today 只显示排序和短理由，详细解释放 Strategy Detail |

### 关键取舍

- 取舍 1：刷新当前日期 active Today，不跨日期改历史 / 未来 plan。
- 取舍 2：依赖刷新使用 deterministic Planning Engine，不让 LLM 重排。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 依赖变更触发当前 Today `system_refresh` | 防止排序和解释滞后 | 提升 P2 依赖对 P1 主线的真实价值 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加依赖变更刷新入口 | `app/services/planning_service.py` | 仅当前 Today 相关任务触发 |
| 2026-05-17 | Task dependency 写入后调用刷新 | `app/services/task_service.py` | 使用延迟 import 避免 service 循环 |
| 2026-05-17 | 补充 Today 排序回归测试 | `tests/test_today_services.py` | 覆盖 plan 已存在后新增依赖 |

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

- 检查用户优先级调整是否也需要对当前 Today 提供可解释的轻量 impact，而不是只等待用户主动 replan。
- 检查 Goal Detail 的 recommended next task 是否应考虑未完成前置任务。
