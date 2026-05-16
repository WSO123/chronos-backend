# Iteration: P1 Task / Light Goal API

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-16  
> 负责人：Chronos Team  
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 Chronos P1 的 Task / Light Goal 基础 API，让后续 Capture / Inbox、Today、Task Detail 和 Focus 可以复用同一套任务与目标底座。

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

### 背景

P1 foundation 已经建立核心模型、事件记录和 service 边界。下一步需要把 Task 和轻量 Goal 暴露为可用 API，让用户可以创建、查看、编辑、完成和延后任务，并能把任务关联到目标。

### 目标

- 实现 Task 基础 API。
- 实现 TaskStep 创建和完成 API。
- 实现 Task events 查询 API。
- 实现 Light Goal 创建、列表、详情和编辑 API。
- 建立 P1 临时用户上下文依赖，使用 `X-User-Id` 做 user_id 隔离。
- 补齐 API / service 测试。
- 收紧任务状态流转，避免重复完成 / 延后污染事件数据。
- 提供本地开发用户 seed 脚本，方便启动数据库后手动验证 API。

### 非目标

- 不实现用户注册 / 登录 / 鉴权。
- 不实现 Capture / Inbox。
- 不实现 Today 聚合。
- 不实现 Goal Detail 的完整目标洞察、依赖图、风险分析。
- 不接入真实 LLM。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [ ] AI Agent

### 产品人格

本迭代只提供执行前必要的任务和目标信息，不把 Task Detail 做成信息仓库。任务历史通过单独 events API 获取。

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
| Task API | 创建、查看、编辑、完成、延后 | Must | P1 基础任务能力 |
| TaskStep API | 创建步骤、完成步骤 | Must | Task Detail / Focus 共用 |
| Task Events API | 查询任务事件 | Must | 避免 Task Detail 承载历史仓库 |
| Light Goal API | 创建、列表、详情、编辑目标 | Must | P1 只做轻量目标 |
| 用户上下文 | `X-User-Id` 依赖 | Must | 后续替换为 auth |
| 统一错误响应 | 404 / invalid state / missing user id | Must | 保持 API 可读 |
| Dev seed | 创建本地开发用户 | Should | 用于手动 API 验证 |

### 用户故事

```text
作为 Chronos 用户，
我希望可以创建目标和任务，并能完成、延后、拆分任务步骤，
以便系统开始承载每天真正可执行的行动对象。
```

### 主要流程

```text
创建 Goal
-> 创建 Task 并关联 Goal
-> 查看 Task Detail
-> 创建 / 完成 TaskStep
-> 完成或延后 Task
-> 查询 Task events
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

无新增状态。使用既有状态：

```text
Task.active -> Task.completed
Task.in_focus -> Task.completed
Task.active -> Task.postponed
Task.in_focus -> Task.postponed
```

重复完成、重复延后、已完成任务继续创建 / 完成步骤均返回 `INVALID_STATE`。

### 事件变更

使用既有事件：

- GOAL_CREATED
- GOAL_UPDATED
- TASK_CREATED
- TASK_UPDATED
- TASK_COMPLETED
- TASK_POSTPONED
- TASK_STEP_CREATED
- TASK_STEP_COMPLETED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/tasks` | 创建任务 | TaskCreate | TaskResponse |
| GET | `/api/v1/tasks/{task_id}` | 获取任务详情 | - | TaskResponse |
| PATCH | `/api/v1/tasks/{task_id}` | 编辑任务 | TaskUpdate | TaskResponse |
| POST | `/api/v1/tasks/{task_id}/complete` | 完成任务 | - | TaskResponse |
| POST | `/api/v1/tasks/{task_id}/postpone` | 延后任务 | - | TaskResponse |
| POST | `/api/v1/tasks/{task_id}/steps` | 创建任务步骤 | TaskStepCreate | TaskStepResponse |
| POST | `/api/v1/tasks/{task_id}/steps/{step_id}/complete` | 完成步骤 | - | TaskStepResponse |
| GET | `/api/v1/tasks/{task_id}/events` | 查询任务事件 | - | ActivityEventResponse[] |
| POST | `/api/v1/goals` | 创建目标 | GoalCreate | GoalResponse |
| GET | `/api/v1/goals` | 目标列表 | - | GoalResponse[] |
| GET | `/api/v1/goals/{goal_id}` | 目标详情 | - | GoalResponse |
| PATCH | `/api/v1/goals/{goal_id}` | 编辑目标 | GoalUpdate | GoalResponse |

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
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 可以创建、查看、编辑、完成、延后任务。
- [x] 可以创建和完成任务步骤。
- [x] 可以查询任务事件。
- [x] 可以创建、查看、编辑轻量目标。
- [x] 不同 `X-User-Id` 之间数据隔离。
- [x] 404 / invalid state 返回统一错误结构。

### 数据验收

- [x] 任务和目标写入正确。
- [x] 关键状态流转正确。
- [x] 任务操作写入 `ActivityEvent`。
- [x] 不新增不必要数据模型。

### 体验验收

- [x] Task Detail API 默认不返回大量历史事件。
- [x] events 单独查询。
- [x] Goal Detail 保持轻量。

---

## 8. 测试计划

### 单元测试

- [x] Service 创建 / 更新 Task
- [x] Service 完成 / 延后 Task
- [x] Service 创建 / 完成 TaskStep
- [x] Service 创建 / 更新 Goal
- [x] ActivityEvent 写入

### API 测试

- [x] Task happy path
- [x] Goal happy path
- [x] 404
- [x] invalid state
- [x] user_id 隔离

### 集成测试

- [x] 使用测试数据库创建 schema
- [x] FastAPI dependency override

### 手动验证

```text
1. 启动服务。
2. 使用 X-User-Id 请求创建 Goal。
3. 创建 Task 并关联 Goal。
4. 完成步骤和任务。
5. 查询 Task events。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 暂用 `X-User-Id` | 不是正式鉴权 | P1 用于 user_id 隔离，后续替换为 auth dependency |
| Goal Detail 轻量 | 暂不支持目标洞察 | P2 再做完整 Goals |
| API 先不接 AI | 不能自动拆解任务 | 后续 Task Breakdown Agent 接入 |

### 关键取舍

- 先让任务和目标对象可用，再做 Capture / Inbox。
- Task events 独立接口，避免 Task Detail 变成信息仓库。
- P1 暂时不引入认证系统。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | P1 API 使用 `X-User-Id` | 当前还没有 auth 模块，但需要 user_id 隔离 | 后续接登录后替换依赖即可 |
| 2026-05-16 | Task events 单独接口 | 遵守 Task Detail 不做信息仓库 | 前端按需加载历史 |
| 2026-05-16 | 手动 Task API 不暴露 `source` 输入 | 避免客户端伪造 AI / email / calendar 来源 | Capture / 外部来源后续由对应 service 内部设置 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Task / Light Goal 迭代文档 | `docs/iterations/2026-05-16-p1-task-goal-api.md` | 本文件 |
| 2026-05-16 | 新增 API 公共依赖和错误响应 | `app/api/deps.py`、`app/api/errors.py` | `X-User-Id` 和统一错误结构 |
| 2026-05-16 | 新增 Task / Goal schemas | `app/schemas/tasks.py`、`app/schemas/goals.py` | 请求与响应结构 |
| 2026-05-16 | 补齐 Task / Goal service 能力 | `app/services/task_service.py`、`app/services/goal_service.py` | 查询、更新、事件、状态边界 |
| 2026-05-16 | 新增 Task / Goal API | `app/api/v1/tasks.py`、`app/api/v1/goals.py` | P1 业务 API |
| 2026-05-16 | 收紧状态机和输入边界 | `app/services/task_service.py`、`app/schemas/tasks.py` | 防止重复事件和来源伪造 |
| 2026-05-16 | 新增开发用户 seed 脚本 | `scripts/dev_seed_user.py` | 方便本地手动调 API |
| 2026-05-16 | 新增 service / API 测试 | `tests/test_task_goal_services.py`、`tests/test_task_goal_api.py` | 16 个测试通过 |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests`
- [x] `python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- 无

### 已知问题

- P1 仍使用 `X-User-Id` 作为临时用户上下文，后续接认证系统时需要替换 dependency。

---

## 13. 后续迭代建议

- Capture / Inbox 文本输入闭环。
- Today / DailyPlan 基础聚合。
- Task Breakdown mock Agent。
