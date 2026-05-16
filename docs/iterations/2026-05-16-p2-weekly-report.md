# Iteration: P2 Weekly Report Aggregate

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-16  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

补齐 P2 Reports 路径的 Weekly Report 轻量聚合能力，让 Me -> Reports 可以看到一周执行趋势、高价值任务推进、Focus 总量和滞后任务，而不把报告页做成复杂驾驶舱。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [ ] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P1 已经支持 Daily Report 和 Me Overview，P2 需要开始承接复盘路径：

```text
Today / Me -> Daily Report / Weekly Report / Monthly Report
```

Weekly Report 是 Reports & Insights System 的第一层增强，但它仍应保持克制：帮助用户看到本周趋势和风险，不替代 Today 的每日执行决策。

### 目标

- 新增 `GET /api/v1/reports/weekly`。
- 返回本周每日趋势、周汇总、Focus 汇总、滞后任务和轻量建议。
- 复用已有 DailyReport / Focus / Task / Goal / ActivityEvent 数据，不新增持久化模型。
- 保持用户本地日期和本地周口径。

### 非目标

- 不实现 Monthly Report。
- 不实现 Insight Detail。
- 不接真实 LLM。
- 不新增 WeeklyReport 持久化表。
- 不让 Weekly Report 反向修改 Task / Goal / Today 状态。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
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

- 轻盈：只返回必要趋势和风险，不堆叠复杂指标。
- 克制：最多返回 5 个滞后任务，建议保持短句。
- 可信赖：所有指标来自已有执行事件和状态，不伪造洞察。
- 不施压：建议强调重新判断和保护重要任务，不催促用户“多做”。
- 聪明但不炫耀：提供高价值任务与滞后任务判断，但不暴露复杂 score factors。

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
| Weekly Report API | 获取用户某一周的报告聚合 | Must | `week_start` 会归一到周一 |
| Daily Trends | 返回 7 天每日计划数、完成数、延后数、中断数、Focus 时长、完成率 | Must | 复用 `daily_metrics` |
| Weekly Summary | 返回周总完成、延后、中断、Focus、高价值完成、风险目标、滞后任务 | Must | P2 轻量口径 |
| Focus Summary | 返回周 Focus 总时长、活跃日均值、最佳 Focus 日期 | Should | 支撑 Me Reports |
| Lagging Tasks | 返回最多 5 个滞后任务 | Should | 高价值优先 |
| Suggestions | 返回规则建议 | Could | 不接 LLM |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Me / Reports 里看到本周执行趋势，
以便知道哪些高价值任务推进了、哪些任务需要重新决策。
```

### 主要流程

```text
进入 Me
-> 查看 Reports
-> 打开 Weekly Report
-> 查看周汇总 / 每日趋势 / Focus / 滞后任务
-> 回到 Today 调整下一轮执行
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

无。Weekly Report 当前是只读聚合，不新增数据库表。

### 状态机变更

无。

### 事件变更

不新增事件。读取已有事件：

- `TASK_COMPLETED`
- `TASK_POSTPONED`
- `FOCUS_SESSION_COMPLETED`
- `FOCUS_SESSION_INTERRUPTED`
- `FOCUS_SESSION_POSTPONED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/reports/weekly` | 获取某周 Weekly Report 聚合 | `week_start` query，可选 | `WeeklyReportResponse` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

无。

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本迭代不调用 LLM，上述边界沿用项目级约束。

---

## 7. 验收标准

### 功能验收

- [x] 可以按用户本地周返回 `week_start` 和 `week_end`。
- [x] 可以返回 7 天 daily trends。
- [x] 可以汇总完成数、延后数、中断数、Focus 时长和平均完成率。
- [x] 可以统计高价值任务完成数。
- [x] 可以返回 active goal count、at-risk goal count 和 overdue task count。
- [x] 可以返回最多 5 个 lagging tasks。

### 数据验收

- [x] 不新增业务表。
- [x] 不改变 Task / Goal / Today 状态。
- [x] 用户隔离由现有 API dependency 和 service 查询条件保证。
- [x] 日期边界使用用户 timezone。

### 体验验收

- [x] 用户能清楚知道本周的趋势和下一步关注点。
- [x] 页面默认信息不过载。
- [x] AI 解释克制可信。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Service 测试 Weekly Report 聚合。
- [x] Service 测试 Focus / high-value / lagging task 口径。

### API 测试

- [x] 正常路径。
- [x] 当前用户数据读取。

### 集成测试

- [ ] DB migration：无新增 migration。
- [ ] Worker / AIJob：不涉及。
- [ ] fallback 路径：规则建议。

### 手动验证

```text
1. 创建 goal / high value task / overdue task。
2. 进入 Today 并完成一次 Focus。
3. 调用 GET /api/v1/reports/weekly。
4. 确认 weekly summary、daily trends、focus、lagging tasks 正确。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Weekly Report 不持久化 | 无法保留历史快照 | 当前优先保持简单；后续 Monthly / Insight 可再评估快照模型 |
| 高价值完成依赖 ActivityEvent | 如果旧数据缺事件会少算 | P1 后续要求关键状态变化同事务写事件 |
| at-risk goal 是规则判断 | 不等于真实 AI 风险预测 | P2 先以 deadline + unfinished tasks 做可信规则 |

### 关键取舍

- 取舍 1：先做只读聚合，不新增 `WeeklyReport` 表，降低数据模型复杂度。
- 取舍 2：建议文案使用规则生成，不接 LLM，避免报告路径依赖外部模型可用性。
- 取舍 3：Weekly Report 只反馈趋势和风险，不提供重新调度动作，避免抢走 Today 的行动感。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | `week_start` 归一到周一 | 降低前端传参成本 | 前端可传任意周内日期 |
| 2026-05-16 | Weekly Report 不持久化 | P2 先验证反馈层价值 | 无 migration，后续可升级 |
| 2026-05-16 | 滞后任务最多返回 5 个 | 保持克制，避免信息过载 | 前端默认展示更轻 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Weekly Report schemas | `app/schemas/reports.py` | P2 response contract |
| 2026-05-16 | 新增 Weekly Report service 聚合 | `app/services/report_service.py` | 复用 daily metrics |
| 2026-05-16 | 新增 Weekly Report API | `app/api/v1/reports.py` | `GET /reports/weekly` |
| 2026-05-16 | 补充测试 | `tests/test_report_me_services.py`、`tests/test_report_me_api.py` | 聚合与 API |
| 2026-05-16 | 更新文档 | `docs/chronos-backend-architecture-v1.md`、`docs/chronos-p1-frontend-api-contract.md` | 对齐 API |

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

- P2 Strategy Detail：解释 Today 策略和滚动计划原因。
- P2 Insight Detail：从 Weekly Report 进一步沉淀行为模式。
- P2 Monthly Report：扩展长期目标和行为趋势。
