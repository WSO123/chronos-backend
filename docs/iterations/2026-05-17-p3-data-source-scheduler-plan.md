# Iteration: P3 Data Source Scheduler Plan

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Data Source Scheduler Plan 只读接口和 Celery Beat proposal，使 calendar / email / health sync worker 的调度边界与 reminder worker 一样可查询、可测试、可解释。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P3 已有 `data_source.sync_ready_connections` 与 `health.sync_ready_energy_connections`，但缺少和 reminder 一致的 scheduler contract。若后续直接写部署配置，容易把“外部输入必须进 Capture / Inbox”和“健康数据只服务 Energy / Today 策略”的边界散落到运维层。

### 目标

- 新增 `GET /api/v1/scheduler/data-sources`。
- 新增 `GET /api/v1/scheduler/data-sources/celery-beat`。
- 明确 calendar / email sync 只进入 Capture / Inbox，不自动确认任务。
- 明确 health sync 只写 EnergyDailyMetric，不创建任务、提醒或 Today。
- P3 smoke 覆盖新增 scheduler contract。

### 非目标

- 不启动 Celery Beat。
- 不执行 worker。
- 不新增真实 provider。
- 不新增数据库表。

---

## 3. 产品约束对齐

### 核心路径

```text
Data Source -> Capture / Inbox -> Energy -> Today Strategy Context
```

- [x] Capture
- [x] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

调度契约先把后台自动化说清楚，再考虑真正启用，让 Chronos 的“聪明”保持可解释和可信。

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
| Data source scheduler plan | 返回数据接入 worker 调度契约 | Must | 只读 |
| Data source beat proposal | 返回 JSON-friendly Beat proposal | Must | 不写 Celery 配置 |
| Guardrails | 明确不自动确认、不创建 Today、不创建提醒 | Must | 防止后台越界 |
| Smoke alignment | P3 smoke 校验新增 scheduler contract | Must | 防回归 |

### 用户故事

```text
作为 Chronos 用户，
我希望外部数据接入在后台运行时仍然保持克制，
以便日历、邮件和健康数据能帮助我安排今天，但不会替我偷偷确认任务。
```

```text
作为后端开发者，
我希望数据接入 worker 的调度策略有明确契约，
以便后续接 Celery Beat 时不会破坏 Capture / Inbox 和 Energy 的边界。
```

### 主要流程

```text
GET /scheduler/data-sources
-> read static scheduler contract
-> GET /scheduler/data-sources/celery-beat
-> deployment uses proposal explicitly
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
| GET | `/api/v1/scheduler/data-sources` | 数据接入 worker 调度计划 | 无 | `DataSourceSchedulerPlanResponse` |
| GET | `/api/v1/scheduler/data-sources/celery-beat` | 数据接入 Beat proposal | 无 | `DataSourceCeleryBeatScheduleResponse` |

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

说明：本轮只读 scheduler contract，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] `GET /scheduler/data-sources` 返回 `data_source.sync_ready_connections` 和 `health.sync_ready_energy_connections`。
- [x] `GET /scheduler/data-sources/celery-beat` 返回两个 ready fanout worker。
- [x] Beat proposal 排除单连接 worker。
- [x] Guardrails 明确 calendar/email 不自动确认，health 不创建任务、提醒或 Today。
- [x] P3 smoke 校验新增 data source scheduler entries。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 migration。

### 体验验收

- [x] 后台自动化边界可解释。
- [x] 数据接入仍服务执行闭环，不替用户决策。

---

## 8. 测试计划

### 单元测试

- [x] scheduler service data source plan / beat proposal。

### API 测试

- [x] scheduler API data source plan / beat proposal。

### 集成测试

- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Contract 与真实部署配置漂移 | 生产调度可能不一致 | 后续 Beat wiring 从 service 输出生成 |
| 数据源 sync 频率过高 | provider 压力或重复导入 | 先只提供 proposal，真实部署前再按 provider 限流调整 |
| health 与 calendar/email 混在同一入口 | 语义不清 | 分别列 entry 和 guardrails |

### 关键取舍

本轮仍不启动自动调度，只先沉淀契约，保持 P3 自然生长模块的可信边界。

---

## 10. Review 记录

### 自检结论

- 与 P3 信息架构一致：数据接入服务 Capture / Inbox 与 Energy，而不是一级导航扩张。
- 与产品人格一致：调度先可解释，后自动化。
- 与工程规范一致：只读接口不写库，worker 边界沉淀在 service。

### 后续建议

- 后续可补统一 scheduler overview，把 reminders 与 data sources 汇总为一个部署视图。
