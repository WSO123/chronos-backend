# Iteration: P2 Goal Detail Aggregate

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 P2 Goal Detail 聚合 API，让 `Goals -> Goal Detail -> Task Detail -> Focus` 路径具备后端承接能力，同时保持 Goal Detail 轻量、清晰、可行动。

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

P1 已经跑通每日执行闭环。根据产品信息架构，P2 需要增强目标系统，让用户从中长期目标进入具体任务，并继续衔接 Task Detail 与 Focus。当前 Goal API 只有基础信息，无法支撑 Goal Detail 的进度、任务列表和下一步建议。

### 目标

- 新增 `GET /api/v1/goals/{goal_id}/detail`。
- 返回 Goal Overview、Goal Progress、Goal Task List、Dependency Map、AI Suggestion 和 Goal Actions。
- 推荐一个下一步任务，服务 `Goal Detail -> Task Detail -> Focus`。
- 先提供规则版风险判断和建议，不接真实 LLM。
- 不破坏 P1 的 `GET /goals/{goal_id}` 基础接口。

### 非目标

- 不新增 DB 表。
- 不实现真实任务依赖边。
- 不实现 Dependency View。
- 不实现 Goal progress timeline。
- 不接真实 LLM / Agent。
- 不实现单独的 mark goal complete action，仍通过 `PATCH /goals/{goal_id}` 更新 status。

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

Goal Detail 只返回能帮助用户理解目标进展和进入下一步行动的信息。它不展示冗长分析，不伪造复杂依赖图，也不把规则建议包装成真实智能。

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
| Goal Detail API | 返回目标详情聚合 | Must | P2 |
| Goal Progress | 任务完成数、完成率、风险状态 | Must | 规则计算 |
| Goal Task List | 未完成任务、已完成任务、推荐下一步 | Must | 可进入 Task Detail |
| Dependency Map | 返回节点顺序和空 edges | Should | 不伪造依赖 |
| Rule AI Suggestion | 返回轻量建议和风险提醒 | Should | source=`rule` |
| Actions | 返回可添加、编辑、标记完成能力 | Should | 前端控制按钮 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Goal Detail 看到目标进度和下一步任务，
以便从长期目标自然进入今天可以执行的任务。
```

### 主要流程

```text
GET /goals
-> GET /goals/{goal_id}/detail
-> user taps recommended_next_task
-> GET /tasks/{task_id}
-> POST /focus-sessions
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

无。复用：

```text
Goal
Task
TaskStep
```

### 状态机变更

无新增状态机。Goal Detail 读取现有：

```text
Goal.active / completed / archived
Task.active / in_focus / postponed / completed / archived
```

### 事件变更

无新增事件。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/goals/{goal_id}/detail` | Goal Detail 聚合 | path goal id | `GoalDetailResponse` |

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

P2 本轮只提供规则版建议：

- `source=rule`
- 根据任务是否为空、是否全部完成、deadline 风险和推荐下一步任务生成短建议
- 不写业务表，不生成 AIJob
- 不阻塞 Goal Detail 主响应

### LLM 安全边界

- [x] 不把规则建议包装成真实 LLM
- [x] 不伪造依赖边
- [x] 用户仍通过 Task Detail / Task Edit 修正具体任务

---

## 7. 验收标准

### 功能验收

- [x] 可以获取 Goal Detail 聚合。
- [x] 返回目标基础信息。
- [x] 返回进度统计和风险状态。
- [x] 返回未完成任务、已完成任务和推荐下一步任务。
- [x] 返回 dependency nodes，edges 为空并说明原因。
- [x] 返回规则版建议。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] 不新增 DB migration。
- [x] 归档任务不计入 Goal Detail 展示。
- [x] 完成率按非归档关联任务计算。
- [x] 推荐任务优先 active / in_focus，再 postponed，最后 completed 不参与推荐。

### 体验验收

- [x] 前端可以从推荐任务进入 Task Detail。
- [x] Goal Detail 不暴露过量中间数据。
- [x] Dependency Map 明确当前没有真实依赖边。

---

## 8. 测试计划

### 自动化检查

- [x] Service 测试：Goal Detail progress / task groups / suggestion
- [x] API 测试：Goal Detail response / user isolation
- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. Review 记录

- 保留 P1 `GET /goals/{goal_id}` 基础接口，新聚合使用 `/detail`，降低破坏面。
- Dependency Map 只返回节点顺序和说明，不提前制造不存在的依赖语义。
- AI Suggestion 目前明确为 `source=rule`，后续真实 LLM 接入时再引入 AIJob。
