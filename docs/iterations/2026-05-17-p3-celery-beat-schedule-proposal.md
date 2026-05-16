# Iteration: P3 Celery Beat Schedule Proposal

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Reminder Celery Beat Schedule Proposal，只读返回 JSON-friendly 的 Beat 配置草案，并明确排除需要 per-user fanout 的 execution reminder。

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

上一轮建立了 scheduler contract，但真正进入部署时还需要一个接近 Celery Beat 的配置视图。为了避免直接修改运行时调度，本轮只生成 JSON-friendly proposal，帮助后续配置落地和 review。

### 目标

- 新增 `GET /api/v1/scheduler/reminders/celery-beat`。
- 返回 deadline generator、dispatch_due、cleanup worker 的 Beat 草案。
- 明确 `reminder.generate_execution` 被排除，因为它需要已有 Today active plan 和 per-user fanout。
- 保持只读，不修改 celery runtime。

### 非目标

- 不启动 Celery Beat。
- 不写 `celery_app.conf.beat_schedule`。
- 不新增 execution fanout worker。
- 不做生产部署配置。

---

## 3. 产品约束对齐

### 核心路径

```text
Scheduler Contract -> Celery Beat Proposal -> Explicit Deployment Wiring
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

自动化必须先可解释、可 review，再进入后台运行。此轮继续保持“聪明但不自作主张”。

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
| Beat proposal service | 返回 JSON-friendly Beat 草案 | Must | read-only |
| Beat proposal API | `GET /scheduler/reminders/celery-beat` | Must | 开发态鉴权 |
| Excluded entries | 明确 execution fanout 不直接调度 | Must | 防隐式 Today 创建 |
| Tests | service / API 测试 | Must | 不触发 worker |

### 用户故事

```text
作为后端开发者，
我希望能看到接近 Celery Beat 的 reminder 调度草案，
以便后续部署配置可以被 review，而不是散落在环境里。
```

```text
作为 Chronos 用户，
我希望后台自动化不会绕过 Today 计划边界，
以便系统不会偷偷替我重新安排一天。
```

### 主要流程

```text
GET /scheduler/reminders/celery-beat
-> return schedule entries
-> list excluded fanout entries
-> deployment wires explicitly later
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
| GET | `/api/v1/scheduler/reminders/celery-beat` | Reminder Beat 草案 | 无 | `ReminderCeleryBeatScheduleResponse` |

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

说明：本轮是 scheduler proposal，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 返回 deadline / dispatch / cleanup 三类可直接 Beat 化的任务。
- [x] 不包含 execution generator。
- [x] excluded_entries 说明 execution 需要 active Today plan。
- [x] endpoint 不修改 celery runtime。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 migration。

### 体验验收

- [x] 后台自动化边界清晰。
- [x] Today 计划不被隐式创建。

---

## 8. 测试计划

### 单元测试

- [x] service 返回 Beat proposal。
- [x] execution fanout 被排除。

### API 测试

- [x] GET /scheduler/reminders/celery-beat。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Proposal 与真实 Beat 配置漂移 | 部署不一致 | 后续从 service 生成 runtime config |
| Execution 不自动调度 | 仍需 fanout worker | 后续单独做 fanout |
| Crontab UTC 需要理解 | 本地时间换算成本 | response 明确 timezone=UTC |

### 关键取舍

- 取舍 1：只读 proposal，不改运行配置。
- 取舍 2：排除 execution generator，避免隐式 Today plan。
- 取舍 3：只输出 JSON-friendly 配置，不直接使用 Celery crontab object。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Execution fanout excluded | 需要 active Today plan | 后续补 fanout worker |
| 2026-05-17 | Beat proposal 使用 JSON-friendly schedule | API 可读可测 | 部署层再转换为 Celery 对象 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 Beat proposal service/API/schema | Scheduler modules | read-only |
| 2026-05-17 | 补测试 | Scheduler tests | service / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | Beat proposal |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_scheduler_services tests.test_scheduler_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 Celery Beat 配置转换。
- [ ] Execution fanout worker。

### 已知问题

- 当前 proposal 不会自动进入 `celery_app.conf.beat_schedule`。

---

## 13. 后续迭代建议

- Execution reminder fanout worker。
- P3 stabilization review。
- Reminder read/seen state。
