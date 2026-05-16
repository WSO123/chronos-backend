# Iteration: P2 Monthly Report Aggregate

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-16  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

新增 `GET /api/v1/reports/monthly`，把 Reports 反馈层从 Daily / Weekly 扩展到 Monthly，用于长期目标趋势和行为节奏回看，同时保持只读、轻量、不持久化。

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

P2 Reports & Insights System 需要 Monthly Report。Daily Report 回答“今天发生了什么”，Weekly Report 回答“这一周的趋势如何”，Monthly Report 则用于更长周期地观察高价值任务推进、Focus 总量、目标风险和滞后任务。

### 目标

- 新增 Monthly Report API / schema / service。
- 返回月度 summary、weekly trends、daily trends 和轻量建议。
- 复用现有 Daily Metrics / Task / Goal / FocusSession 数据。
- 不新增 MonthlyReport 持久化表。

### 非目标

- 不接真实 LLM。
- 不实现深度长期行为模型。
- 不修改 Task / Goal / Today 状态。
- 不替代 Today 的执行序列。

---

## 3. 产品约束对齐

### 核心路径

```text
Today / Me -> Daily Report / Weekly Report / Monthly Report
```

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [x] Report
- [x] Me
- [x] Goals
- [ ] AI Agent

### 产品人格

- 轻盈：月报只返回趋势和少量建议。
- 克制：不做复杂 scoring dashboard。
- 可信赖：指标来自现有执行数据。
- 不施压：建议强调清理和保护，而不是多做。
- 聪明但不炫耀：展示可理解趋势，不展示复杂模型细节。

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Monthly Report API | 获取某月聚合报告 | Must | `month` 可选 |
| Monthly Summary | 完成、专注、高价值、风险和滞后汇总 | Must | 规则聚合 |
| Weekly Trends | 将月内数据按 7 天区块聚合 | Should | 服务图表 |
| Daily Trends | 返回每日趋势 | Should | 前端可按需图表化 |
| Suggestions | 返回轻量建议 | Could | 规则生成 |

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

无。Monthly Report 是只读聚合，不新增数据库表。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/reports/monthly` | 获取月度报告聚合 | `month` query，可选 | `MonthlyReportResponse` |

---

## 6. AI / LLM 影响

- [x] 不涉及真实 LLM 调用
- [x] 使用规则 fallback 输出

---

## 7. 验收标准

- [x] 可以按月份返回 `month_start` / `month_end`。
- [x] 可以返回 summary、weekly trends、daily trends。
- [x] 可以统计高价值完成、Focus 总量、风险目标和滞后任务。
- [x] 不改变 Task / Goal / Today 状态。
- [x] 用户隔离由现有 dependency 和 service 查询条件保证。

---

## 8. 测试计划

- [x] Service 测试 Monthly Report 聚合。
- [x] API 测试 Monthly Report 正常路径。
- [x] 全量测试后补充验证。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 不持久化月报 | 历史快照无法固定 | P2 先验证展示价值，后续可加快照表 |
| 周趋势不是自然周 | 月内 7 天区块更简单 | 前端文档说明是趋势区块 |
| 规则建议朴素 | 智能感有限 | 后续接 Monthly Report Agent |

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | Monthly Report 不持久化 | 保持 P2 轻量 | 无 migration |
| 2026-05-16 | 复用 daily metrics | 保持口径一致 | 降低重复逻辑 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Monthly Report schema | `app/schemas/reports.py` | P2 response contract |
| 2026-05-16 | 新增 Monthly Report service | `app/services/report_service.py` | 规则聚合 |
| 2026-05-16 | 新增 Monthly Report API | `app/api/v1/reports.py` | `GET /reports/monthly` |
| 2026-05-16 | 补充测试 | `tests/test_report_me_services.py`、`tests/test_report_me_api.py` | service / API |

---

## 12. 验证结果

### 已验证

- [x] `python -m unittest tests.test_report_me_services tests.test_report_me_api`
- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `git diff --check`
- [x] `python scripts/smoke_p1_execution_loop.py`

### 未验证

- [ ] 真实前端联调。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- P2 Dependency View / 任务依赖基础能力。
- P2 Today Insights Preview。
