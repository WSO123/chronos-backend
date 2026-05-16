# Iteration: P3 Execution Reminder Fanout

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 `reminder.generate_execution_for_active_users` fanout worker，批量为已有 Today active plan 的 active users 生成 execution reminders，并跳过 no-plan 用户，避免定时调度隐式创建 Today。

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

单用户 execution reminder generator 已经具备“existing Today plan only”的边界，但定时调度不能直接调用单用户任务。上一轮 Beat proposal 将 execution 排除，本轮补一个安全 fanout worker，让调度层可以批量处理 active users，同时继续避免隐式创建 Today。

### 目标

- 新增 active users fanout service。
- 新增 Celery task `reminder.generate_execution_for_active_users`。
- 对无 active Today plan 的用户计入 `no_plan_count` 并跳过。
- 对关闭 execution reminders 的用户计入 `disabled_count`。
- Scheduler plan / Beat proposal 纳入 fanout worker。

### 非目标

- 不创建 Today plan。
- 不 replan。
- 不发送提醒。
- 不实现复杂分片游标。

---

## 3. 产品约束对齐

### 核心路径

```text
Today active plan -> Execution Reminder Fanout -> Reminder Center
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [x] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Fanout 只顺着用户已经拥有的 Today 计划生成温和提醒，不在后台替用户重新安排一天。

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
| Fanout service | 遍历 active users | Must | max_users clamp |
| No-plan skip | 无 Today active plan 不创建 | Must | no_plan_count |
| Disabled skip | 设置关闭时跳过 | Must | disabled_count |
| Worker task | JSON-ready payload | Must | Celery |
| Scheduler alignment | plan / Beat proposal 纳入 fanout | Must | interval proposal |

### 用户故事

```text
作为 Chronos 用户，
我希望系统只基于我已经存在的 Today 计划做执行提醒，
以便后台自动化不会突然替我创建或重排计划。
```

```text
作为后端开发者，
我希望 execution reminder 有安全 fanout worker，
以便后续定时调度可以批量运行，同时保持 no-plan skip。
```

### 主要流程

```text
reminder.generate_execution_for_active_users
-> load active users
-> check existing active Today plan
-> call single-user execution generator
-> aggregate counts
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。只创建 scheduled reminders。

### 事件变更

无。

### API 变更

无 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `reminder.generate_execution_for_active_users` | 批量生成 execution reminders |

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

说明：本轮是规则 fanout，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 有 active Today plan 的用户可生成 execution reminders。
- [x] 无 plan 用户计入 no_plan_count，不创建 Today。
- [x] disabled 用户计入 disabled_count。
- [x] worker 返回 JSON-ready payload。
- [x] Scheduler plan 和 Beat proposal 使用 fanout worker。

### 数据验收

- [x] 不新增模型。
- [x] 不修改 DailyPlan / DailyPlanItem。
- [x] 幂等逻辑复用单用户 generator。

### 体验验收

- [x] 不偷偷创建 Today。
- [x] 不在 Today 首屏增加复杂度。

---

## 8. 测试计划

### 单元测试

- [x] fanout skips no-plan users。
- [x] fanout tracks disabled users。
- [x] worker JSON-ready result。
- [x] scheduler plan / Beat proposal includes fanout。

### API 测试

- [x] scheduler API reflects fanout task。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| active users 太多 | 单次任务过重 | max_users clamp，后续补 cursor |
| Fanout 被过早调度 | 可能多次运行 | 单用户 generator 幂等 |
| 无 plan 用户多 | 结果噪音 | no_plan_count 明确暴露 |

### 关键取舍

- 取舍 1：先 max_users，不做分页游标。
- 取舍 2：无 plan 只 skip，不创建 Today。
- 取舍 3：Beat proposal 使用 fanout，而不是单用户 worker。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Fanout 先用 max_users | P3 保持轻量 | 后续可补 cursor |
| 2026-05-17 | No-plan skip | 防止隐式 Today 创建 | 调度可安全重复运行 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 fanout service/worker | Reminder service / workers | execution reminders |
| 2026-05-17 | Scheduler plan / Beat proposal 纳入 fanout | Scheduler service | safe fanout |
| 2026-05-17 | 补测试 | Reminder / Scheduler tests | service / worker / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | fanout worker |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_scheduler_services tests.test_scheduler_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 大用户量分片。
- [ ] 真实 Celery Beat 运行。

### 已知问题

- 当前 fanout 只有 `max_users`，没有 cursor / pagination。

---

## 13. 后续迭代建议

- P3 stabilization review。
- Reminder read/seen state。
- Calendar provider adapter hardening。
