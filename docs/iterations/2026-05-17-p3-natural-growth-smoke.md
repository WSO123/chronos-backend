# Iteration: P3 Natural Growth Smoke

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 P3 自然生长闭环 smoke 脚本，把健康数据接入、外部日历输入、Today、执行提醒、提醒已读、提醒派发和调度契约串成一次可重复回归。

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

P3 已经分多轮完成数据源、外部输入、健康精力、Reminder Center、提醒生成、派发、已读和 scheduler contract。需要一个稳定 smoke，验证这些能力组合后仍然服务主闭环，而不是变成割裂的后台模块。

### 目标

- 新增 `scripts/smoke_p3_natural_growth_loop.py`。
- 验证 health data source 可同步为 Energy Dashboard 数据。
- 验证 calendar external import 可进入 Capture / Inbox，并由用户归类后进入 Task / Today。
- 验证 execution reminder 可从已有 Today plan 生成、展示、标记已读并派发。
- 验证 scheduler plan 和 celery beat proposal 仍可查询。

### 非目标

- 不新增业务 API。
- 不新增数据库表或 migration。
- 不接真实第三方 provider。
- 不启动真实 Celery worker / Beat。

---

## 3. 产品约束对齐

### 核心路径

```text
Data Source -> Capture -> Inbox -> Today -> Reminder Center -> Scheduler Contract
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

P3 smoke 用开发者可重复验证的方式保证“复杂度在背后”，用户可见仍是轻量的 Today、精力提示和温和提醒，不让接入和调度能力破坏克制感。

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
| P3 smoke script | 运行自然生长闭环回归 | Must | 使用真实本地 DB |
| Health sync check | fake health provider 同步到 Energy Dashboard | Must | 不接真实账号 |
| External import check | calendar item 进入 Capture / Inbox / Task | Must | 先归类为 Task，保留 source context |
| Reminder check | execution reminder 生成、summary、已读、dispatch | Must | 只用已有 Today plan |
| Scheduler check | 查询 scheduler plan / beat proposal | Must | 不触发调度 |

### 用户故事

```text
作为 Chronos 用户，
我希望日历和健康数据接入后仍然自然服务今天的执行安排，
以便系统更懂我的上下文，但不会变得喧闹或失控。
```

```text
作为后端开发者，
我希望 P3 自然生长能力有一条可重复 smoke 回归，
以便后续改动能快速发现跨模块闭环断裂。
```

### 主要流程

```text
Seed user
-> enable reminder settings
-> connect health source
-> sync health metric
-> read Energy Dashboard
-> connect calendar source
-> external import to Capture / Inbox
-> classify Inbox item as Task
-> confirm Inbox to Task
-> create/read Today
-> generate execution reminder
-> read reminder summary
-> batch mark seen
-> dispatch due reminder
-> read scheduler contracts
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [ ] Service
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

无。

### 事件变更

复用既有事件：

- `EXTERNAL_CAPTURE_IMPORTED`
- `DATA_SOURCE_SYNCED`

### API 变更

无新增 API。脚本复用既有 P1-P3 API。

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

说明：本轮只做 smoke，不新增 LLM 行为。

---

## 7. 验收标准

### 功能验收

- [x] 脚本能 seed 独立用户并打开提醒设置。
- [x] health source fake metric 能同步进 Energy Dashboard。
- [x] calendar external import 能先归类为任务，再确认成任务，并保留 `source_context`。
- [x] Today 能包含导入任务。
- [x] execution reminder 能从当前用户已有 Today plan 生成。
- [x] Reminder summary 能看到 pending / unseen。
- [x] batch seen 能标记提醒已读。
- [x] dispatch worker 能把 due in-app reminder 置为 sent。
- [x] scheduler plan 和 celery beat proposal 能返回 reminder worker 条目。

### 数据验收

- [x] 不新增 schema。
- [x] 不影响其他用户数据隔离。
- [x] 只读 scheduler endpoint 不写库。

### 体验验收

- [x] P3 接入能力仍围绕 Today 执行闭环。
- [x] 自动提醒温和、可解释，并保留用户控制感。

---

## 8. 测试计划

### 单元测试

- [x] 复用既有全量测试。

### API 测试

- [x] 复用既有全量测试。

### 集成测试

- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| smoke 使用真实本地 DB | 本地历史数据可能影响断言 | 脚本 seed 独立用户，并用单用户 execution generator |
| dispatch worker 是全局扫描 | 可能派发其他 due reminder | 断言当前 smoke reminder 最终变为 sent |
| fake provider 与真实 provider 有差距 | 不能代表 OAuth/真实 API 稳定性 | 当前只验证 Chronos 内部闭环，真实 provider 留到 P3 后续 |

### 关键取舍

本轮不追求真实第三方接入，而是优先保证 Chronos 内部 P3 闭环稳定：数据先自然进入系统，再服务 Today 和 Reminder，而不是让后台自动化直接接管用户计划。

---

## 10. Review 记录

### 自检结论

- 与产品定位一致：验证“接入和提醒”服务每日执行，不扩成通用自动化平台。
- 与交互流程一致：外部输入仍走 Capture / Inbox / 用户归类 / Today，而不是绕过确认层。
- 与架构边界一致：scheduler contract 只读，execution reminder 只消费已有 Today plan。

### 后续建议

- 下一轮可补 P3 smoke 在 README / 开发规范中的运行入口。
- 后续真实 provider 接入前，需要单独补 OAuth/token 安全设计文档。
