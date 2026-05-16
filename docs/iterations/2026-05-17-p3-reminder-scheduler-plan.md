# Iteration: P3 Reminder Scheduler Plan

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Reminder Scheduler Plan 只读接口，沉淀 reminder generator / dispatch worker 的调度频率、scope 和 guardrails，但不直接启动定时任务。

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

P3 自动提醒已经具备 deadline generator、execution generator、dispatch worker、delivery provider 和 cooldown。下一步如果直接接 Celery Beat，容易把调度频率和产品边界散落在部署配置里，因此先建立可查询、可测试的 scheduler contract。

### 目标

- 新增 `GET /api/v1/scheduler/reminders`。
- 描述 reminder 相关 worker 的 cadence、scope、payload_template。
- 明确 execution generator 不创建 Today、不 replan。
- 明确 dispatch_due 保留 delivery provider 和 cooldown 语义。

### 非目标

- 不启动 Celery Beat。
- 不写定时任务到数据库。
- 不触发任何 worker。
- 不新增 scheduler admin UI。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder Scheduler Plan -> Reminder Workers -> Reminder Center
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

调度计划先清晰可解释，再进入自动化，避免“聪明”变成用户不可理解的后台动作。

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
| Scheduler plan service | 返回 reminder worker 调度计划 | Must | 只读 |
| Scheduler API | `GET /scheduler/reminders` | Must | 开发态鉴权 |
| Guardrails | 每个 entry 明确边界 | Must | 防止隐式 replan |
| Tests | service / API 测试 | Must | 不触发 worker |

### 用户故事

```text
作为后端开发者，
我希望 reminder worker 的调度策略有一个可查询契约，
以便部署定时任务时不会破坏产品边界。
```

```text
作为 Chronos 用户，
我希望自动提醒的后台运行方式是克制、可解释的，
以便系统不会在我不知情时重新安排 Today。
```

### 主要流程

```text
GET /scheduler/reminders
-> return static scheduler contract
-> deployment reads contract
-> explicit scheduler wiring happens outside this endpoint
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

无。

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/scheduler/reminders` | Reminder worker 调度计划 | 无 | `ReminderSchedulerPlanResponse` |

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

说明：本轮是 scheduler contract，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 返回 deadline / execution / dispatch 三类 reminder worker。
- [x] 每个 entry 有 cadence、scope、payload_template 和 guardrails。
- [x] endpoint 不触发 worker。
- [x] execution entry 明确 existing Today plan only。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 migration。

### 体验验收

- [x] 调度策略可解释。
- [x] 自动化不绕过用户控制感。

---

## 8. 测试计划

### 单元测试

- [x] scheduler service entries。

### API 测试

- [x] GET /scheduler/reminders。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 只读 contract 与部署配置漂移 | 真实调度可能不一致 | 后续接 Celery Beat 时从同一 service 生成配置 |
| 暂不自动调度 | 需要人工 wiring | 当前更安全，避免后台行为失控 |
| Scheduler API 暴露给普通用户 | 无实际业务数据 | 仍要求开发态 X-User-Id |

### 关键取舍

- 取舍 1：先契约，后自动调度。
- 取舍 2：不把 scheduler 状态持久化。
- 取舍 3：调度 guardrails 写进 response，方便 review。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Scheduler plan 是只读 contract | 自动调度前先稳定边界 | 不触发 worker |
| 2026-05-17 | Execution reminder 需要 active Today plan | 避免隐式创建计划 | 调度层需要 fanout 判断 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 scheduler service/schema/API | `app/services/scheduler_service.py` / `app/api/v1/scheduler.py` | reminder plan |
| 2026-05-17 | 注册 router | `app/api/v1/router.py` | `/scheduler/reminders` |
| 2026-05-17 | 补测试 | `tests/test_scheduler_services.py` / `tests/test_scheduler_api.py` | service / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | scheduler contract |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_scheduler_services tests.test_scheduler_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] Celery Beat 实际配置。
- [ ] 生产调度部署。

### 已知问题

- 当前只是 contract，不是 active scheduler。后续接 Celery Beat 时应从该 service 复用 entry 定义。

---

## 13. 后续迭代建议

- Delivery attempt cleanup worker。
- Celery Beat config generation from scheduler plan。
- Reminder read/seen state。
