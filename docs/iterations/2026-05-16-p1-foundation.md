# Iteration: P1 Foundation

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-16  
> 负责人：Chronos Team  
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

跑通 Chronos P1 的工程基础和核心数据模型，为后续 Task / Goal API、Capture / Inbox、Today、Focus 和 Daily Report 提供稳定地基。

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

Chronos 的核心不是普通任务列表，而是 `Capture -> Inbox -> Today -> Task Detail -> Focus -> Report` 的每日执行闭环。进入具体功能开发前，需要先建立可持续扩展的模型层、事件层、AIJob 层和 service 边界，避免后续业务逻辑散落到 router / worker / model 中。

### 目标

- 统一项目基础命名和本地配置默认值。
- 建立 Alembic migration 基础结构。
- 实现 P1 foundation 核心模型：`User`、`UserSettings`、`Goal`、`Task`、`TaskStep`、`ActivityEvent`、`AIJob`。
- 建立基础 service 边界：`TaskService`、`GoalService`、`ActivityEventService`、`AIJobService`。
- 从 Git 索引移除 `.env` 和 `__pycache__`，避免本地敏感配置和编译产物继续进入版本管理。

### 非目标

- 不实现正式 Task / Goal API。
- 不实现 Capture / Inbox。
- 不实现 Today 聚合和 Rolling Plan。
- 不接入真实 LLM。
- 不实现 FocusSession、DailyPlan、DailyReport 等后续 P1 模型。

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
- [x] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本次迭代不增加前端复杂度，只建立后端内部复杂度承载层。模型和 service 保持清晰克制，让后续页面接口可以返回少而准的数据。

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
| 工程基础整理 | 统一命名、配置默认值、v1 router、`.env.example` | Must | P1 Step 0 |
| Alembic 初始化 | 新增 migration 基础结构和 foundation migration | Must | P1 Step 1 |
| 核心模型 | User、UserSettings、Goal、Task、TaskStep、ActivityEvent、AIJob | Must | 后续 API 的数据底座 |
| Service 骨架 | Task / Goal / ActivityEvent / AIJob service | Must | 先确定业务边界 |
| Git 卫生 | `.env`、`__pycache__` 从索引移除 | Must | 本地文件保留 |

### 用户故事

```text
作为 Chronos 的后端开发者，
我希望先拥有清晰的数据模型、状态枚举、事件记录和 service 边界，
以便后续实现 Capture、Today、Focus 等功能时不破坏核心闭环。
```

### 主要流程

```text
工程基础整理
-> Alembic 初始化
-> 核心模型创建
-> service 边界创建
-> 基础验证
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [x] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

新增模型：

```text
User
UserSettings
Goal
Task
TaskStep
ActivityEvent
AIJob
```

核心枚举：

```text
ValueLevel
PlanningPreference
AIStrategyPreference
GoalStatus
TaskStatus
TaskSource
EntityType
ActorType
EventSource
AIJobType
AIJobStatus
```

### 状态机变更

```text
Task.status = active | in_focus | completed | postponed | archived
AIJob.status = queued | running | succeeded | succeeded_with_fallback | failed | canceled
Goal.status = active | completed | archived
```

### 事件变更

本次 service 骨架已使用：

- GOAL_CREATED
- TASK_CREATED
- TASK_COMPLETED
- TASK_POSTPONED
- TASK_STEP_CREATED
- TASK_STEP_COMPLETED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| - | - | 本迭代不新增业务 API | - | - |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

本迭代不实现 Agent，但新增 `AIJob` 模型和 `AIJobService`，为后续 Capture Parser、Daily Planner、Task Breakdown、Daily Report Generator 提供异步任务状态底座。

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] `.env.example` 存在，`.env` 不再被 Git 跟踪。
- [x] `__pycache__` 不再被 Git 跟踪。
- [x] `app/api/v1/router.py` 存在并被 `main.py` 挂载。
- [x] Alembic 基础结构存在。
- [x] foundation migration 覆盖 P1 核心模型。
- [x] service 方法表达业务动作，而不是底层数据库操作。

### 数据验收

- [x] 关键数据模型可被 SQLAlchemy metadata 注册。
- [x] 状态枚举使用明确枚举，不使用随意字符串。
- [x] 任务状态变化写入 `ActivityEvent`。
- [x] AIJob 支持 `succeeded_with_fallback`。

### 体验验收

- [x] 本迭代不增加前端信息负担。
- [x] 后续页面接口具备保持克制的模型基础。
- [x] 核心流程未来不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Model metadata 测试
- [x] Enum value 测试
- [x] Service method import 测试

### API 测试

- [ ] 本迭代不新增业务 API

### 集成测试

- [x] Alembic migration 文件存在
- [x] `alembic upgrade head --sql` 可生成 PostgreSQL DDL
- [x] 本地数据库 migration upgrade

### 手动验证

```text
1. 导入 app.models，确认 SQLAlchemy metadata 能看到 foundation tables。
2. 导入核心 service，确认模块边界无循环依赖。
3. 运行基础 unittest。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| P1 先不做完整 API | 暂时不能通过 HTTP 使用模型 | 下一迭代进入 Task / Light Goal API |
| FocusSession / DailyPlan 暂未建模 | Today / Focus 还无法落库 | 后续按闭环逐步补齐 |
| service 当前直接使用 db session | 后续复杂查询可能膨胀 | P1 保持简单，必要时再引入 repository 并更新规范 |

### 关键取舍

- 先做 foundation，不提前实现 Capture / Today / Focus。
- `ActivityEvent` 先作为统一事实记录，后续计划和复盘都基于事件扩展。
- `AIJob` 先支持 mock / fallback 需要的状态，不绑定具体 provider。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | P1 service 直接使用 db session | 当前业务还轻，减少过早抽象 | 后续引入 repository 需更新规范 |
| 2026-05-16 | 先移除 `.env` 和 `__pycache__` 索引 | 避免本地配置和编译产物污染版本库 | 本地文件保留，不影响运行 |
| 2026-05-16 | `AIJob.metadata` 在 ORM 中命名为 `job_metadata` | 避免与 SQLAlchemy declarative 保留属性冲突 | 数据库列名仍为 `metadata` |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 foundation iteration 文档 | `docs/iterations/2026-05-16-p1-foundation.md` | 本文件 |
| 2026-05-16 | 新增核心模型与枚举 | `app/models/*` | P1 Step 1 |
| 2026-05-16 | 新增 Alembic migration | `alembic/*` | P1 Step 1 |
| 2026-05-16 | 新增 service 骨架 | `app/services/*` | P1 Step 1 |
| 2026-05-16 | 新增基础测试 | `tests/*` | foundation 验证 |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `python -m unittest discover -s tests`
- [x] `alembic upgrade head --sql`
- [x] `alembic upgrade head`
- [x] `alembic current`

### 未验证

- 无

### 已知问题

- 当前还没有业务 API，下一迭代需要补 Task / Light Goal API。

---

## 13. 后续迭代建议

- P1 Task / Light Goal API。
- Capture / Inbox 文本输入闭环。
- DailyPlan / Today 基础聚合。
