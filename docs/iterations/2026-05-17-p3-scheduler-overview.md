# Iteration: P3 Scheduler Overview

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增统一 Scheduler Overview 只读接口，把 data source 与 reminder 两类调度契约汇总成部署视角，便于后续接 Celery Beat 前统一检查边界。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P3 已有 reminder scheduler contract 和 data source scheduler contract。它们各自清晰，但部署或回归时还缺少一个汇总视图来确认当前有哪些 scheduler domain、多少 entries、哪些 worker 进入 Beat proposal、哪些 worker 被排除。

### 目标

- 新增 `GET /api/v1/scheduler/overview`。
- overview 从现有 domain plan / beat proposal 派生，不复制配置。
- 展示 domain、plan path、beat path、entry counts、task names 和 guardrail count。
- P3 smoke 校验 overview 包含 `data_sources` 与 `reminders` 两个 domain。

### 非目标

- 不启动 scheduler。
- 不写 Celery Beat 配置。
- 不新增 worker。
- 不新增数据库表。

---

## 3. 产品约束对齐

### 核心路径

```text
Scheduler Contracts -> Scheduler Overview -> Deployment Readiness
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

Overview 让后台自动化保持可解释，帮助 Chronos 在变聪明之前先保持可信。

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
| Scheduler overview service | 汇总 data source / reminder scheduler contract | Must | 从现有方法派生 |
| Scheduler overview API | `GET /scheduler/overview` | Must | 只读 |
| Tests | service / API / smoke 覆盖 | Must | 不触发 worker |

### 用户故事

```text
作为后端开发者，
我希望有一个统一 scheduler overview，
以便上线自动调度前能快速看到所有调度域和被排除的 worker。
```

```text
作为 Chronos 用户，
我希望后台自动化上线前经过清晰边界检查，
以便系统不会因为调度配置失误而绕过我的确认权。
```

### 主要流程

```text
GET /scheduler/overview
-> derive data source summary from data source plan / beat proposal
-> derive reminder summary from reminder plan / beat proposal
-> return read-only overview
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
| GET | `/api/v1/scheduler/overview` | 汇总 scheduler domains | 无 | `SchedulerOverviewResponse` |

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

说明：本轮只读 scheduler overview，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] `GET /scheduler/overview` 返回 `data_sources` 与 `reminders` 两个 domain。
- [x] 每个 domain 返回 plan path、beat path、entry count、task names、excluded task names。
- [x] overview 从现有 plan / beat proposal 派生，不复制 scheduler 配置。
- [x] P3 smoke 校验 overview domains。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 migration。

### 体验验收

- [x] 后台自动化上线前更容易检查边界。
- [x] 不增加用户可见复杂度。

---

## 8. 测试计划

### 单元测试

- [x] scheduler service overview。

### API 测试

- [x] scheduler overview API。

### 集成测试

- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Overview 与 domain plan 漂移 | 汇总不可信 | 从现有 service 方法派生 |
| 返回过多配置细节 | 变成复杂控制台 | 只返回 counts、paths、task names，不返回完整 payload |

### 关键取舍

Overview 不重复完整 plan 内容，而是提供部署检查所需摘要，完整 guardrails 仍在 domain plan 中查看。

---

## 10. Review 记录

### 自检结论

- 与 P3 scheduler contracts 对齐。
- 只读，不触发 worker，不写库。
- 没有把 scheduler 做成可操作控制台，符合克制原则。

### 后续建议

- 若后续正式接 Beat，可让部署脚本读取 `*/celery-beat` proposal 生成配置。
