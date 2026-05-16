# Iteration: P1 Daily Report / Me Overview

> 状态：Done
> 阶段：P1
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 Chronos P1 的反馈层基础能力：Daily Report 汇总当天执行结果，Me Overview 提供个人基础数据总览，让 `Capture -> Inbox -> Today -> Focus -> Report / Me` 的数据闭环成立。

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

Today / Focus 已经能产生执行顺序、完成、延后、中断和专注时长。下一步需要把这些执行数据收敛为每日反馈，给用户一个轻量复盘入口，也为后续 Rolling Plan 学习提供行为数据。

### 目标

- 新增 `DailyReport` 模型和 migration。
- 实现 Daily Report 获取与生成 API。
- 汇总当天完成任务数、延后任务数、中断数、Focus 时长、完成率。
- 生成 P1 规则版简洁建议，不接真实 LLM。
- 实现 `GET /api/v1/me/overview`，返回 Profile、今日数据、本周 Focus、Goal / Task 基础统计、Report 入口和设置摘要。

### 非目标

- 不实现 Weekly / Monthly Report。
- 不实现复杂 Insight Detail。
- 不实现真实 LLM Report Generator。
- 不实现 Me 的 Energy / Social / Gamification 模块。
- 不实现完整 Settings 修改接口。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me
- [x] Goals
- [x] AI Agent

### 产品人格

Daily Report 只回答当天发生了什么、有什么轻量建议。Me Overview 只提供基础数据总览，不把洞察、解释和复杂分析推到前台。

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
| DailyReport 模型 | 持久化每日复盘快照 | Must | 一天一个 report |
| Daily Report Generate | 基于当天执行数据生成 / 刷新 report | Must | P1 同步规则生成 |
| Daily Report Get | 读取 report，不存在时 lazy generate | Must | 保证页面可打开 |
| Me Overview | 返回基础个人数据总览 | Must | 不做复杂洞察 |
| ActivityEvent | Report 生成写入事件 | Must | 服务后续行为学习 |

### 用户故事

```text
作为 Chronos 用户，
我希望完成一天执行后看到轻量复盘，
了解今天完成了多少、专注了多久、哪些任务被延后或中断，
以便明天更清楚地开始。
```

### 主要流程

```text
GET /reports/daily
-> DailyReport lazy generate
-> ActivityEvent + FocusSession + DailyPlan 聚合
-> 返回 DailyReport

GET /me/overview
-> 聚合今日 / 本周 / Goal / Task / Report 入口
-> 返回基础数据总览
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
DailyReport
```

核心字段：

```text
user_id
daily_plan_id
report_date
completed_task_count
postponed_task_count
interrupted_count
focus_minutes
completion_rate
ai_summary
ai_suggestions
generated_from_plan_version
refreshed_at
```

约束：

```text
unique(user_id, report_date)
```

### 状态机变更

本迭代不新增业务状态机。

### 事件变更

- DAILY_REPORT_GENERATED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/reports/daily` | 获取当天 Daily Report，不存在则生成 | `report_date` query | DailyReportResponse |
| POST | `/api/v1/reports/daily/generate` | 生成 / 刷新 Daily Report | `report_date` query | DailyReportResponse |
| GET | `/api/v1/reports/daily/{report_date}` | 获取指定日期 Daily Report | path date | DailyReportResponse |
| GET | `/api/v1/me/overview` | 获取 Me 基础总览 | `today` query | MeOverviewResponse |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及 mock/rule Agent
- [ ] 新增真实 Agent
- [ ] 修改真实 LLM Prompt
- [ ] 修改 Structured Output
- [x] 修改 fallback

### Agent 设计

P1 不接真实 LLM。`ReportService` 使用规则生成 `ai_summary` 和 `ai_suggestions`：

- 输入：`ActivityEvent`、`FocusSession`、`DailyPlan`
- 输出：`DailyReport`
- fallback：即使当天没有执行数据，也能生成空状态 report
- 是否需要用户确认：不需要，Report 是反馈快照

### LLM 安全边界

- [x] Report 不直接改变 Task / Goal / Today 状态。
- [x] P1 规则建议简洁，不产生复杂洞察。
- [x] 核心反馈不依赖真实 LLM 可用性。

---

## 7. 验收标准

### 功能验收

- [x] 可以生成并持久化 DailyReport。
- [x] DailyReport 能汇总完成任务数。
- [x] DailyReport 能汇总延后任务数。
- [x] DailyReport 能汇总 Focus 中断数。
- [x] DailyReport 能汇总 Focus 时长。
- [x] DailyReport 能引用 DailyPlan version。
- [x] Me Overview 能返回今日完成率和本周 Focus 时长。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] `DailyReport` 一天一个唯一快照。
- [x] `generate` 可刷新同一个 report。
- [x] Report 生成写入 `ActivityEvent`。
- [x] Me Overview 不会隐式生成 DailyReport。

### 体验验收

- [x] Daily Report response 不返回复杂 score factors。
- [x] Me Overview 不返回 P2/P3/P4 的复杂模块数据。
- [x] 核心流程不依赖真实 LLM。

---

## 8. 测试计划

### 单元测试

- [x] Daily Report 汇总完成 / 延后 / 中断 / Focus 时长。
- [x] `get_or_generate` 幂等。
- [x] `generate` 刷新同一 report。
- [x] Me Overview 返回基础反馈且不隐式生成 report。

### API 测试

- [x] `GET /reports/daily`
- [x] `POST /reports/daily/generate`
- [x] `GET /reports/daily/{report_date}`
- [x] `GET /me/overview`
- [x] user isolation

---

## 9. 验证记录

- [x] `.venv/bin/python -m unittest discover -s tests`
- [x] `.venv/bin/python -m compileall app tests scripts`
- [x] `.venv/bin/alembic upgrade head --sql`
- [x] `.venv/bin/alembic upgrade head`
- [x] `.venv/bin/alembic current`
- [x] `git diff --check`

---

## 10. 风险与后续

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| P1 建议为规则生成 | 文案智能度有限 | 后续替换 Daily Report Generator Agent |
| Me Overview 较轻 | 暂不覆盖 Energy / Insights / Social | 按 P2/P3/P4 逐步扩展 |
| Report 按执行事件聚合 | 依赖事件写入完整性 | 继续要求关键状态变化同事务写 ActivityEvent |

---

## 11. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | P1 Report 同步规则生成 | 不让真实 LLM 阻塞闭环 | 后续可平滑替换 Agent |
| 2026-05-16 | Me Overview 不隐式生成 report | 避免查看 Me 产生复盘快照副作用 | Report 入口只显示是否可用 |
| 2026-05-16 | Daily Report 不改变任务状态 | Report 是反馈层，不是调度层 | 保持用户控制感 |

---

## 12. 文件变更

| 日期 | 变更 | 文件 | 说明 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 DailyReport 模型和 migration | `app/models/report.py`、`alembic/versions/20260516_0006_daily_reports.py` | P1 反馈快照 |
| 2026-05-16 | 新增 Report Service / API / Schema | `app/services/report_service.py`、`app/api/v1/reports.py`、`app/schemas/reports.py` | Daily Report |
| 2026-05-16 | 新增 Me Overview | `app/services/me_service.py`、`app/api/v1/me.py`、`app/schemas/me.py` | 基础数据总览 |
| 2026-05-16 | 新增测试 | `tests/test_report_me_services.py`、`tests/test_report_me_api.py` | 回归覆盖 |

---

## 13. 下一步

- review 本迭代需求和代码。
- 如无优化项，进入下一轮：P1 Task Detail 聚合接口或 AIJob 查询接口。
