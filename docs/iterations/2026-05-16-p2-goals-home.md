# Iteration: P2 Goals Home Aggregate

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 P2 Goals 首页聚合 API，让前端可以展示目标列表、目标摘要、筛选计数、目标进度、风险状态和推荐下一步任务。

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
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)

### 背景

Goal Detail 已经具备聚合能力，但 Goals 首页仍只有基础列表。根据产品信息架构，Goals 首页需要展示目标列表、进度、Deadline、风险状态、关联任务数、筛选和总览，作为进入 Goal Detail 的上一级承接页。

### 目标

- 新增 `GET /api/v1/goals/home`。
- 返回 Goals Summary。
- 返回 filter counts 和当前 filter 结果。
- Goal card 包含 progress、risk、deadline、关联任务数、推荐下一步任务 id。
- 保留 `GET /api/v1/goals` 作为轻量列表 / selector，不改变 P1 行为。

### 非目标

- 不新增 DB 表。
- 不实现复杂 Goals dashboard。
- 不实现真实 LLM 目标洞察。
- 不实现 Goal dependency edges。
- 不移除或改变原有 `GET /goals`。

---

## 3. 产品约束对齐

### 核心路径

```text
Goals -> Goal Detail -> Task Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [x] Task Detail
- [x] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

Goals Home 只提供目标推进所需的扫描信息，不做复杂仪表盘。它帮助用户判断哪个目标需要关注，并把用户自然带到 Goal Detail 和推荐任务。

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
| Goals Home API | 目标首页聚合 | Must | P2 |
| Goal Summary | 总目标、活跃、完成、即将截止、高价值、风险、本周推进 | Must | 规则计算 |
| Filter Counts | all / active / due_soon / completed / high_value | Must | 支持 tabs |
| Goal Cards | 进度、风险、deadline、关联任务数、推荐任务 | Must | 支持扫描 |
| Selector Compatibility | 保留原 `GET /goals` | Must | 不破坏 P1 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Goals 首页快速看到目标推进状态，
以便决定先进入哪个目标，并继续进入下一步任务。
```

### 主要流程

```text
GET /goals/home?filter=active
-> user scans goal cards
-> GET /goals/{goal_id}/detail
-> user taps recommended next task
-> GET /tasks/{task_id}
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests
- [x] Docs

### 数据模型变更

无。新增 `GoalHomeFilter` enum 仅用于 API query 和 response，不创建数据库 enum。

### 状态机变更

无新增状态机。Goals Home 读取：

```text
Goal.active / completed / archived
Task.active / in_focus / postponed / completed / archived
```

### 事件变更

无新增事件。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/goals/home` | Goals 首页聚合 | query filter / limit / offset | `GoalsHomeResponse` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及 rule/fallback Agent
- [ ] 新增真实 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

无真实 LLM。Goals Home 的风险状态和推荐下一步任务来自规则：

- active / in_focus 任务优先于 postponed。
- deadline 近且完成率低时标记 `at_risk`。
- deadline 已过且仍有未完成任务时标记 `behind`。
- 无任务目标标记 `needs_breakdown`。

### LLM 安全边界

- [x] 不写 AIJob。
- [x] 不伪装成真实智能洞察。
- [x] 只返回短风险原因和推荐任务 id。

---

## 7. 验收标准

### 功能验收

- [x] 可以获取 Goals Home 聚合。
- [x] 支持 `all` / `active` / `due_soon` / `completed` / `high_value` filter。
- [x] 返回 summary 和 filter counts。
- [x] Goal card 返回进度、风险、关联任务数和推荐下一步任务 id。
- [x] 不同 `X-User-Id` 数据隔离。
- [x] 原 `GET /goals` 轻量列表仍可用。

### 数据验收

- [x] archived goals 不进入 Goals Home。
- [x] archived tasks 不计入 goal card。
- [x] weekly_completed_task_count 按本周完成任务计算。
- [x] due soon filter 只包含 active 且 deadline 在 7 天内的目标。

### 体验验收

- [x] Goals 首页可以服务扫描和进入 Goal Detail。
- [x] 不把 Goals 首页做成复杂驾驶舱。
- [x] 推荐下一步只给 task id，具体执行仍进入 Task Detail。

---

## 8. 测试计划

### 自动化检查

- [x] Service 测试：summary / filters / cards / recommended task
- [x] API 测试：`GET /goals/home?filter=due_soon`
- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. Review 记录

- `GET /goals/home` 放在 `/{goal_id}` 之前，避免路由冲突。
- `GET /goals` 保持轻量 selector，不承载 Goals 首页复杂数据。
- Goals Home 不返回完整 Task Detail，前端应使用 `recommended_next_task_id` 再进入 Task Detail。
