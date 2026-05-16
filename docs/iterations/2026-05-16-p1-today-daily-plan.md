# Iteration: P1 Today / DailyPlan

> 状态：Done
> 阶段：P1
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 Chronos P1 的 Today / DailyPlan 基础调度，让正式 Task 能被持久化为当天推荐执行顺序，并通过轻量 Today 聚合接口进入执行闭环。

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

Capture / Inbox 已经能把输入确认生成 Task / Goal。下一步需要把 Task 组织成 Today 的执行顺序。Today 不是实时任务列表，而是 `DailyPlan` 快照，必须保存推荐顺序、策略摘要和进度状态，为后续 Focus / Report 提供数据基础。

### 目标

- 新增 `DailyPlan`、`PlanRevision`、`StrategySnapshot`、`DailyPlanItem` 模型和 migration。
- 实现 `GET /api/v1/today`，首次打开当天 Today 时 lazy create active DailyPlan。
- 实现 `POST /api/v1/today/replan`，按规则生成新的 plan revision。
- 实现 `PATCH /api/v1/today/items/{item_id}`，支持 Today 内完成 / 延后 / 跳过等轻操作。
- Replan 时保留当天已完成项，避免今日进度因重排回落。
- Today item 从 postponed 改回 planned 时，同步 Task 回到 active。
- P1 使用 rule planner，不接真实 LLM，不返回复杂评分细节。

### 非目标

- 不实现真实 LLM Daily Planner。
- 不实现 Strategy Detail。
- 不实现复杂时间块日历排程。
- 不实现 P2 洞察、精力预测和任务依赖调度。
- 不实现 FocusSession / DailyReport。

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
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本迭代让 Today 回答“今天先做什么”，但不展示复杂 score factors。规则排序、section 判断和策略因子保存在后端，前端默认只拿到摘要、行动序列、进度和 quick actions。

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
| DailyPlan 快照 | 保存用户某天 active plan | Must | 一天一个 active plan |
| PlanRevision | replan 时生成新版本 | Must | 保留历史 revision item |
| StrategySnapshot | 保存轻量策略摘要 | Must | Today 默认不返回 score factors |
| DailyPlanItem | 保存任务顺序、section 和状态 | Must | 当前 revision 作为 Today 来源 |
| Today API | 返回首页聚合数据 | Must | 轻量、克制 |
| Today item 操作 | 完成 / 延后 / 跳过今日项 | Must | 同步 Task 状态 |
| Replan 进度保护 | 已完成项在新 revision 中继续保留 | Must | 防止完成率回落 |

### 用户故事

```text
作为 Chronos 用户，
我希望打开 Today 时直接看到今天推荐的执行顺序，
并能快速完成或延后任务，
以便减少每天重新排任务的认知成本。
```

### 主要流程

```text
GET /today
-> DailyPlan lazy create
-> rule planner
-> DailyPlanItem ordered sequence
-> StrategySnapshot
-> TodayResponse
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
DailyPlan
PlanRevision
StrategySnapshot
DailyPlanItem
```

### 状态机变更

```text
DailyPlan.draft -> active
DailyPlan.active -> closed

DailyPlanItem.planned -> completed
DailyPlanItem.planned -> postponed
DailyPlanItem.planned -> skipped
```

P1 仅实际使用 active plan；draft / closed 为后续扩展保留。

### 事件变更

- DAILY_PLAN_CREATED
- DAILY_PLAN_REPLANNED
- DAILY_PLAN_ITEM_UPDATED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/today` | 获取 Today 聚合，必要时自动创建 DailyPlan | `plan_date` query | TodayResponse |
| POST | `/api/v1/today/replan` | 重新生成当前日期 plan revision | TodayReplanRequest | TodayResponse |
| PATCH | `/api/v1/today/items/{item_id}` | 更新今日项状态 | TodayItemUpdate | TodayTaskResponse |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及 mock/rule Agent
- [ ] 新增真实 Agent
- [ ] 修改真实 LLM Prompt
- [x] 定义 Daily Planner Structured Output 形态
- [x] 修改 fallback

### Agent 设计

P1 不接真实 LLM。`PlanningService` 使用 rule planner：

- 输入对象：active / postponed Task
- 输出对象：DailyPlan、PlanRevision、StrategySnapshot、DailyPlanItem
- fallback：即使没有任务，也生成空 Today plan 和轻量策略摘要
- 是否需要用户确认：用户可 replan / 手动操作 item

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] P1 规则输出经过 service 统一落库
- [x] 失败时仍可打开 Today
- [ ] AIJob 状态可查询（P1 同步 rule planner 暂不创建 AIJob，异步 LLM 接入时补齐）
- [x] 用户保留 replan 和轻操作权

---

## 7. 验收标准

### 功能验收

- [x] 首次打开 Today 自动生成 DailyPlan。
- [x] Today 返回推荐执行序列、策略摘要、进度和 quick actions。
- [x] Replan 生成新的 PlanRevision。
- [x] Replan 后当天已完成任务仍保留在当前 Today 进度中。
- [x] Today item 完成时同步 Task.completed。
- [x] Today item 延后时同步 Task.postponed。
- [x] Today item 改回 planned 时同步 Task.active。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] DailyPlan / revision / strategy / items 正确落库。
- [x] Today 默认读取 current revision。
- [x] 旧 revision item 不允许通过 Today 当前接口修改。
- [x] 关键动作写入 `ActivityEvent`。

### 体验验收

- [x] Today response 不返回 score factors。
- [x] Today 以行动序列为核心，不返回复杂洞察。
- [x] 核心流程不依赖真实 LLM。

---

## 8. 测试计划

### 单元测试

- [x] Today lazy create
- [x] rule planner section 排序
- [x] replan version 增长
- [x] replan 保留已完成进度
- [x] item complete 同步 Task 和事件
- [x] item planned 重新激活 postponed Task

### API 测试

- [x] `GET /today`
- [x] `POST /today/replan`
- [x] `PATCH /today/items/{item_id}`
- [x] user_id 隔离
- [x] old revision item blocked

### 集成测试

- [x] Alembic migration 可生成 SQL
- [x] FastAPI dependency override

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| rule planner 简单 | 排序不够智能 | P1 先证明 DailyPlan 快照和闭环，后续替换 Daily Planner Agent |
| replan 不做复杂 diff 展示 | 前端暂时不能展示详细变化解释 | diff_payload 先保存 task ids，P2 再增强 |
| Today item 操作只覆盖基础状态 | Focus 后状态同步未完成 | FocusSession 迭代中补齐 |

### 关键取舍

- P1 先做 DailyPlan 持久化，不做日历时间块。
- Today 默认不暴露 `score_factors`。
- Rule planner 用 section + sort_order 表达推荐顺序，为后续 LLM adapter 留接口。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | 首次打开 Today lazy create DailyPlan | 降低前端调用复杂度 | Today 始终可用 |
| 2026-05-16 | Replan 生成新 PlanRevision | 保留滚动计划历史 | 后续 Report 可引用 plan version |
| 2026-05-16 | P1 使用 rule planner | 不让 LLM 可用性阻塞核心闭环 | 后续升级 Daily Planner Agent |
| 2026-05-16 | Today 默认不返回 score factors | 避免首页变成驾驶舱 | Strategy Detail 后续单独实现 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Today / DailyPlan 迭代文档 | `docs/iterations/2026-05-16-p1-today-daily-plan.md` | 本文件 |
| 2026-05-16 | 新增 DailyPlan 模型和 migration | `app/models/daily_plan.py`、`alembic/versions/20260516_0003_today_daily_plan.py` | P1 Today 快照 |
| 2026-05-16 | 新增 PlanningService | `app/services/planning_service.py` | rule planner + item action |
| 2026-05-16 | 新增 Today API 和 schema | `app/api/v1/today.py`、`app/schemas/today.py` | 首页聚合接口 |
| 2026-05-16 | 扩展 TaskService 内部事务能力 | `app/services/task_service.py` | 支持 Today item 操作同事务同步 |
| 2026-05-16 | 新增 service / API 测试 | `tests/test_today_services.py`、`tests/test_today_api.py` | 覆盖主路径和边界 |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `alembic upgrade head --sql`
- [x] `alembic upgrade head`
- [x] `git diff --check`

### 未验证

- 无

### 已知问题

- P1 使用 rule planner，排序质量只服务闭环验证，后续需要替换为 Daily Planner Agent / LLM adapter。
- FocusSession 未实现前，`focus_minutes` 保持为 0。

---

## 13. 后续迭代建议

- Task Detail 承接层。
- FocusSession 基础执行。
- Daily Report 基础复盘。
