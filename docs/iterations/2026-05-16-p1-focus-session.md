# Iteration: P1 FocusSession

> 状态：Done
> 阶段：P1
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 Chronos P1 的 FocusSession 基础执行态，让用户可以从 Task / Today item 开始专注，并通过完成、中断、延后把执行行为回写到 Task、Today 和 ActivityEvent。

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

Today / DailyPlan 已经能生成当天推荐执行顺序。下一步需要把计划推进到执行态：FocusSession 记录开始、结束、状态、实际专注时长，并让完成 / 中断 / 延后形成可追踪事件。

### 目标

- 新增 `FocusSession` 模型和 migration。
- 实现 Focus start / complete / interrupt / postpone API。
- 开始 Focus 时将 Task 置为 `in_focus`。
- 完成 / 延后 Focus 时同步 Task 和 DailyPlanItem。
- 中断 Focus 时记录时长，并将 Task 恢复为 `active`。
- 使用数据库部分唯一索引保证同一用户最多只有一个 active FocusSession。
- 所有关键操作写入 ActivityEvent。

### 非目标

- 不实现 pause / resume。
- 不实现复杂 Focus 洞察。
- 不实现 Focus 页面控制面板能力。
- 不实现自动提醒和番茄钟策略配置。
- 不实现 Daily Report 聚合。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [ ] Task Detail
- [x] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本迭代只记录执行需要的最少状态：开始、完成、中断、延后、实际时长。Focus 仍然是单任务执行场景，不返回复杂分析、策略解释或管理信息。

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
| FocusSession 模型 | 记录任务执行会话 | Must | P1 不做 pause |
| Start Focus | 从 Task / Today item 开始专注 | Must | 服务层检查 + DB 唯一约束 |
| Complete Focus | 完成 session 并完成 Task / Today item | Must | 记录实际时长 |
| Interrupt Focus | 中断 session，Task 回到 active | Must | Today item 保持 planned |
| Postpone Focus | 延后 session，并同步 Task / Today item | Must | 记录实际时长 |
| ActivityEvent | 记录 Focus 行为事件 | Must | 服务后续 Report |

### 用户故事

```text
作为 Chronos 用户，
我希望从 Today 推荐任务进入 Focus，
在完成、中断或延后后自动更新今日进度，
以便不用手动维护执行结果。
```

### 主要流程

```text
POST /focus-sessions
-> Task.in_focus
-> FocusSession.active
-> complete / interrupt / postpone
-> Task + DailyPlanItem + ActivityEvent
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

新增：

```text
FocusSession
```

约束：

```text
unique(user_id) where status = 'active'
```

### 状态机变更

```text
FocusSession.active -> completed
FocusSession.active -> interrupted
FocusSession.active -> postponed

Task.active -> in_focus
Task.postponed -> in_focus
Task.in_focus -> completed
Task.in_focus -> active       // interrupt
Task.in_focus -> postponed
```

P1 预留 `paused`，但不暴露 pause / resume API。

### 事件变更

- FOCUS_SESSION_STARTED
- FOCUS_SESSION_COMPLETED
- FOCUS_SESSION_INTERRUPTED
- FOCUS_SESSION_POSTPONED

同时复用：

- TASK_COMPLETED
- TASK_POSTPONED
- DAILY_PLAN_ITEM_UPDATED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/focus-sessions` | 开始专注 | FocusSessionCreate | FocusSessionResponse |
| GET | `/api/v1/focus-sessions/{session_id}` | 查询专注会话 | - | FocusSessionResponse |
| POST | `/api/v1/focus-sessions/{session_id}/complete` | 完成专注 | FocusSessionFinishRequest | FocusSessionResponse |
| POST | `/api/v1/focus-sessions/{session_id}/interrupt` | 中断专注 | FocusSessionFinishRequest | FocusSessionResponse |
| POST | `/api/v1/focus-sessions/{session_id}/postpone` | 延后专注 | FocusSessionFinishRequest | FocusSessionResponse |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及 mock/rule Agent
- [ ] 新增真实 Agent
- [ ] 修改真实 LLM Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] Focus 操作由用户显式触发。
- [x] Focus 不调用 LLM。
- [x] Focus 不自动改变任务含义，只更新执行状态。

---

## 7. 验收标准

### 功能验收

- [x] 可以从 Task 创建 FocusSession。
- [x] 可以从 Today item 创建 FocusSession。
- [x] 同一用户不能同时存在多个 active FocusSession，包含数据库级约束。
- [x] 完成 Focus 后 Task.completed，Today item.completed。
- [x] 中断 Focus 后 Task.active，Today item 保持 planned。
- [x] 延后 Focus 后 Task.postponed，Today item.postponed。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] FocusSession 正确落库。
- [x] actual_duration_min 正确写入 FocusSession 和 Task。
- [x] DailyPlan.focus_minutes 正确累加。
- [x] 关键动作写入 ActivityEvent。

### 体验验收

- [x] Focus response 只返回执行态必要信息。
- [x] 不返回复杂分析、score factors 或策略解释。
- [x] 核心流程不依赖真实 LLM。

---

## 8. 测试计划

### 单元测试

- [x] start + complete
- [x] interrupt
- [x] postpone
- [x] active session 冲突
- [x] Task / Today 状态同步

### API 测试

- [x] `POST /focus-sessions`
- [x] `GET /focus-sessions/{id}`
- [x] `POST /focus-sessions/{id}/complete`
- [x] `POST /focus-sessions/{id}/interrupt`
- [x] user_id 隔离
- [x] completed session 不可重复 complete

### 集成测试

- [x] Alembic migration 可生成 SQL
- [x] FastAPI dependency override

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| P1 不做 pause | 无法记录暂停片段 | 先保持执行态简单，后续按真实需求补 pause/resume |
| actual_duration 依赖客户端上报或服务端估算 | 可能存在轻微误差 | P1 允许显式传入 actual_duration_min，未传则按 started_at 估算 |
| 一个用户只允许一个 active session | 不支持并行专注 | 符合单任务 Focus 场景 |

### 关键取舍

- FocusSession 独立于 Task，沉淀执行行为数据。
- complete / postpone 复用 TaskService，避免任务状态事件分裂。
- interrupt 不完成也不延后任务，只记录中断并恢复 Task.active。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | P1 不实现 pause / resume | 避免 Focus 变成控制面板 | 后续可用 `paused` 状态扩展 |
| 2026-05-16 | 同一用户仅允许一个 active session | 保持单任务专注心智 | 防止执行数据重叠 |
| 2026-05-16 | interrupt 后 Task 回到 active | 中断不等于延后或完成 | Today item 保持 planned |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 FocusSession 迭代文档 | `docs/iterations/2026-05-16-p1-focus-session.md` | 本文件 |
| 2026-05-16 | 新增 FocusSession 模型和 migration | `app/models/focus_session.py`、`alembic/versions/20260516_0004_focus_sessions.py` | P1 执行态 |
| 2026-05-16 | 新增 FocusService | `app/services/focus_service.py` | start / complete / interrupt / postpone |
| 2026-05-16 | 新增 Focus API 和 schema | `app/api/v1/focus_sessions.py`、`app/schemas/focus_sessions.py` | 执行态接口 |
| 2026-05-16 | 扩展 TaskService / PlanningService | `app/services/task_service.py`、`app/services/planning_service.py` | 同步执行时长和 Today progress |
| 2026-05-16 | 新增 service / API 测试 | `tests/test_focus_services.py`、`tests/test_focus_api.py` | 覆盖主路径和边界 |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `alembic upgrade head --sql`
- [x] `alembic upgrade head`
- [x] `git diff --check`
- [x] `alembic current`

### 未验证

- 无

### 已知问题

- P1 不支持 pause / resume。
- FocusSession 不生成复杂洞察，仅沉淀后续 Report 所需行为数据。

---

## 13. 后续迭代建议

- Daily Report 基础复盘。
- Me Overview 基础数据。
- Task Detail 聚合增强。
